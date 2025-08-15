"""
Database connection and session management.

This module sets up SQLAlchemy to connect to our database.
It handles the connection pool and provides session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# STEP 1: Create the database engine
# The engine is like a factory that creates database connections
# It manages a pool of connections for efficiency
engine = create_engine(
    settings.database_url,
    # Connection pool settings:
    # pool_pre_ping=True means test connections before using them
    # This helps recover from database restarts
    pool_pre_ping=True,
    # echo=True would print all SQL statements (useful for debugging)
    echo=settings.debug,
)

# STEP 2: Create a SessionLocal class
# This is a factory for creating database sessions
# A session is like a shopping cart - you add changes to it, then commit all at once
SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-save changes (we control when to commit)
    autoflush=False,   # Don't auto-send changes to DB (we control this too)
    bind=engine,       # Connect sessions to our engine
)

# STEP 3: Create a base class for our models
# All our database models will inherit from this
# Think of it as the parent class for all tables
Base = declarative_base()


def get_db() -> Session:
    """
    Dependency function that provides a database session.
    
    This is a generator function (uses yield).
    FastAPI will:
    1. Call this function
    2. Get the database session
    3. Pass it to your endpoint
    4. After the endpoint runs, close the session
    
    This ensures:
    - Each request gets its own session
    - Sessions are always closed properly
    - No connection leaks
    
    Yields:
        Session: A database session for the request
    """
    db = SessionLocal()
    try:
        logger.debug("Database session created")
        yield db  # Provide the session to the endpoint
    finally:
        db.close()  # Always close the session when done
        logger.debug("Database session closed")