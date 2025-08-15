"""
ElevenLabs Personalization webhook.

Returns a variables map that includes first_message and system_prompt
so agents that template these values have them available as dynamic vars.
"""

from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional
from app.db.database import get_db
from app.services.lead_service import LeadService
from app.services.call_service import CallService
from app.services.elevenlabs_service import ElevenLabsService
from app.schemas.call import CallTranscriptUpdate
from app.core.config import settings
import logging
import hmac
import hashlib
import time
import re
from app.db.models import Lead as LeadModel


router = APIRouter(prefix="/elevenlabs", tags=["elevenlabs"])

logger = logging.getLogger(__name__)


def _verify_signature(raw_body: bytes, header_val: Optional[str]) -> bool:
    secret = settings.elevenlabs_webhook_secret
    if not secret:
        return True
    if not header_val:
        return False

    try:
        parts = dict(p.strip().split("=", 1) for p in header_val.split(","))
        ts = int(parts.get("t", "0"))
        provided = parts.get("v0", "")
    except Exception:
        return False

    now = int(time.time())
    # Temporarily widen tolerance to help diagnose signature issues
    if ts < now - 2 * 60 * 60 or ts > now + 10 * 60:
        return False

    body_text = raw_body.decode("utf-8")
    # Primary scheme: sign "t.<body>"
    payload = f"{ts}.{body_text}"
    mac = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    expected = "v0=" + mac
    if hmac.compare_digest(provided, expected):
        return True
    # Fallback scheme: some send HMAC over body only
    mac2 = hmac.new(secret.encode("utf-8"), body_text.encode("utf-8"), hashlib.sha256).hexdigest()
    expected2 = "v0=" + mac2
    return hmac.compare_digest(provided, expected2)


def _redact_signature(sig: Optional[str]) -> str:
    if not sig:
        return ""
    try:
        parts = [p.strip() for p in sig.split(",")]
        out = []
        for p in parts:
            if p.startswith("v0="):
                out.append("v0=<redacted>")
            else:
                out.append(p)
        return ",".join(out)
    except Exception:
        return "<unparseable>"




def _debug_signature(raw_body: bytes, header_val: Optional[str]) -> None:
    """Log signature diagnostics (redacted) to help pinpoint mismatches."""
    try:
        body_len = len(raw_body)
        body_sha = hashlib.sha256(raw_body).hexdigest()
        if not header_val:
            logger.info("HMAC debug: no signature header; body_len=%s body_sha256=%s", body_len, body_sha)
            return
        parts = dict(p.strip().split("=", 1) for p in header_val.split(","))
        ts_str = parts.get("t", "0")
        v0 = parts.get("v0", "")
        red_v0 = (v0[:6] + "..." + v0[-6:]) if len(v0) > 12 else v0
        try:
            ts = int(ts_str)
        except Exception:
            ts = 0
        now = int(time.time())
        skew = now - ts
        # Compute expected signatures for diagnostics
        try:
            secret = settings.elevenlabs_webhook_secret or ""
            mac_t_body = hmac.new(secret.encode("utf-8"), f"{ts}.{raw_body.decode('utf-8')}".encode("utf-8"), hashlib.sha256).hexdigest() if secret else ""
            mac_body = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest() if secret else ""
            match_t_body = ("v0=" + mac_t_body) == v0 if mac_t_body else False
            match_body = ("v0=" + mac_body) == v0 if mac_body else False
        except Exception:
            match_t_body = False
            match_body = False
        logger.info(
            "HMAC debug: t=%s skew_s=%s v0=%s body_len=%s body_sha256=%s match_t_body=%s match_body=%s",
            ts_str,
            skew,
            red_v0,
            body_len,
            body_sha,
            match_t_body,
            match_body,
        )
    except Exception:
        pass


