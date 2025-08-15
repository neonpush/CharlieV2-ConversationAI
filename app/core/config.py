"""
Configuration module for the Lead Management API.

This module handles all environment variables and application settings.
It uses Pydantic to validate and parse environment variables automatically.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Settings class that manages all environment variables.
    
    How this works for a CS student:
    - Think of this as a blueprint for configuration
    - Pydantic reads environment variables automatically
    - If DATABASE_URL exists in env, it maps to database_url field
    - Missing required fields cause startup failure (fail-fast principle)
    - Optional fields have defaults or can be None
    
    Example:
        If you set DATABASE_URL="postgresql://..." in your environment,
        settings.database_url will contain that value.
    """
    
    # Database configuration
    database_url: str  # Required - app won't start without this
    
    # Webhook authentication
    webhook_secret: str  # Secret key to validate incoming webhooks
    
    # Twilio configuration for phone calls
    twilio_account_sid: str  # Your Twilio account identifier
    twilio_auth_token: str   # Secret token for Twilio API
    twilio_from_number: str  # Phone number to call from
    
    # Public URL for callbacks
    # Railway provides this automatically as RAILWAY_PUBLIC_DOMAIN
    public_base_url: str  # Where Twilio sends callbacks
    
    # ElevenLabs configuration for AI voice
    elevenlabs_api_key: str  # API key for ElevenLabs
    elevenlabs_agent_url: Optional[str] = None  # WebSocket URL (optional)
    elevenlabs_agent_id: Optional[str] = None  # Agent ID for ElevenLabs
    elevenlabs_telephony_call_url: Optional[str] = None  # Outbound call init URL
    elevenlabs_agent_phone_number_id: Optional[str] = None  # Phone number ID attached to the agent (for telephony outbound)
    
    # Additional configuration
    elevenlabs_webhook_secret: Optional[str] = None  # Webhook secret from ElevenLabs
    webhook_base_url: Optional[str] = None  # Base URL for webhooks (ngrok)
    user_phone_number: Optional[str] = None  # Test phone number
    
    # Application settings with defaults
    debug: bool = False  # Enable debug mode (more logs, show docs)
    port: int = 8000    # Port to run the server on
    auto_call_new_leads: bool = True  # Automatically call new leads when created
    
    class Config:
        """
        Pydantic configuration.
        
        What each setting does:
        - env_file: Load from .env file if it exists (for local dev)
        - case_sensitive: False means DATABASE_URL or database_url both work
        """
        env_file = ".env"
        case_sensitive = False


# Create a single instance to use throughout the app
# This pattern is called "singleton" - we only need one settings object
settings = Settings()