"""
Lead API endpoints.

This module handles all HTTP endpoints for lead management.
Think of it as the "front door" - where HTTP requests come in.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.services.lead_service import LeadService
from app.api.deps import require_webhook_secret
from app.schemas.lead import (
    LeadCreate,
    LeadResponse,
    CallTranscriptUpdate,
    LeadPhaseInfo
)
import logging
from app.core.logging import with_context
from app.core.config import settings

# Create a router - this groups related endpoints
router = APIRouter(
    prefix="/api/leads",  # All endpoints start with /api/leads
    tags=["leads"]        # For documentation grouping
)

logger = logging.getLogger(__name__)


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new lead.
    
    This is the initial webhook that creates a lead when someone
    fills out a form or calls in.
    
    Args:
        lead_data: The lead information (validated by Pydantic)
        db: Database session (injected by FastAPI)
        
    Returns:
        LeadResponse: The created lead with ID and timestamps
    """
    logger.info(f"Creating new lead: {lead_data.phone}")
    
    # Use the service to handle business logic
    service = LeadService(db)
    lead = service.create_lead(lead_data)
    
    # Auto-initiate call if enabled and phone number available
    if settings.auto_call_new_leads and lead.phone:
        logger.info(f"Auto-initiating call for new lead {lead.id}")
        try:
            # Import here to avoid circular imports
            from app.services.call_service import CallService
            from app.services.elevenlabs_service import ElevenLabsService
            from app.schemas.call import CallCreate, CallUpdate
            
            # Build dynamic variables and system prompt
            elevenlabs_service = ElevenLabsService()
            dynamic_vars = elevenlabs_service.build_dynamic_variables(lead)
            system_prompt = dynamic_vars.get("system_prompt", "")
            
            # Create call record
            call_service = CallService(db)
            call_record = call_service.create_call(CallCreate(
                lead_id=lead.id,
                system_prompt=system_prompt,
                status="initiated"
            ))
            
            # Initiate the call via ElevenLabs
            call_data = await elevenlabs_service.initiate_outbound_call_via_elevenlabs(
                lead=lead, 
                to_number=lead.phone
            )
            
            # Update call record with conversation_id
            conversation_id = call_data.get("conversation_id")
            if conversation_id:
                call_service.update_call(call_record.id, CallUpdate(
                    conversation_id=conversation_id,
                    status="in_progress"
                ))
                logger.info(f"Auto-call initiated successfully for lead {lead.id}, call {call_record.id}")
            
        except Exception as e:
            logger.error(f"Failed to auto-initiate call for lead {lead.id}: {e}")
            # Don't fail the lead creation if call fails
            # Just log the error and continue
    
    # Convert to response model
    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single lead by ID.
    
    Args:
        lead_id: The lead's database ID
        db: Database session
        
    Returns:
        LeadResponse: The lead data
        
    Raises:
        404: If lead not found
    """
    log = with_context(logger, lead_id=lead_id)
    log.debug("Fetching lead")
    
    service = LeadService(db)
    lead = service.get_lead(lead_id)
    
    if not lead:
        logger.warning(f"Lead {lead_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found"
        )
    
    return LeadResponse.model_validate(lead)


@router.post("/{lead_id}/transcript", status_code=status.HTTP_200_OK, dependencies=[Depends(require_webhook_secret)])
async def store_transcript(
    lead_id: int,
    transcript_data: CallTranscriptUpdate,
    db: Session = Depends(get_db)
):
    """
    Store call transcript from ElevenLabs webhook.
    
    This endpoint receives the transcript after a call ends.
    We just store it - processing can happen later.
    
    Args:
        lead_id: The lead's ID
        transcript_data: Contains the transcript text
        db: Database session
        
    Returns:
        Simple success message
        
    Raises:
        404: If lead not found
    """
    log = with_context(logger, lead_id=lead_id)
    log.info("Storing transcript")
    
    # Validate the lead_id matches
    if int(transcript_data.lead_id) != lead_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead ID mismatch"
        )
    
    service = LeadService(db)
    
    try:
        lead = service.store_call_transcript(transcript_data)
        return {
            "message": "Transcript stored successfully",
            "lead_id": lead.id,
            "transcript_length": len(transcript_data.transcript)
        }
    except ValueError as e:
        logger.error(f"Error storing transcript: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{lead_id}/phase", response_model=LeadPhaseInfo)
async def check_lead_phase(
    lead_id: int,
    db: Session = Depends(get_db)
):
    """
    Check lead's phase progression status.
    
    This tells you:
    - Current phase
    - Can they progress?
    - What's missing/unconfirmed?
    - What's the next phase?
    
    Args:
        lead_id: The lead's ID
        db: Database session
        
    Returns:
        LeadPhaseInfo: Detailed phase information
        
    Raises:
        404: If lead not found
    """
    logger.debug(f"Checking phase for lead {lead_id}")
    
    service = LeadService(db)
    lead = service.get_lead(lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found"
        )
    
    phase_info = service.check_phase_requirements(lead)
    return phase_info