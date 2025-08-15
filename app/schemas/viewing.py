"""
Property viewing schemas.

These handle viewing appointment data validation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class PropertyViewingBase(BaseModel):
    """
    Base schema for property viewing.
    
    Common fields for viewing appointments.
    """
    
    property_address: str = Field(..., alias="propertyAddress")
    viewing_date: str = Field(..., alias="viewingDate")
    viewing_time: str = Field(..., alias="viewingTime")
    notes: Optional[str] = None
    
    model_config = ConfigDict(
        populate_by_name=True,
    )


class PropertyViewingCreate(PropertyViewingBase):
    """
    Schema for creating a property viewing.
    
    Used when booking a new viewing appointment.
    """
    
    # Which lead is this viewing for
    lead_id: int = Field(..., alias="leadId")
    
    # Status defaults to "scheduled"
    status: str = Field(default="scheduled")


class PropertyViewingResponse(PropertyViewingBase):
    """
    Schema for property viewing responses.
    
    What we return when querying viewings.
    """
    
    id: int
    lead_id: int = Field(alias="leadId")
    status: str
    
    # Timestamps
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,  # Allow reading from ORM objects
    )