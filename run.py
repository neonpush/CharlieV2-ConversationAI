"""
Entry point to run the FastAPI application.

This script starts the web server.
Railway will run this file to start our app.
"""

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    """
    This block only runs if we execute the file directly:
    python run.py
    
    It won't run if the file is imported.
    """
    
    # Start the web server
    # uvicorn.run() starts the ASGI server
    # Parameters:
    # - "app.main:app" = import app from app.main module
    # - host="0.0.0.0" = listen on all network interfaces
    # - port = from our settings (default 8000)
    # - reload = auto-restart when code changes (only in debug mode)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,  # Auto-reload only in development
        log_level="debug" if settings.debug else "info"
    )