@router.post("/personalization")
async def personalization(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    # Server-initiated convenience: allow lead_id query param and skip signature
    lead_id_param = request.query_params.get("lead_id")
    if lead_id_param and lead_id_param.isdigit():
        lead_service = LeadService(db)
        lead = lead_service.get_lead(int(lead_id_param))
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        es = ElevenLabsService()
        full_vars = es.build_dynamic_variables(lead)
        first_message = full_vars.get("first_message", "")
        system_prompt = full_vars.get("system_prompt", "")
        # Return ONLY the two required variables
        variables = {
            "first_message": first_message,
            "system_prompt": system_prompt,
        }
        return {
            "type": "conversation_initiation_client_data",
            "dynamic_variables": variables,
        }

    # Webhook mode (called by ElevenLabs) - verify signature
    raw = await request.body()
    sig = request.headers.get("elevenlabs-signature") or request.headers.get("x-elevenlabs-signature")
    
    # TEMPORARY: Disable signature verification for testing
    logger.warning("PERSONALIZATION SIGNATURE VERIFICATION TEMPORARILY DISABLED FOR TESTING")
    # if not _verify_signature(raw, sig):
    #     # Fallback: accept shared secret header if provided (no HMAC)
    #     shared = request.headers.get("secret")
    #     if not shared or shared != settings.elevenlabs_webhook_secret:
    #         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        logger.info("EL personalization hit - headers: %s", {
            "content_type": request.headers.get("content-type"),
            "user_agent": request.headers.get("user-agent"),
            "signature": _redact_signature(sig),
        })
        logger.debug("EL personalization raw body (len=%d)", len(raw))
    except Exception:
        pass

    # Accept JSON or form-encoded payloads
    payload: Dict[str, Any] = {}
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict) or not payload:
        try:
            form = await request.form()
            payload = {k: v for k, v in form.items()}
            # If there is a 'payload' field with JSON string, try to parse it
            if isinstance(payload.get("payload"), str):
                import json as _json
                try:
                    nested = _json.loads(payload["payload"])  # type: ignore[index]
                    if isinstance(nested, dict):
                        # Merge but prefer top-level keys
                        for k, v in nested.items():
                            payload.setdefault(k, v)
                except Exception:
                    pass
        except Exception:
            payload = {}

    # Log the payload structure for debugging
    logger.info("Personalization webhook payload keys: %s", list(payload.keys()))
    logger.debug("Full personalization payload: %s", str(payload)[:500] + "..." if len(str(payload)) > 500 else str(payload))

    # Try to extract conversation_id from the payload
    conversation_id = None
    try:
        # Check for conversation_id in various possible locations
        if "conversation_id" in payload:
            conversation_id = payload["conversation_id"]
        elif isinstance(payload.get("data"), dict):
            conversation_id = payload["data"].get("conversation_id")
        elif isinstance(payload.get("call"), dict):
            conversation_id = payload["call"].get("conversation_id")
        
        logger.info("Personalization webhook - conversation_id: %s", conversation_id)
    except Exception as e:
        logger.warning("Failed to extract conversation_id from payload: %s", e)

    # Try to find call record and generate variables
    call_service = CallService(db)
    call_record = None
    
    # Method 1: Try to find by conversation_id (if available)
    if conversation_id:
        try:
            call_record = call_service.get_call_by_conversation_id(conversation_id)
            if call_record:
                logger.info("Found call record %s by conversation_id %s for lead %s", 
                           call_record.id, conversation_id, call_record.lead_id)
        except Exception as e:
            logger.error("Failed to lookup call by conversation_id %s: %s", conversation_id, e)
    
    # Method 2: If no call found by conversation_id, this might be an inbound call
    # Create Call records for inbound calls (with conversation_id OR call_sid)
    call_identifier = conversation_id or payload.get("call_sid")
    
    if not call_record and call_identifier:
        try:
            # Extract phone numbers from the payload 
            caller_phone = None
            called_phone = None
            
            # Extract caller phone - check all possible locations
            caller_phone = (
                payload.get("caller_id") or
                payload.get("from") or
                payload.get("caller_number")
            )
            
            # Also check nested data if no top-level phone found
            if not caller_phone:
                data = payload.get("data", {})
                if isinstance(data, dict):
                    caller_phone = (
                        data.get("caller_id") or 
                        data.get("from") or
                        data.get("caller_number") or
                        data.get("user_phone")
                    )
            
            logger.info("Inbound call detected - caller: %s, identifier: %s", caller_phone, call_identifier)
            
            if caller_phone:
                # Look up existing lead by phone
                lead = call_service._find_lead_by_phone(caller_phone)
                
                if lead:
                    logger.info("Found existing lead %s for inbound caller %s", lead.id, caller_phone)
                else:
                    # Create new lead for unknown inbound caller  
                    logger.info("Creating new lead for unknown inbound caller: %s", caller_phone)
                    from app.services.lead_service import LeadService
                    from app.schemas.lead import LeadCreate
                    
                    lead_service = LeadService(db)
                    lead = lead_service.create_lead(LeadCreate(
                        phone=caller_phone,
                        name="Unknown Caller"
                    ))
                    logger.info("Created new lead %s for inbound caller", lead.id)
                
                # Create call record for this inbound conversation
                # Use call_identifier (could be conversation_id or call_sid)
                from app.schemas.call import CallCreate
                call_record = call_service.create_call(CallCreate(
                    lead_id=lead.id,
                    conversation_id=call_identifier,  # Store whatever identifier we have
                    status="in_progress"
                ))
                logger.info("Created call record %s for inbound call with identifier %s", call_record.id, call_identifier)
                
            else:
                # No phone found - use unknown caller variables but don't create records yet
                logger.warning("Inbound call detected but no caller phone found in payload")
                # Still provide default variables for the call to proceed
                return {
                    "type": "conversation_initiation_client_data",
                    "dynamic_variables": {
                        "first_message": "Hello! I'm Charlie from Lobby. How can I help you today?",
                        "system_prompt": "You are Charlie from Lobby, a helpful real estate assistant. You're speaking with someone who called our number but we don't have their details yet. Be friendly and ask how you can help them today."
                    }
                }
                
        except Exception as e:
            logger.error("Failed to process inbound call: %s", e)
    
    # If we have a lead (either found or created), generate variables based on their current stage
    if 'lead' in locals() and lead:
        logger.info("Generating personalized variables for lead %s (phone: %s, phase: %s)", 
                   lead.id, lead.phone, lead.phase)
        
        # Generate fresh dynamic variables based on lead's current stage/progress
        es = ElevenLabsService()
        fresh_vars = es.build_dynamic_variables(lead)
        
        # ALWAYS ensure we have a call record for this conversation
        if not call_record:
            # Get ANY identifier we can use
            call_identifier = (
                conversation_id or 
                payload.get("call_sid") or 
                payload.get("conversation_id") or
                f"temp_{lead.id}_{int(datetime.now().timestamp())}"  # Fallback temp ID
            )
            
            # Check if a call with this identifier already exists
            existing_call = call_service.get_call_by_conversation_id(call_identifier)
            if existing_call:
                call_record = existing_call
                logger.info("Found existing call record %s for identifier %s", call_record.id, call_identifier)
            else:
                logger.info("ENSURING call record exists for lead %s with identifier %s", lead.id, call_identifier)
                from app.schemas.call import CallCreate
                from datetime import datetime
                
                call_record = call_service.create_call(CallCreate(
                    lead_id=lead.id,
                    conversation_id=call_identifier,
                    status="in_progress"
                ))
                logger.info("✅ Created call record %s for lead %s", call_record.id, lead.id)
        
        # Store the system prompt in the call record
        system_prompt = fresh_vars.get("system_prompt", "You are Charlie from Lobby.")
        if call_record:
            from app.schemas.call import CallUpdate
            call_service.update_call(call_record.id, CallUpdate(system_prompt=system_prompt))
            logger.info("✅ Updated call record %s with system prompt", call_record.id)
        
        variables = {
            "first_message": fresh_vars.get("first_message", "Hello, this is Charlie from Lobby. How can I help you today?"),
            "system_prompt": system_prompt
        }
        
        return {
            "type": "conversation_initiation_client_data",
            "dynamic_variables": variables,
        }
    
    # If we found a call record but no lead lookup happened above
    elif call_record and call_record.lead:
        logger.info("Using call record %s for lead %s", call_record.id, call_record.lead_id)
        
        # Generate fresh dynamic variables for this specific lead
        es = ElevenLabsService()
        fresh_vars = es.build_dynamic_variables(call_record.lead)
        
        variables = {
            "first_message": fresh_vars.get("first_message", "Hello, this is Charlie from Lobby. How can I help you today?"),
            "system_prompt": fresh_vars.get("system_prompt", "You are Charlie from Lobby.")
        }
        
        return {
            "type": "conversation_initiation_client_data",
            "dynamic_variables": variables,
        }
    else:
        logger.warning("No lead found for conversation_id: %s or phone lookup", conversation_id)

    # Fallback: use cached variables (old behavior)
    logger.info("Using fallback cached variables")
    try:
        from app.services.elevenlabs_prewarm import get_prewarm_service
        cached = get_prewarm_service().get_last_cached() or {}
    except Exception:
        cached = {}
    
    # Filter to ONLY first_message and system_prompt
    variables = {}
    if isinstance(cached, dict):
        if "first_message" in cached:
            variables["first_message"] = cached["first_message"]
        if "system_prompt" in cached:
            variables["system_prompt"] = cached["system_prompt"]
    
    if not variables:
        # Minimal safe defaults if nothing prewarmed
        variables = {
            "first_message": "Hello, this is Charlie from Lobby. How can I help you today?",
            "system_prompt": "You are Charlie from Lobby."
        }
    
    return {
        "type": "conversation_initiation_client_data",
        "dynamic_variables": variables,
    }


