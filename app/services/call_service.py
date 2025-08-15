"""
Call service - Business logic for call management.

This service handles:
- Creating call records
- Storing transcripts
- Managing call status updates
- Call analysis tracking
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.db.models import Call, Lead
from app.schemas.call import CallCreate, CallUpdate, CallTranscriptUpdate
import logging

logger = logging.getLogger(__name__)


class CallService:
    """
    Service class for call operations.
    
    Handles all business logic related to calls and transcripts.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service with a database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_call(self, call_data: CallCreate) -> Call:
        """
        Create a new call record in the database.
        
        Args:
            call_data: Validated call data
            
        Returns:
            Call: The created call object
        """
        logger.info(f"Creating new call record for lead {call_data.lead_id}")
        
        # Convert Pydantic model to dict
        call_dict = call_data.model_dump(exclude_none=True)
        
        # Create the Call object
        new_call = Call(**call_dict)
        
        # Save to database
        self.db.add(new_call)
        self.db.commit()
        self.db.refresh(new_call)
        
        logger.info(f"Call record created with ID: {new_call.id}")
        return new_call
    
    def get_call(self, call_id: int) -> Optional[Call]:
        """
        Get a call by ID.
        
        Args:
            call_id: The call ID to look up
            
        Returns:
            Call object if found, None otherwise
        """
        return self.db.query(Call).filter(Call.id == call_id).first()
    
    def get_call_by_conversation_id(self, conversation_id: str) -> Optional[Call]:
        """
        Get a call by ElevenLabs conversation ID.
        
        Args:
            conversation_id: The ElevenLabs conversation ID
            
        Returns:
            Call object if found, None otherwise
        """
        return self.db.query(Call).filter(Call.conversation_id == conversation_id).first()
    
    def get_calls_for_lead(self, lead_id: int) -> List[Call]:
        """
        Get all calls for a specific lead.
        
        Args:
            lead_id: The lead ID
            
        Returns:
            List of Call objects, ordered by creation date (newest first)
        """
        return (
            self.db.query(Call)
            .filter(Call.lead_id == lead_id)
            .order_by(Call.created_at.desc())
            .all()
        )
    
    def update_call(self, call_id: int, call_update: CallUpdate) -> Optional[Call]:
        """
        Update a call record.
        
        Args:
            call_id: The call ID to update
            call_update: The update data
            
        Returns:
            Updated Call object if found, None otherwise
        """
        call = self.get_call(call_id)
        if not call:
            return None
        
        # Update fields that were provided
        update_data = call_update.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(call, field, value)
        
        self.db.commit()
        self.db.refresh(call)
        
        logger.info(f"Call {call_id} updated")
        return call
    
    def store_transcript(self, conversation_id: str, transcript: str) -> bool:
        """
        Store or update the call transcript from ElevenLabs webhook.
        
        Args:
            conversation_id: ElevenLabs conversation identifier
            transcript: Full conversation transcript
            
        Returns:
            bool: True if successful, False if call not found
        """
        # Find the call by conversation_id
        call = self.get_call_by_conversation_id(conversation_id)
        if not call:
            logger.warning(f"Call with conversation_id {conversation_id} not found")
            return False
        
        logger.info(f"Storing transcript for call {call.id} (conversation_id: {conversation_id})")
        
        # Update the transcript and mark as completed
        call.transcript = transcript
        call.status = "completed"
        
        # Save to database
        self.db.commit()
        self.db.refresh(call)
        
        logger.info(f"Transcript stored for call {call.id} - {len(transcript)} characters")
        
        return True
    
    def mark_call_analyzed(self, call_id: int) -> Optional[Call]:
        """
        Mark a call as analyzed.
        
        Args:
            call_id: The call ID to mark as analyzed
            
        Returns:
            Updated Call object if found, None otherwise
        """
        call = self.get_call(call_id)
        if not call:
            return None
        
        call.analyzed = True
        self.db.commit()
        self.db.refresh(call)
        
        logger.info(f"Call {call_id} marked as analyzed")
        return call
    
    def get_unanalyzed_calls(self) -> List[Call]:
        """
        Get all calls that have transcripts but haven't been analyzed yet.
        
        Returns:
            List of Call objects that need analysis
        """
        return (
            self.db.query(Call)
            .filter(
                Call.transcript.isnot(None),
                Call.analyzed == False
            )
            .order_by(Call.created_at.asc())
            .all()
        )
    

    
    def _find_lead_by_phone(self, phone_number: str) -> Optional[Lead]:
        """
        Find an existing lead by phone number.
        
        Args:
            phone_number: Phone number to search for
            
        Returns:
            Lead object if found, None otherwise
        """
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        
        # Get all leads with phone numbers
        leads = self.db.query(Lead).filter(Lead.phone.isnot(None)).all()
        
        for lead in leads:
            if lead.phone:
                lead_phone_clean = ''.join(filter(str.isdigit, lead.phone))
                # Match if last 10 digits are the same
                if (len(clean_phone) >= 10 and len(lead_phone_clean) >= 10):
                    if clean_phone[-10:] == lead_phone_clean[-10:]:
                        logger.info(f"Found existing lead {lead.id} for phone {phone_number}")
                        return lead
        
        return None
