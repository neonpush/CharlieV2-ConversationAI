"""
Logging configuration for the application.

This module sets up structured logging that works well with Railway.
Structured logging means consistent format that's easy to search/filter.
"""

import logging
import sys
from typing import Optional, Mapping, Any


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for the entire application.
    
    What is logging?
    - It's like print() but much more powerful
    - Helps us track what the app is doing
    - Essential for debugging issues in production
    
    Parameters explained:
    - debug: If True, show ALL messages (even tiny details)
             If False, only show important stuff (INFO level and above)
    
    Returns:
    - None (this function just sets things up)
    
    Example of log levels:
    - DEBUG: "Checking if user exists in database..."
    - INFO: "User successfully created"
    - WARNING: "API rate limit approaching"
    - ERROR: "Failed to connect to database"
    """
    
    # Choose how detailed our logs should be
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Create a formatter - this decides how each log line looks
    # %(asctime)s = timestamp like "2024-01-15 14:30:45"
    # %(name)s = which part of app logged this (e.g., "app.api.health")
    # %(levelname)s = DEBUG, INFO, WARNING, or ERROR
    # %(message)s = the actual message we want to log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create a handler - this decides WHERE logs go
    # StreamHandler(sys.stdout) means "print to console"
    # Railway captures console output, so we'll see logs in their dashboard
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Get the root logger (parent of all loggers in our app)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
    
    # Log that logging is set up (meta!)
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at {logging.getLevelName(log_level)} level")


def with_context(logger: logging.Logger, **context: Any) -> logging.LoggerAdapter:
    """
    Return a LoggerAdapter that injects correlation context like lead_id and call_sid.

    Usage:
        log = with_context(logging.getLogger(__name__), lead_id=123, call_sid="CA...")
        log.info("Dialing lead")
    """
    class ContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            extra = kwargs.get("extra", {})
            merged = {**context, **extra}
            kwargs["extra"] = merged
            # Prefix message with keys for easy grep
            tags = " ".join(f"{k}={v}" for k, v in merged.items() if v is not None)
            return (f"[{tags}] {msg}" if tags else msg, kwargs)

    return ContextAdapter(logger, {})