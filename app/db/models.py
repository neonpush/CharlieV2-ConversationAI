"""
Database models (tables).

These classes define the structure of our database tables.
Each class becomes a table, each attribute becomes a column.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, 
    ForeignKey, CheckConstraint, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import enum


class ContractLength(enum.Enum):
    """
    Enum for contract length values.
    
    These are the only allowed values for contract_length column.
    Using an enum ensures data integrity - can't insert invalid values.
    """
    LT_SIX_MONTHS = "LT_SIX_MONTHS"      # Less than 6 months
    SIX_MONTHS = "SIX_MONTHS"            # Exactly 6 months
    TWELVE_MONTHS = "TWELVE_MONTHS"      # Exactly 12 months
    GT_TWELVE_MONTHS = "GT_TWELVE_MONTHS" # Greater than 12 months


class CharlieOccupation(enum.Enum):
    """
    Enum for occupation types from Charlie.
    
    These are the allowed occupation categories.
    """
    EMPLOYED = "employed"
    STUDENT = "student"
    CRUISING = "cruising"


class LeadPhase(enum.Enum):
    """
    Enum for lead phases.
    
    Tracks where the lead is in our process.
    """
    CONFIRM_INFO = "CONFIRM_INFO"        # Confirming their information
    BOOKING_VIEWING = "BOOKING_VIEWING"  # Ready to book a viewing
    VIEWING_BOOKED = "VIEWING_BOOKED"    # Viewing scheduled
    COMPLETED = "COMPLETED"              # Process complete


class Lead(Base):
    """
    Lead model - represents a potential tenant.
    
    This is our main table. Each row is one lead.
    Stores all their information and tracks confirmations.
    """
    
    # Tell SQLAlchemy what table name to use
    __tablename__ = "leads"
    
    # Primary key - unique identifier for each lead
    # Integer, auto-increments (1, 2, 3, ...)
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic information fields
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    
    # Location and preferences
    postcode = Column(String(20), nullable=True)
    budget = Column(Integer, nullable=True)  # Monthly budget in pounds/dollars
    move_in_date = Column(String(100), nullable=True)  # When they want to move
    
    # Employment information
    occupation = Column(String(255), nullable=True)  # Keep as string for flexibility
    occupation_type = Column(
        SQLEnum(CharlieOccupation),
        nullable=True,
        name="occupation_type_enum"
    )
    yearly_wage = Column(Integer, nullable=True)  # Annual salary
    
    # Property details
    address_line_1 = Column(String(255), nullable=True)  # Street address
    bedroom_count = Column(Integer, nullable=True)  # Number of bedrooms
    bathroom_count = Column(Integer, nullable=True)  # Number of bathrooms
    availability_at = Column(String(100), nullable=True)  # When property is available
    property_cost = Column(Integer, nullable=True)  # Actual property price
    deposit_cost = Column(Integer, nullable=True)  # Security deposit amount
    is_bills_included = Column(Boolean, nullable=True)  # Whether bills are included in rent
    
    # Contract preference with constraint
    contract_length = Column(
        SQLEnum(ContractLength),  # Use our enum
        nullable=True,
        name="contract_length_enum"  # Name for the DB constraint
    )
    
    # Confirmation flags - track what's been verified
    # Default to False - nothing confirmed initially
    name_confirmed = Column(Boolean, default=False, nullable=False)
    budget_confirmed = Column(Boolean, default=False, nullable=False)
    move_in_date_confirmed = Column(Boolean, default=False, nullable=False)
    occupation_confirmed = Column(Boolean, default=False, nullable=False)
    yearly_wage_confirmed = Column(Boolean, default=False, nullable=False)
    contract_length_confirmed = Column(Boolean, default=False, nullable=False)
    
    # Current phase in the process
    phase = Column(
        SQLEnum(LeadPhase),
        default=LeadPhase.CONFIRM_INFO,
        nullable=False
    )
    
    # Viewing information (stored on lead for simplicity)
    viewing_date = Column(String(50), nullable=True)
    viewing_time = Column(String(50), nullable=True)
    viewing_notes = Column(Text, nullable=True)
    property_address = Column(Text, nullable=True)
    
    # Lead availability information
    # Multiple availability slots stored as JSON or text
    availability_slots = Column(Text, nullable=True)  # JSON string of availability times
    availability_notes = Column(Text, nullable=True)  # Additional notes about availability
    availability_confirmed = Column(Boolean, default=False, nullable=False)  # Has lead confirmed availability?
    landlord_approval_pending = Column(Boolean, default=False, nullable=False)  # Waiting for landlord approval?
    
    # Call transcript from ElevenLabs
    call_transcript = Column(Text, nullable=True)
    
    # Timestamps - automatically set
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # Set to current time on insert
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # Set to current time on insert
        onupdate=func.now(),       # Update to current time on update
        nullable=False
    )
    
    # Relationships
    # One lead can have many calls
    calls = relationship("Call", back_populates="lead")
    # One lead can have many viewings
    viewings = relationship("PropertyViewing", back_populates="lead")
    
    def __repr__(self):
        """
        String representation for debugging.
        
        When you print a Lead object, this is what you see.
        """
        return f"<Lead(id={self.id}, name={self.name}, phase={self.phase})>"


class Call(Base):
    """
    Call model - represents a call conversation with ElevenLabs.
    
    This table stores individual call records, linking to leads
    and tracking conversation transcripts and analysis status.
    """
    
    __tablename__ = "calls"
    
    # Primary key - unique ID for each call
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key - links to the Lead table
    lead_id = Column(
        Integer, 
        ForeignKey("leads.id"),
        nullable=False,
        index=True  # Index for faster queries by lead
    )
    
    # ElevenLabs conversation ID (unique identifier from ElevenLabs)
    conversation_id = Column(String(255), nullable=True, unique=True, index=True)
    
    # Call transcript from ElevenLabs
    transcript = Column(Text, nullable=True)
    
    # System prompt used for this call
    system_prompt = Column(Text, nullable=True)
    
    # Analysis status - whether the transcript has been analyzed
    analyzed = Column(Boolean, default=False, nullable=False)
    
    # Call status and metadata
    status = Column(
        String(50), 
        default="initiated",  # initiated, in_progress, completed, failed
        nullable=False
    )
    
    # Call duration in seconds (if available)
    duration_seconds = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationship back to Lead
    lead = relationship("Lead", back_populates="calls")
    
    def __repr__(self):
        return f"<Call(id={self.id}, lead_id={self.lead_id}, conversation_id={self.conversation_id}, status={self.status})>"


class PropertyViewing(Base):
    """
    PropertyViewing model - represents a scheduled property viewing.
    
    This table stores viewing appointments.
    Each viewing is linked to a lead (the person viewing).
    """
    
    # Table name in the database
    __tablename__ = "property_viewings"
    
    # Primary key - unique ID for each viewing
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key - links to the Lead table
    # This creates the relationship: "This viewing belongs to lead X"
    lead_id = Column(
        Integer, 
        ForeignKey("leads.id"),  # References leads.id column
        nullable=False
    )
    
    # Property details
    property_address = Column(Text, nullable=False)
    
    # Viewing schedule
    viewing_date = Column(String(50), nullable=False)
    viewing_time = Column(String(50), nullable=False)
    
    # Status of the viewing
    status = Column(
        String(50), 
        default="scheduled",  # Can be: scheduled, completed, cancelled
        nullable=False
    )
    
    # Additional notes about the viewing
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationship back to Lead
    # This allows us to access: viewing.lead to get the Lead object
    lead = relationship("Lead", back_populates="viewings")
    
    def __repr__(self):
        """
        String representation for debugging.
        """
        return f"<PropertyViewing(id={self.id}, lead_id={self.lead_id}, date={self.viewing_date})>"