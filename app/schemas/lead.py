"""
Lead schemas for validation.

These Pydantic models validate incoming data and format responses.
They convert between API format (camelCase) and database format (snake_case).
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.db.models import ContractLength, LeadPhase


class LeadBase(BaseModel):
    """
    Base schema with common lead fields.
    
    This is the parent class for other lead schemas.
    We use Field(alias="...") to handle camelCase from API.
    """
    
    # Basic information
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
    # Location and preferences
    postcode: Optional[str] = None
    budget: Optional[int] = None
    move_in_date: Optional[str] = Field(None, alias="moveInDate")
    
    # Employment information
    occupation: Optional[str] = None
    yearly_wage: Optional[int] = Field(None, alias="yearlyWage")
    
    # Contract preference - using the enum
    contract_length: Optional[ContractLength] = Field(None, alias="contractLength")
    
    # Property address for viewing
    property_address: Optional[str] = Field(None, alias="propertyAddress")
    
    # Pydantic v2 configuration
    model_config = ConfigDict(
        # Allow using field names OR aliases
        populate_by_name=True,
        # Use enum values (strings) not enum objects in JSON
        use_enum_values=True,
    )


class LeadCreate(LeadBase):
    """
    Schema for creating a new lead (webhook payload).
    
    This is what we receive from the webhook.
    All fields are optional since we gather info gradually.
    """
    
    @field_validator('postcode')
    @classmethod
    def validate_postcode(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate postcode has minimum length.
        
        Args:
            v: The postcode value
            
        Returns:
            The validated postcode
            
        Raises:
            ValueError: If postcode is too short
        """
        if v and len(v.strip()) < 1:
            raise ValueError("Postcode must not be empty")
        return v.strip() if v else None
    
    @field_validator('yearly_wage', 'budget')
    @classmethod
    def validate_positive_number(cls, v: Optional[int]) -> Optional[int]:
        """
        Ensure wage and budget are positive numbers.
        """
        if v is not None and v < 0:
            raise ValueError("Must be a positive number")
        return v


class CallTranscriptUpdate(BaseModel):
    """
    Schema for ElevenLabs webhook - just the transcript.
    
    This is much simpler - we just store what was said.
    Later we can process it however we want.
    """
    lead_id: str = Field(..., alias="leadId")
    transcript: str = Field(..., description="Full call transcript")
    
    model_config = ConfigDict(
        populate_by_name=True,  # Accept both camelCase and snake_case
    )


class AgentUpdateRequest(BaseModel):
    """
    Schema for agent's end-of-call update.
    
    This is what the ElevenLabs agent sends us at the end of a call.
    It includes confirmation flags and optional new/updated data.
    """
    
    # Lead identifier
    lead_id: str = Field(..., alias="leadId")
    
    # Confirmation flags - what the agent verified
    confirm_name: Optional[bool] = Field(False, alias="confirmName")
    confirm_budget: Optional[bool] = Field(False, alias="confirmBudget")
    confirm_move_in_date: Optional[bool] = Field(False, alias="confirmMoveInDate")
    confirm_occupation: Optional[bool] = Field(False, alias="confirmOccupation")
    confirm_yearly_wage: Optional[bool] = Field(False, alias="confirmYearlyWage")
    confirm_contract_length: Optional[bool] = Field(False, alias="confirmContractLength")
    
    # Optional updated/new data
    name: Optional[str] = None
    occupation: Optional[str] = None
    yearly_wage: Optional[int] = Field(None, alias="yearlyWage")
    contract_length: Optional[ContractLength] = Field(None, alias="contractLength")
    
    # Viewing booking fields
    viewing_date: Optional[str] = Field(None, alias="viewingDate")
    viewing_time: Optional[str] = Field(None, alias="viewingTime")
    viewing_notes: Optional[str] = Field(None, alias="viewingNotes")
    
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
    )


class LeadUpdate(LeadBase):
    """
    Schema for updating an existing lead.
    
    All fields are optional - only update what's provided.
    """
    pass  # Inherits everything from LeadBase


class LeadPhaseInfo(BaseModel):
    """
    Schema for phase progression information.
    
    This tells us if a lead can move to the next phase.
    """
    
    current_phase: LeadPhase
    can_progress: bool
    missing_fields: List[str] = Field(default_factory=list)
    unconfirmed_fields: List[str] = Field(default_factory=list)
    next_phase: Optional[LeadPhase] = None
    
    model_config = ConfigDict(
        use_enum_values=True,
    )


class LeadResponse(LeadBase):
    """
    Schema for lead responses.
    
    This is what we send back to API clients.
    Includes all lead data plus metadata.
    """
    
    # Database fields
    id: int
    phase: LeadPhase
    
    # Confirmation status fields
    name_confirmed: bool = Field(alias="nameConfirmed")
    budget_confirmed: bool = Field(alias="budgetConfirmed")
    move_in_date_confirmed: bool = Field(alias="moveInDateConfirmed")
    occupation_confirmed: bool = Field(alias="occupationConfirmed")
    yearly_wage_confirmed: bool = Field(alias="yearlyWageConfirmed")
    contract_length_confirmed: bool = Field(alias="contractLengthConfirmed")
    
    # Viewing information
    viewing_date: Optional[str] = Field(None, alias="viewingDate")
    viewing_time: Optional[str] = Field(None, alias="viewingTime")
    viewing_notes: Optional[str] = Field(None, alias="viewingNotes")
    
    # Timestamps
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    # Phase information
    phase_info: Optional[LeadPhaseInfo] = Field(None, alias="phaseInfo")
    
    model_config = ConfigDict(
        # Allow field names or aliases
        populate_by_name=True,
        # Use enum values in JSON
        use_enum_values=True,
        # Allow ORM mode (read from database objects)
        from_attributes=True,
    )