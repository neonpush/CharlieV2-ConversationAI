"""
Call management API endpoints.

These endpoints handle initiating and managing phone calls.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response                                
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from app.db.database import get_db
from app.services.lead_service import LeadService
from app.services.call_service import CallService
from app.services.elevenlabs_prewarm import get_prewarm_service
from app.services.twilio_service import TwilioService
from app.core.config import settings
from pydantic import BaseModel, Field
from app.schemas.call import CallCreate, CallUpdate
import logging
from app.core.logging import with_context

router = APIRouter(
    prefix="/api/calls",
    tags=["calls"]
)

logger = logging.getLogger(__name__)


class CallRequest(BaseModel):
    """     
    Request model for initiating a call.
    """
    lead_id: int = Field(..., description="ID of the lead to call")
    phone_override: Optional[str] = Field(None, description="Override phone number")
    use_elevenlabs_telephony: Optional[bool] = Field(True, description="If false, use Twilio bridge instead of ElevenLabs")


class TwilioStatusCallback(BaseModel):
    """
    Twilio status callback data.
    
    Twilio sends this when call status changes.
    """
    CallSid: str
    CallStatus: str
    To: str
    From: str
    Direction: str
    Duration: Optional[str] = None
    AnsweredBy: Optional[str] = None  # human, machine, or unknown


@router.post("/initiate")
async def initiate_call(
    request: CallRequest,
    db: Session = Depends(get_db)
):
    """
    Initiate a phone call to a lead.
    
    This will:
    1. Get the lead from database
    2. Pre-populate ElevenLabs with lead context
    3. Make call via Twilio
    4. Connect to ElevenLabs agent
    
    Args:
        request: Contains lead_id and optional phone override
        db: Database session
        
    Returns:
        Call initiation details
    """
    log = with_context(logger, lead_id=request.lead_id)
    log.info("Initiating call")
    
    # Get the lead
    lead_service = LeadService(db)
    lead = lead_service.get_lead(request.lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {request.lead_id} not found"
        )
    
    # Determine phone number to use
    phone_to_call = request.phone_override or lead.phone
    
    if not phone_to_call:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number available for this lead"
        )
    
    # Optional: Pre-warm variables/prompt for faster connect
    try:
        get_prewarm_service().prewarm_for_lead(lead)
    except Exception:
        pass

    # Build context for ElevenLabs
    # Note: ElevenLabs doesn't support full pre-population,
    # but we can pass dynamic variables through the agent URL
    from app.services.elevenlabs_service import ElevenLabsService
    elevenlabs_service = ElevenLabsService()
    
    # Build dynamic variables that can be used in prompts
    dynamic_vars = elevenlabs_service.build_dynamic_variables(lead)
    
    # Build custom agent URL with context
    # Note: We don't pass the ElevenLabs URL to Twilio
    # Twilio will call our TwiML endpoint, which then connects to ElevenLabs
    
    log.info(f"Built context with {len(dynamic_vars)} variables")
    
    # Make the call, either via ElevenLabs Telephony or Twilio
    if request.use_elevenlabs_telephony or not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        from app.services.elevenlabs_service import ElevenLabsService
        es = ElevenLabsService()
        
        # Create call record first with system prompt
        call_service = CallService(db)
        
        # Get the system prompt that will be used for this call
        system_prompt = dynamic_vars.get("system_prompt", "")
        
        call_record = call_service.create_call(CallCreate(
            lead_id=lead.id,
            system_prompt=system_prompt,
            status="initiated"
        ))
        
        try:
            data = await es.initiate_outbound_call_via_elevenlabs(lead=lead, to_number=phone_to_call)
            
            # Extract conversation_id from ElevenLabs response and update call record
            conversation_id = data.get("conversation_id")
            if conversation_id:
                call_service.update_call(call_record.id, CallUpdate(
                    conversation_id=conversation_id,
                    status="in_progress"
                ))
                log.info(f"Stored conversation_id {conversation_id} for call {call_record.id}")
            
        except Exception as e:
            # Mark call as failed
            call_service.update_call(call_record.id, CallUpdate(status="failed"))
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

        log.info("Call initiated via ElevenLabs Telephony")
        return {
            "message": "Call initiated successfully (ElevenLabs)",
            "provider": "elevenlabs",
            "lead_id": lead.id,
            "phone": phone_to_call,
            "call_id": call_record.id,
            "conversation_id": conversation_id,
            "provider_response": data,
            "dynamic_variables": dynamic_vars,
        }
    else:
        twilio_service = TwilioService()
        result = twilio_service.make_call_to_lead(
            lead_id=lead.id,
            to_number=phone_to_call,
            agent_url=None
        )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to initiate call")
        )
    
    # Add call_sid to log context for downstream operations
    log = with_context(logger, lead_id=lead.id, call_sid=result.get("call_sid"))
    log.info("Call initiated")

    return {
        "message": "Call initiated successfully",
        "provider": "twilio",
        "call_sid": result["call_sid"],
        "status": result["status"],
        "lead_id": lead.id,
        "phone": phone_to_call,
        "dynamic_variables": dynamic_vars
    }


@router.get("/status/{call_sid}")
async def get_call_status(call_sid: str):
    """
    Get the current status of a call.
    
    Args:
        call_sid: Twilio call SID
        
    Returns:
        Current call status
    """
    logger.debug(f"Checking status for call {call_sid}")
    
    twilio_service = TwilioService()
    status = twilio_service.get_call_status(call_sid)
    
    if "error" in status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=status["error"]
        )
    
    return status


@router.post("/twilio/status")
async def twilio_status_webhook(request: Request):
    """
    Webhook for Twilio call status updates.
    
    Twilio calls this endpoint when call status changes.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Simple acknowledgment
    """
    # Get form data (Twilio sends as form-encoded)
    form_data = await request.form()
    
    # Check if this is a Stream status update (WebSocket status)
    stream_sid = form_data.get("StreamSid")
    if stream_sid:
        # This is a WebSocket stream status callback
        stream_status = form_data.get("StreamStatus")
        error_code = form_data.get("ErrorCode")
        error_message = form_data.get("ErrorMessage")
        
        logger.warning(f"Stream status: {stream_status}")
        if error_code or error_message:
            logger.error(f"Stream failed - Code: {error_code}, Message: {error_message}")
        
        # Log all stream data for debugging
        logger.info("Full stream status data:")
        for key, value in form_data.items():
            logger.info(f"  {key}: {value}")
        
        return Response(content="", status_code=200)
    
    # Regular call status update
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    to_number = form_data.get("To")
    from_number = form_data.get("From")
    duration = form_data.get("Duration")
    
    log = with_context(logger, call_sid=call_sid)
    log.info(f"Call status update: {call_status}")
    log.debug(f"Call details - To: {to_number}, Duration: {duration}s")
    
    # Here you could:
    # 1. Update lead status in database
    # 2. Trigger follow-up actions
    # 3. Send notifications
    
    # For now, just log it
    if call_status == "completed":
        log.info(f"Call completed. Duration: {duration} seconds")
    elif call_status == "failed":
        log.warning("Call failed")
    elif call_status == "busy":
        log.info("Busy signal")
    elif call_status == "no-answer":
        log.info("No answer")
    
    # Twilio expects a simple response
    return {"status": "received"}