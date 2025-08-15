"""
Call schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CallCreate(BaseModel):
    """Schema for creating a new call record."""
    lead_id: int
    conversation_id: Optional[str] = None
    system_prompt: Optional[str] = None
    status: str = "initiated"


class CallUpdate(BaseModel):
    """Schema for updating a call record."""
    conversation_id: Optional[str] = None
    transcript: Optional[str] = None
    system_prompt: Optional[str] = None
    analyzed: Optional[bool] = None
    status: Optional[str] = None
    duration_seconds: Optional[int] = None


class CallTranscriptUpdate(BaseModel):
    """Schema for updating call transcript from webhook."""
    conversation_id: str = Field(..., description="ElevenLabs conversation ID")
    transcript: str = Field(..., description="Call transcript text")


class CallResponse(BaseModel):
    """Schema for call response."""
    id: int
    lead_id: int
    conversation_id: Optional[str]
    transcript: Optional[str]
    system_prompt: Optional[str]
    analyzed: bool
    status: str
    duration_seconds: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
