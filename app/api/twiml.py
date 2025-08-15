"""
TwiML endpoints for handling Twilio calls.

This creates a bridge between Twilio and ElevenLabs,
allowing us to pass dynamic variables properly.
"""

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse, Connect
from app.db.database import get_db
from app.services.lead_service import LeadService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.prompt_storage import get_prompt_storage
from app.core.config import settings
import logging
from app.core.logging import with_context
import json
import urllib.parse
import base64

router = APIRouter(
    prefix="/twiml",
    tags=["twiml"]
)

logger = logging.getLogger(__name__)


@router.post("/answer")
async def answer_call(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    TwiML endpoint that Twilio calls when the phone is answered.
    
    This is where we can inject lead data before connecting to ElevenLabs.
    
    Args:
        lead_id: ID of the lead being called
        request: Twilio webhook request
        db: Database session
        
    Returns:
        TwiML response directing the call
    """
    # Read lead_id from query string
    lead_id_str = request.query_params.get("lead_id")
    if not lead_id_str or not lead_id_str.isdigit():
        response = VoiceResponse()
        response.say("Sorry, this call is not associated with a lead. Goodbye.")
        response.hangup()
        return Response(content=str(response), media_type="text/xml")

    lead_id = int(lead_id_str)

    log = with_context(logger, lead_id=lead_id)
    log.info("Answering call")
    
    # Get the lead data
    lead_service = LeadService(db)
    lead = lead_service.get_lead(lead_id)
    
    if not lead:
        # If lead not found, play error message and hang up
        response = VoiceResponse()
        response.say("Sorry, there was an error with this call. Goodbye.")
        response.hangup()
        return Response(content=str(response), media_type="text/xml")
    
    # Build dynamic variables for ElevenLabs
    elevenlabs_service = ElevenLabsService()
    dynamic_vars = elevenlabs_service.build_dynamic_variables(lead)
    
    # STORE THE FULL SYSTEM PROMPT AND GET A REFERENCE ID
    prompt_storage = get_prompt_storage()
    
    # Extract the system prompt and first message from variables
    system_prompt = dynamic_vars.pop("system_prompt", "")
    first_message = dynamic_vars.pop("first_message", "")
    
    # Store the prompt and get a reference ID
    prompt_ref = prompt_storage.store_prompt(
        lead_id=lead.id,
        system_prompt=system_prompt,
        first_message=first_message,
        variables=dynamic_vars
    )
    
    log.info(f"Stored prompt with reference: {prompt_ref}")
    
    # Create TwiML response
    response = VoiceResponse()
    
    # Option 1: Use Connect verb to connect to ElevenLabs WebSocket
    # Prefer signed URL for private agents; fall back to configured URL
    ws_url: str | None = None
    if settings.elevenlabs_agent_id and settings.elevenlabs_api_key:
        try:
            # Generate short-lived signed WS URL server-side
            ws_url = await elevenlabs_service.get_signed_conversation_url()
        except Exception as e:
            log.error(f"Failed to get signed ElevenLabs URL: {e}")
            ws_url = None
    if not ws_url and settings.elevenlabs_agent_url:
        # Fallback to static configured URL (public agent)
        ws_url = settings.elevenlabs_agent_url

        # Encode dynamic variables (including prompt + first message) as base64 JSON
        try:
            payload_vars = dict(dynamic_vars)
            payload_vars["system_prompt"] = system_prompt
            payload_vars["first_message"] = first_message
            encoded_vars = base64.b64encode(json.dumps(payload_vars).encode()).decode()
        except Exception:
            encoded_vars = ""

        # Connect to ElevenLabs and pass parameters via <Parameter>
        connect = Connect()
        # Add simple status callback to see WebSocket errors
        stream = connect.stream(
            url=ws_url,
            status_callback=f"{settings.public_base_url}/api/calls/twilio/status",
            status_callback_method="POST"
        )
        
        # Minimal identifiers
        stream.parameter(name="prompt_ref", value=prompt_ref)
        stream.parameter(name="lead_id", value=str(lead.id))
        # Helpful lightweight context
        if lead.name:
            stream.parameter(name="customer_name", value=lead.name)
        if lead.phase:
            stream.parameter(name="phase", value=str(lead.phase))
        # Bulk variables payload (optional, may be empty if encoding fails)
        if encoded_vars:
            stream.parameter(name="variables_b64", value=encoded_vars)

        response.append(connect)

        log.info(f"Connecting to ElevenLabs at {ws_url}")
        log.info(f"Sending {len(dynamic_vars)} variables via TwiML parameters")
    
    else:
        # Fallback: Use text-to-speech if no ElevenLabs URL
        greeting = elevenlabs_service.get_phase_first_message(lead)
        response.say(greeting)
        
        # Gather input (optional)
        response.pause(length=2)
        response.say("Please stay on the line.")
        
    return Response(content=str(response), media_type="text/xml")


@router.post("/status/{lead_id}")
async def call_status(
    lead_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle call status updates from Twilio.
    
    Args:
        lead_id: ID of the lead
        request: Twilio status webhook
        db: Database session
        
    Returns:
        Empty response (Twilio doesn't need content)
    """
    # Get form data from Twilio
    form_data = await request.form()
    call_status = form_data.get("CallStatus")
    call_sid = form_data.get("CallSid")
    duration = form_data.get("CallDuration")
    
    logger.info(f"Call status for lead {lead_id}: {call_status} (SID: {call_sid})")
    
    # You could update lead status here based on call outcome
    if call_status == "completed":
        logger.info(f"Call completed for lead {lead_id}, duration: {duration}s")
        # Could update lead phase or add notes
        
    elif call_status in ["failed", "busy", "no-answer"]:
        logger.warning(f"Call failed for lead {lead_id}: {call_status}")
        # Could mark for retry or update status
    
    return Response(content="", status_code=200)




