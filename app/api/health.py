"""
Health check endpoints.

These endpoints help monitor if our application is running correctly.
Railway and other platforms use these to know if they should send traffic to our app.
"""

from fastapi import APIRouter, Response, status
from typing import Dict, Any
import logging

# Create a router - this groups related endpoints together
# prefix="/health" means all routes in this file start with /health
# tags=["health"] groups them in the documentation
router = APIRouter(prefix="/health", tags=["health"])

# Get a logger for this module
logger = logging.getLogger(__name__)


@router.get("/healthz")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint - "Is the app alive?"
    
    What's the difference between health and readiness?
    - Health: Is the Python process running? Can it respond?
    - Readiness: Can it actually do work? (DB connected, etc.)
    
    This endpoint:
    - Always returns 200 OK if the app is running
    - Doesn't check external dependencies
    - Used by Railway to know if the container is alive
    
    URL: GET /health/healthz
    
    Returns:
        Dict with status "healthy"
        
    Example response:
        {
            "status": "healthy",
            "service": "lead-management-api"
        }
    """
    
    logger.debug("Health check called")
    
    # Simple response - if we can return this, the app is running
    return {
        "status": "healthy",
        "service": "lead-management-api"
    }


@router.get("/readyz")
async def readiness_check(response: Response) -> Dict[str, Any]:
    """
    Readiness check - "Can the app actually handle requests?"
    
    This checks if the app is ready to do real work:
    - Database is connected
    - Required services are available
    - App is fully initialized
    
    Railway uses this to know when to send traffic to our app.
    
    URL: GET /health/readyz
    
    Args:
        response: FastAPI Response object to set HTTP status code
        
    Returns:
        Dict with readiness status and individual check results
        
    Example response when ready:
        {
            "status": "ready",
            "checks": {
                "database": true,
                "config": true
            }
        }
        
    Example response when NOT ready:
        {
            "status": "not_ready",
            "checks": {
                "database": false,
                "config": true
            }
        }
    """
    
    logger.debug("Readiness check called")
    
    # Dictionary to track what's working
    checks = {
        "config": False,
        "database": False  # We'll implement DB check later
    }
    
    # Check 1: Configuration loaded successfully
    try:
        from app.core.config import settings
        # If we can access settings, config is good
        checks["config"] = bool(settings.database_url)
        logger.debug("Config check passed")
    except Exception as e:
        logger.error(f"Config check failed: {e}")
        checks["config"] = False
    
    # For now, we'll skip database check (will add in Milestone B)
    # Just mark it as "not checked yet"
    checks["database"] = None  # None means not implemented
    
    # Determine overall readiness
    # We're ready if all implemented checks pass (ignore None values)
    implemented_checks = [v for v in checks.values() if v is not None]
    is_ready = all(implemented_checks) if implemented_checks else False
    
    # Set HTTP status code
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("App not ready - some checks failed")
    else:
        logger.info("App is ready - all checks passed")
    
    return {
        "status": "ready" if is_ready else "not_ready",
        "checks": checks
    }