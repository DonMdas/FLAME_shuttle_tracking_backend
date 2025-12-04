from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from core.config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency to get database session.
    Use this in route dependencies.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    # Import models to register them with Base BEFORE creating tables
    # This ensures the model classes are defined and registered
    from .models import Vehicle, Admin, Schedule
    
    # Now create all tables
    Base.metadata.create_all(bind=engine)
    
    # Verify tables were created
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"📊 Database tables created: {tables}")
    
    if not tables:
        print("⚠️  Warning: No tables found after create_all()")
        print(f"   Base.metadata.tables: {list(Base.metadata.tables.keys())}")
        raise RuntimeError("Failed to create database tables!")
