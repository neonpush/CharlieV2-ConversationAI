"""
Prompt Storage Service for managing system prompts.

This service stores prompts temporarily and provides references
that can be passed through TwiML URLs safely.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class PromptStorage:
    """
    In-memory storage for system prompts.
    
    In production, you'd want to use Redis or a database.
    This stores prompts temporarily with automatic cleanup.
    """
    
    def __init__(self):
        """Initialize the storage."""
        # Dictionary to store prompts by ID
        self._storage: Dict[str, Dict] = {}
        
        # TTL for prompts (5 minutes should be enough for call setup)
        self.ttl_minutes = 5
        
        logger.info("PromptStorage initialized")
    
    def store_prompt(self, lead_id: int, system_prompt: str, first_message: str, variables: dict) -> str:
        """
        Store a system prompt and related data.
        
        Args:
            lead_id: The lead ID
            system_prompt: The full system prompt
            first_message: The first message to say
            variables: Additional variables for context
            
        Returns:
            A unique reference ID for this prompt
        """
        # Generate a unique ID based on content
        content = f"{lead_id}:{system_prompt}:{first_message}:{json.dumps(variables, sort_keys=True)}"
        prompt_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # Store with timestamp for cleanup
        self._storage[prompt_id] = {
            "lead_id": lead_id,
            "system_prompt": system_prompt,
            "first_message": first_message,
            "variables": variables,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=self.ttl_minutes)
        }
        
        logger.info(f"Stored prompt {prompt_id} for lead {lead_id}")
        
        # Clean up old entries
        self._cleanup_expired()
        
        return prompt_id
    
    def get_prompt(self, prompt_id: str) -> Optional[Dict]:
        """
        Retrieve a stored prompt by ID.
        
        Args:
            prompt_id: The prompt reference ID
            
        Returns:
            The stored prompt data or None if not found/expired
        """
        # Check if exists
        if prompt_id not in self._storage:
            logger.warning(f"Prompt {prompt_id} not found")
            return None
        
        # Check if expired
        prompt_data = self._storage[prompt_id]
        if datetime.now() > prompt_data["expires_at"]:
            logger.warning(f"Prompt {prompt_id} has expired")
            del self._storage[prompt_id]
            return None
        
        logger.info(f"Retrieved prompt {prompt_id} for lead {prompt_data['lead_id']}")
        return prompt_data
    
    def _cleanup_expired(self):
        """Remove expired prompts from storage."""
        now = datetime.now()
        expired_ids = [
            pid for pid, data in self._storage.items()
            if now > data["expires_at"]
        ]
        
        for pid in expired_ids:
            del self._storage[pid]
            logger.debug(f"Cleaned up expired prompt {pid}")
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired prompts")


# Global instance (singleton pattern)
_prompt_storage = None

def get_prompt_storage() -> PromptStorage:
    """
    Get the global PromptStorage instance.
    
    Returns:
        The singleton PromptStorage instance
    """
    global _prompt_storage
    if _prompt_storage is None:
        _prompt_storage = PromptStorage()
    return _prompt_storage