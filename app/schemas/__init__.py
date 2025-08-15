"""
Pydantic schemas for request/response validation.

This module exports all schemas for easy importing.
"""

from app.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadPhaseInfo,
    AgentUpdateRequest,
)
from app.schemas.viewing import (
    PropertyViewingCreate,
    PropertyViewingResponse,
)

# Export all schemas
__all__ = [
    "LeadCreate",
    "LeadUpdate", 
    "LeadResponse",
    "LeadPhaseInfo",
    "AgentUpdateRequest",
    "PropertyViewingCreate",
    "PropertyViewingResponse",
]