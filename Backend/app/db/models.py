from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone, timedelta
from db.session import Base

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)


class Admin(Base):
    """
    Admin user model - stores admin accounts created by Super Admin.
    Super Admin credentials are in .env file.
    """
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    def __repr__(self):
        return f"<Admin {self.username}>"


class Vehicle(Base):
    """
    Vehicle model - stores vehicle information and GPS device tokens.
    """
    __tablename__ = "vehicles"
    
    vehicle_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Display information
    name = Column(String(100), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    
    # Device information
    device_unique_id = Column(String(50), unique=True, nullable=False, index=True)
    access_token = Column(String(500), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    # Cached location data
    last_latitude = Column(Float, nullable=True)
    last_longitude = Column(Float, nullable=True)
    last_updated = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    schedules = relationship("Schedule", back_populates="vehicle", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Vehicle {self.name} ({self.device_unique_id})>"


class Schedule(Base):
    """
    Schedule model - stores route schedules for vehicles.
    Admin creates schedules linking vehicles to routes with timing.
    Only active schedules are visible to users.
    """
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Schedule details
    start_time = Column(DateTime(timezone=True), nullable=False)
    from_location = Column(String(255), nullable=False)
    to_location = Column(String(255), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    # Relationship
    vehicle = relationship("Vehicle", back_populates="schedules")
    
    def __repr__(self):
        return f"<Schedule {self.from_location} → {self.to_location} (Vehicle {self.vehicle_id})>"
