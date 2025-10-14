"""Database session management."""

import os
from sqlmodel import SQLModel, create_engine, Session
from core.config import settings


# Create database directory if it doesn't exist
db_dir = os.path.dirname(settings.smoker_db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

# Create SQLite engine
engine = create_engine(
    f"sqlite:///{settings.smoker_db_path}",
    echo=False,  # Set to True for SQL debugging
    connect_args={"check_same_thread": False}
)


def create_db_and_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session


def get_session_sync():
    """Get synchronous database session."""
    return Session(engine)
