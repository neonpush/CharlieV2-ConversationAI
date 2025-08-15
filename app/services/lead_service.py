"""
Lead service - Business logic for lead management.

This service handles:
- Creating and updating leads
- Phase progression logic
- Confirmation management
"""

from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.db.models import Lead, LeadPhase, ContractLength
from app.schemas.lead import (
    LeadCreate, 
    LeadUpdate, 
    LeadPhaseInfo,
    AgentUpdateRequest,
    CallTranscriptUpdate
)
import logging

logger = logging.getLogger(__name__)


class LeadService:
    """
    Service class for lead operations.
    
    This contains all the business logic for leads.
    Think of it as the "brain" that makes decisions.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service with a database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_lead(self, lead_data: LeadCreate) -> Lead:
        """
        Create a new lead in the database.
        
        Args:
            lead_data: Validated lead data from the webhook
            
        Returns:
            Lead: The created lead object
        """
        logger.info(f"Creating new lead with phone: {lead_data.phone}")
        
        # Convert Pydantic model to dict, excluding None values
        lead_dict = lead_data.model_dump(exclude_none=True)
        
        # Create the Lead object
        new_lead = Lead(
            **lead_dict,
            phase=LeadPhase.CONFIRM_INFO  # Start directly in CONFIRM_INFO
        )
        
        # Save to database
        self.db.add(new_lead)
        self.db.commit()
        self.db.refresh(new_lead)  # Get the generated ID
        
        logger.info(f"Lead created with ID: {new_lead.id}")
        return new_lead
    
    def get_lead(self, lead_id: int) -> Optional[Lead]:
        """
        Get a lead by ID.
        
        Args:
            lead_id: The lead's database ID
            
        Returns:
            Lead or None if not found
        """
        return self.db.query(Lead).filter(Lead.id == lead_id).first()
    
    def check_phase_requirements(self, lead: Lead) -> LeadPhaseInfo:
        """
        Check if a lead meets requirements to progress phases.
        
        This is the core business logic for phase progression.
        Now checks the _confirmed columns directly!
        
        Args:
            lead: The lead to check
            
        Returns:
            LeadPhaseInfo with progression details
        """
        
        # Define which confirmations we need
        # These are the _confirmed columns we check
        required_confirmations = [
            'name_confirmed',
            'budget_confirmed', 
            'move_in_date_confirmed',
            'occupation_confirmed',
            'yearly_wage_confirmed',
            # Note: contract_length_confirmed is optional
        ]
        
        # Check what's not confirmed yet
        unconfirmed_fields = []
        missing_fields = []
        
        for confirmation_field in required_confirmations:
            # Get the base field name (remove '_confirmed')
            field_name = confirmation_field.replace('_confirmed', '')
            field_value = getattr(lead, field_name, None)
            is_confirmed = getattr(lead, confirmation_field, False)
            
            if field_value is None:
                # Field doesn't have data
                missing_fields.append(field_name)
            elif not is_confirmed:
                # Field has data but not confirmed
                unconfirmed_fields.append(field_name)
        
        # Determine if we can progress
        can_progress = False
        next_phase = None
        
        if lead.phase == LeadPhase.CONFIRM_INFO:
            # Can move to BOOKING_VIEWING if ALL confirmations are done
            # This means no missing fields AND no unconfirmed fields
            all_confirmed = all(
                getattr(lead, field, False) 
                for field in required_confirmations
                if getattr(lead, field.replace('_confirmed', ''), None) is not None
            )
            if all_confirmed and not missing_fields:
                can_progress = True
                next_phase = LeadPhase.BOOKING_VIEWING
                
        elif lead.phase == LeadPhase.BOOKING_VIEWING:
            # Can move to VIEWING_BOOKED if viewing is scheduled
            if lead.viewing_date and lead.viewing_time:
                can_progress = True
                next_phase = LeadPhase.VIEWING_BOOKED
        
        return LeadPhaseInfo(
            current_phase=lead.phase,
            can_progress=can_progress,
            missing_fields=missing_fields,
            unconfirmed_fields=unconfirmed_fields,
            next_phase=next_phase
        )
    
    def update_lead_phase(self, lead: Lead) -> bool:
        """
        Try to progress a lead to the next phase.
        
        Args:
            lead: The lead to update
            
        Returns:
            bool: True if phase was updated, False otherwise
        """
        phase_info = self.check_phase_requirements(lead)
        
        if phase_info.can_progress and phase_info.next_phase:
            old_phase = lead.phase
            lead.phase = phase_info.next_phase
            self.db.commit()
            
            logger.info(f"Lead {lead.id} progressed from {old_phase.value} to {lead.phase.value}")
            return True
        
        return False
    
    def store_call_transcript(self, transcript_update: CallTranscriptUpdate) -> Lead:
        """
        Store the call transcript from ElevenLabs webhook.
        
        Simple method - just saves the transcript to the lead.
        
        Args:
            transcript_update: Contains lead_id and transcript
            
        Returns:
            Lead: The updated lead object
        """
        # Get the lead
        lead = self.get_lead(int(transcript_update.lead_id))
        if not lead:
            raise ValueError(f"Lead {transcript_update.lead_id} not found")
        
        logger.info(f"Storing transcript for lead {lead.id}")
        
        # Store the transcript
        lead.call_transcript = transcript_update.transcript
        
        # Save to database
        self.db.commit()
        self.db.refresh(lead)
        
        logger.info(f"Transcript stored for lead {lead.id} - {len(transcript_update.transcript)} characters")
        
        return lead
    
    def process_agent_update(self, update_request: AgentUpdateRequest) -> Tuple[Lead, LeadPhaseInfo]:
        """
        Process the agent's end-of-call update.
        
        This is called when the ElevenLabs agent finishes a call.
        It's a single batch update with confirmations and new data.
        
        Args:
            update_request: The update from the agent
            
        Returns:
            Tuple of (updated lead, phase info)
        """
        # Get the lead
        lead = self.get_lead(int(update_request.lead_id))
        if not lead:
            raise ValueError(f"Lead {update_request.lead_id} not found")
        
        logger.info(f"Processing agent update for lead {lead.id}")
        
        # Step 1: Apply confirmations
        # These confirm existing data
        if update_request.confirm_name and lead.name:
            lead.name_confirmed = True
            logger.debug(f"Confirmed name: {lead.name}")
            
        if update_request.confirm_budget and lead.budget:
            lead.budget_confirmed = True
            logger.debug(f"Confirmed budget: {lead.budget}")
            
        if update_request.confirm_move_in_date and lead.move_in_date:
            lead.move_in_date_confirmed = True
            logger.debug(f"Confirmed move_in_date: {lead.move_in_date}")
            
        if update_request.confirm_occupation and lead.occupation:
            lead.occupation_confirmed = True
            logger.debug(f"Confirmed occupation: {lead.occupation}")
            
        if update_request.confirm_yearly_wage and lead.yearly_wage:
            lead.yearly_wage_confirmed = True
            logger.debug(f"Confirmed yearly_wage: {lead.yearly_wage}")
            
        if update_request.confirm_contract_length and lead.contract_length:
            lead.contract_length_confirmed = True
            logger.debug(f"Confirmed contract_length: {lead.contract_length}")
        
        # Step 2: Apply new/updated data
        # New data is automatically confirmed
        if update_request.name:
            lead.name = update_request.name
            lead.name_confirmed = True
            logger.debug(f"Updated name to: {update_request.name}")
            
        if update_request.occupation:
            lead.occupation = update_request.occupation
            lead.occupation_confirmed = True
            logger.debug(f"Updated occupation to: {update_request.occupation}")
            
        if update_request.yearly_wage is not None:
            lead.yearly_wage = update_request.yearly_wage
            lead.yearly_wage_confirmed = True
            logger.debug(f"Updated yearly_wage to: {update_request.yearly_wage}")
            
        if update_request.contract_length:
            lead.contract_length = update_request.contract_length
            lead.contract_length_confirmed = True
            logger.debug(f"Updated contract_length to: {update_request.contract_length}")
        
        # Step 3: Handle viewing information
        if update_request.viewing_date:
            lead.viewing_date = update_request.viewing_date
            logger.debug(f"Set viewing_date: {update_request.viewing_date}")
            
        if update_request.viewing_time:
            lead.viewing_time = update_request.viewing_time
            logger.debug(f"Set viewing_time: {update_request.viewing_time}")
            
        if update_request.viewing_notes:
            lead.viewing_notes = update_request.viewing_notes
            logger.debug(f"Set viewing_notes: {update_request.viewing_notes}")
        
        # Step 4: Save changes
        self.db.commit()
        self.db.refresh(lead)
        
        # Step 5: Check if we can progress phase
        phase_info = self.check_phase_requirements(lead)
        if phase_info.can_progress:
            self.update_lead_phase(lead)
            # Re-check after phase update
            phase_info = self.check_phase_requirements(lead)
        
        logger.info(f"Agent update complete. Lead {lead.id} in phase {lead.phase.value}")
        
        return lead, phase_info