"""
Twilio service for making phone calls.

This service handles all Twilio-related operations:
- Making outbound calls
- Connecting to ElevenLabs agents
- Handling call status updates
"""

from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from app.core.config import settings
from app.core.logging import with_context
import logging

logger = logging.getLogger(__name__)


class TwilioService:
    """
    Service for handling Twilio phone calls.
    
    This is our phone system - it makes calls and connects
    them to our AI agent.
    """
    
    def __init__(self):
        """
        Initialize Twilio client with credentials.
        
        The credentials come from environment variables.
        """
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token
        )
        self.from_number = settings.twilio_from_number
        logger.info(f"Twilio service initialized with number: {self.from_number}")
    
    def make_call_to_lead(
        self,
        lead_id: int,
        to_number: str,
        agent_url: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make an outbound call to a lead.
        
        This call will connect to an ElevenLabs agent.
        
        Args:
            lead_id: The lead's database ID
            to_number: Phone number to call (E.164 format)
            agent_url: Optional custom agent URL
            
        Returns:
            Dict with call details (sid, status, etc.)
            
        Raises:
            TwilioException: If call fails
        """
        log = with_context(logger, lead_id=lead_id)
        log.info(f"Initiating call to {to_number}")
        
        # Instead of connecting directly to ElevenLabs,
        # we use our TwiML endpoint which can properly pass context
        
        if agent_url:
            # Use provided URL directly (for testing)
            agent_endpoint = agent_url
        else:
            # Use constant TwiML answer endpoint with lead_id as query parameter
            agent_endpoint = f"{settings.public_base_url}/twiml/answer?lead_id={lead_id}"
        
        logger.info(f"Using TwiML endpoint for lead {lead_id}")
        logger.debug(f"Agent endpoint: {agent_endpoint}")
        
        try:
            # Create the call
            # Twilio will call the to_number and connect it to our agent
            call = self.client.calls.create(
                to=to_number,
                from_=self.from_number,
                
                # The URL Twilio will connect the call to
                # Now includes lead_id as query parameter!
                url=agent_endpoint,
                
                # Method for the URL request
                method="POST",
                
                # Status callback - where Twilio sends updates
                status_callback=f"{settings.public_base_url}/api/calls/twilio/status",
                status_callback_method="POST",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                
                # Machine detection settings
                machine_detection="Enable",
                machine_detection_timeout=3000
            )
            
            log = with_context(logger, lead_id=lead_id, call_sid=call.sid)
            log.info("Call initiated successfully")
            
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "to": call.to,
                "from": getattr(call, 'from_', getattr(call, 'from', self.from_number)),
                "direction": call.direction,
                "lead_id": lead_id
            }
            
        except TwilioException as e:
            log.error(f"Failed to make call: {e}")
            return {
                "success": False,
                "error": str(e),
                "lead_id": lead_id
            }
    
    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the current status of a call.
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            Dict with call status information
        """
        try:
            call = self.client.calls(call_sid).fetch()
            
            return {
                "sid": call.sid,
                "status": call.status,
                "duration": call.duration,
                "start_time": call.start_time,
                "end_time": call.end_time,
                "to": call.to,
                "from": getattr(call, 'from_', getattr(call, 'from', 'unknown')),
                "direction": call.direction,
                "answered_by": call.answered_by  # human or machine
            }
        except TwilioException as e:
            logger.error(f"Failed to get call status: {e}")
            return {
                "error": str(e)
            }
    
    def end_call(self, call_sid: str) -> bool:
        """
        End an active call.
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            bool: True if successful
        """
        try:
            call = self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call {call_sid} ended successfully")
            return True
        except TwilioException as e:
            logger.error(f"Failed to end call: {e}")
            return False