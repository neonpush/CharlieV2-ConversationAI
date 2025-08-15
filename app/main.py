"""
Main application module.

This is the entry point of our FastAPI application.
It creates the app instance and sets up all configurations.
"""

from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
import logging

# STEP 1: Set up logging before anything else
# This must happen first so all other modules can use logging
setup_logging(debug=settings.debug)

# STEP 2: Create a logger for this module
# __name__ will be "app.main" - helps identify where logs come from
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Factory function that creates and configures our FastAPI application.
    
    What is a factory function?
    - A function that builds and returns an object
    - Like a car factory that produces cars
    
    Why use a factory instead of just creating the app directly?
    1. Testing - we can create multiple app instances for tests
    2. Configuration - all setup logic in one place
    3. Flexibility - easy to create different configs (dev vs prod)
    
    Returns:
        FastAPI: A configured FastAPI application instance
    
    Example usage:
        app = create_app()
        # Now 'app' is ready to handle HTTP requests
    """
    
    # Create the FastAPI instance with metadata
    # This metadata appears in the auto-generated documentation
    app = FastAPI(
        title="Lead Management API",
        description="Python rewrite of lead management system with Twilio/ElevenLabs integration",
        version="1.0.0",
        # Conditional documentation endpoints
        # In production (debug=False), we hide the docs for security
        # In development (debug=True), docs are at /docs and /redoc
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # Log that we successfully created the app
    logger.info(f"FastAPI app created - Debug mode: {settings.debug}")
    
    # STEP: Register routers (add our endpoints to the app)
    # This is like adding pages to a website
    from app.api import health, leads, calls, twiml, elevenlabs
    
    # Include the health router
    # This adds all endpoints from health.py to our app
    app.include_router(health.router)
    logger.info("Health endpoints registered at /health/*")
    
    # Include the leads router
    # This adds all lead management endpoints
    app.include_router(leads.router)
    logger.info("Lead endpoints registered at /api/leads/*")
    
    # Include the calls router
    # This adds call management endpoints
    app.include_router(calls.router)
    logger.info("Call endpoints registered at /api/calls/*")
    
    # Include the TwiML router
    # This handles Twilio webhooks and bridges to ElevenLabs
    app.include_router(twiml.router)
    logger.info("TwiML endpoints registered at /twiml/*")

    # Include ElevenLabs webhook router
    app.include_router(elevenlabs.router)
    logger.info("ElevenLabs endpoints registered at /elevenlabs/*")
    
    return app


# STEP 3: Create the actual app instance
# This runs when the module is imported
app = create_app()

# Log that the module loaded successfully
logger.info("Main application module loaded")