# Allow simple GET for dashboard tests/verification (returns 200)
@router.get("/personalization")
async def personalization_get() -> Dict[str, str]:
    return {"status": "ok", "hint": "POST this endpoint for conversation variables"}


@router.post("/transcript")
async def transcript_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    Receive post-call transcript from ElevenLabs and store it on the lead.
    Expected JSON: { "leadId": "5", "transcript": "..." }
    """
    # Verify signature (if configured)
    raw = await request.body()
    sig = request.headers.get("elevenlabs-signature") or request.headers.get("x-elevenlabs-signature")
    # Log diagnostics
    _debug_signature(raw, sig)
    
    # TEMPORARY: Log raw body for HMAC debugging
    logger.info("Raw body (first 200 chars): %s", raw[:200].decode('utf-8', errors='replace'))
    logger.info("Raw body length: %s", len(raw))
    logger.info("ELEVENLABS_WEBHOOK_SECRET configured: %s", settings.elevenlabs_webhook_secret[:15] + "..." if settings.elevenlabs_webhook_secret else "None")
    
    # TEMPORARY: Disable signature verification for testing
    logger.warning("SIGNATURE VERIFICATION TEMPORARILY DISABLED FOR TESTING")
    # if not _verify_signature(raw, sig):
    #     shared = request.headers.get("secret")
    #     if not shared or shared != settings.elevenlabs_webhook_secret:
    #         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    # Parse payload (accept JSON, else form fallback)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict) or not payload:
        try:
            form = await request.form()
            payload = {k: v for k, v in form.items()}
        except Exception:
            payload = {}
    
    # DETAILED LOGGING: Log the entire payload structure
    import json
    logger.info("=" * 80)
    logger.info("TRANSCRIPT WEBHOOK FULL PAYLOAD STRUCTURE:")
    logger.info("=" * 80)
    
    # Log top-level keys
    logger.info("Top-level keys: %s", list(payload.keys()))
    
    # Log the full payload (pretty printed)
    try:
        payload_json = json.dumps(payload, indent=2, default=str)
        # Split into lines and log each line to avoid truncation
        for line in payload_json.split('\n')[:100]:  # Limit to first 100 lines
            logger.info("  %s", line)
    except Exception as e:
        logger.error("Failed to pretty print payload: %s", e)
        logger.info("Raw payload: %s", str(payload)[:2000])
    
    logger.info("=" * 80)

    # Extract lead_id and transcript from ElevenLabs payload structure
    lead_id = payload.get("leadId") or payload.get("lead_id")
    transcript_text = payload.get("transcript")
    
    # Check nested data structure (ElevenLabs format)
    data = payload.get("data", {})
    if isinstance(data, dict):
        conversation_id = data.get("conversation_id")
        # Look for transcript in data.transcript or data.transcript array
        if not transcript_text:
            if isinstance(data.get("transcript"), str):
                transcript_text = data["transcript"]
            elif isinstance(data.get("transcript"), list):
                # Concatenate all transcript entries
                transcript_parts = []
                for entry in data["transcript"]:
                    if isinstance(entry, dict) and "message" in entry:
                        role = entry.get("role", "unknown")
                        message = entry.get("message", "")
                        transcript_parts.append(f"{role}: {message}")
                transcript_text = "\n".join(transcript_parts)
        
        logger.info("Parsed payload: conversation_id=%s, lead_id=%s, transcript_length=%s", 
                   conversation_id, lead_id, len(transcript_text) if transcript_text else 0)

    # Legacy form payload fallback
    if not transcript_text and isinstance(payload.get("payload"), dict):
        transcript_text = payload["payload"].get("transcript")

    if not transcript_text:
        logger.warning("Transcript webhook missing transcript: payload_keys=%s", list(payload.keys()))
        logger.info("Raw payload structure: %s", str(payload)[:500] + "..." if len(str(payload)) > 500 else str(payload))
        return {"status": "ignored"}
    
    # Extract conversation_id from payload
    data = payload.get("data", {})
    conversation_id = data.get("conversation_id") if isinstance(data, dict) else None
    
    # DEBUGGING: Check if transcript webhook has caller phone number
    caller_phone_transcript = None
    if isinstance(data, dict):
        # Check various possible phone number fields
        caller_phone_transcript = (
            data.get("caller_id") or
            data.get("from") or  
            data.get("caller_number") or
            data.get("user_phone")
        )
        logger.info("Transcript webhook data keys: %s", list(data.keys()))
        logger.info("Transcript webhook caller phone: %s", caller_phone_transcript)
        
        # Check metadata field for phone numbers
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            logger.info("Metadata keys: %s", list(metadata.keys()))
            metadata_phone = (
                metadata.get("caller_id") or
                metadata.get("from") or
                metadata.get("caller_number") or
                metadata.get("user_phone") or
                metadata.get("phone")
            )
            if metadata_phone:
                caller_phone_transcript = metadata_phone
                logger.info("Found phone in metadata: %s", metadata_phone)
        
        # Check conversation_initiation_client_data for phone numbers
        client_data = data.get("conversation_initiation_client_data", {})
        if isinstance(client_data, dict):
            logger.info("Client data keys: %s", list(client_data.keys()))
            # Check dynamic_variables within client_data
            dynamic_vars = client_data.get("dynamic_variables", {})
            if isinstance(dynamic_vars, dict):
                logger.info("Dynamic variables keys: %s", list(dynamic_vars.keys()))
                client_phone = (
                    dynamic_vars.get("customer_phone") or
                    dynamic_vars.get("caller_phone") or
                    dynamic_vars.get("phone")
                )
                if client_phone:
                    caller_phone_transcript = client_phone
                    logger.info("Found phone in client data: %s", client_phone)
                
                # Check system variables for caller_id and call_sid
                system_caller_id = dynamic_vars.get("system__caller_id")
                system_call_sid = dynamic_vars.get("system__call_sid")
                
                if system_caller_id:
                    caller_phone_transcript = system_caller_id
                    logger.info("✅ FOUND system__caller_id in dynamic variables: %s", system_caller_id)
                
                if system_call_sid:
                    logger.info("✅ FOUND system__call_sid in dynamic variables: %s", system_call_sid)
    
    # Also check top level
    if not caller_phone_transcript:
        caller_phone_transcript = (
            payload.get("caller_id") or
            payload.get("from") or
            payload.get("caller_number")
        )
        logger.info("Transcript webhook top-level caller phone: %s", caller_phone_transcript)
    
    if not conversation_id:
        logger.warning("Transcript webhook missing conversation_id: payload_keys=%s", list(payload.keys()))
        return {"status": "ignored"}

    try:
        call_service = CallService(db)
        
        # STRATEGY 1: Try direct conversation_id lookup first
        success = call_service.store_transcript(conversation_id, transcript_text)
        
        if success:
            logger.info("Transcript stored for conversation_id %s - %d chars", conversation_id, len(transcript_text))
            return {"status": "ok"}
        
        # STRATEGY 2: Use phone number to find lead, then find their latest call
        if caller_phone_transcript:
            logger.info("Using phone-based correlation: phone=%s", caller_phone_transcript)
            
            # Find the lead by phone number
            lead = call_service._find_lead_by_phone(caller_phone_transcript)
            
            if lead:
                logger.info("Found lead %s by phone %s", lead.id, caller_phone_transcript)
                
                # Find the most recent call for this lead that needs a transcript
                from app.db.models import Call
                latest_call = (
                    call_service.db.query(Call)
                    .filter(
                        Call.lead_id == lead.id,
                        Call.transcript.is_(None)  # Only calls without transcript
                    )
                    .order_by(Call.created_at.desc())
                    .first()
                )
                
                if latest_call:
                    # Update this call with the conversation_id and transcript
                    from app.schemas.call import CallUpdate
                    call_service.update_call(latest_call.id, CallUpdate(
                        conversation_id=conversation_id,
                        transcript=transcript_text,
                        status="completed"
                    ))
                    logger.info("Updated call %s for lead %s with transcript via phone correlation", 
                               latest_call.id, lead.id)
                    return {"status": "updated_by_phone"}
                else:
                    logger.warning("No call without transcript found for lead %s", lead.id)
            else:
                logger.warning("No lead found for phone %s", caller_phone_transcript)
        
        # STRATEGY 3: Try call_sid correlation as fallback
        logger.info("Trying call_sid correlation as fallback")
        
        # Extract call_sid from payload if available
        call_sid = None
        if isinstance(data, dict):
            call_sid = data.get("call_sid")
            # Also check in dynamic variables for system__call_sid
            client_data = data.get("conversation_initiation_client_data", {})
            if isinstance(client_data, dict):
                dynamic_vars = client_data.get("dynamic_variables", {})
                if isinstance(dynamic_vars, dict):
                    system_call_sid = dynamic_vars.get("system__call_sid")
                    if system_call_sid:
                        call_sid = system_call_sid
                        logger.info("Using system__call_sid from dynamic variables: %s", call_sid)
        if not call_sid:
            call_sid = payload.get("call_sid")
            
        if call_sid:
            # Find call by call_sid (stored in conversation_id field)
            call = call_service.get_call_by_conversation_id(call_sid)
            if call:
                # Update the call with proper conversation_id and transcript
                from app.schemas.call import CallUpdate
                call_service.update_call(call.id, CallUpdate(
                    conversation_id=conversation_id,  # Update to real conversation_id
                    transcript=transcript_text,
                    status="completed"
                ))
                logger.info("Updated call %s: call_sid -> conversation_id, stored transcript", call.id)
                return {"status": "updated_and_stored"}
        
        # If no call_sid found or call not found by call_sid, try time-based correlation
        # Find the most recent call without transcript
        from app.db.models import Call
        recent_call = (
            call_service.db.query(Call)
            .filter(
                Call.transcript.is_(None),
                Call.status == "in_progress"
            )
            .order_by(Call.created_at.desc())
            .first()
        )
        
        if recent_call:
            logger.info("Found recent call %s without transcript, updating", recent_call.id)
            from app.schemas.call import CallUpdate
            call_service.update_call(recent_call.id, CallUpdate(
                conversation_id=conversation_id,
                transcript=transcript_text,
                status="completed"
            ))
            logger.info("Updated call %s with transcript and conversation_id", recent_call.id)
            return {"status": "updated_recent_call"}
        
        # Last resort: Try to find call by caller phone number
        if caller_phone_transcript:
            logger.info("Trying to find call by caller phone: %s", caller_phone_transcript)
            # Find the lead by phone
            lead = call_service._find_lead_by_phone(caller_phone_transcript)
            if lead:
                # Find the most recent call for this lead without transcript
                recent_lead_calls = (
                    call_service.db.query(Call)
                    .filter(
                        Call.lead_id == lead.id,
                        Call.transcript.is_(None),
                        Call.status == "in_progress"
                    )
                    .order_by(Call.created_at.desc())
                    .limit(1)
                    .all()
                )
                
                if recent_lead_calls:
                    call = recent_lead_calls[0]
                    logger.info("Found call %s for lead %s by phone %s", call.id, lead.id, caller_phone_transcript)
                    
                    from app.schemas.call import CallUpdate
                    call_service.update_call(call.id, CallUpdate(
                        conversation_id=conversation_id,
                        transcript=transcript_text,
                        status="completed"
                    ))
                    logger.info("Updated call %s with transcript using phone correlation", call.id)
                    return {"status": "updated_by_phone"}
        
        logger.warning("No call record found by any method for conversation_id %s", conversation_id)
        return {"status": "call_not_found"}
        
    except Exception as e:
        logger.error("Failed storing transcript for conversation_id %s: %s", conversation_id, e)
        return {"status": "error", "detail": str(e)}

    return {"status": "ok"}


