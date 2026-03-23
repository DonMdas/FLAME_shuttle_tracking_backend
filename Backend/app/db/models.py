from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Time, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone, timedelta
from .session import Base
from app.core.constants import RouteType

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)


class RouteTypeModel(Base):
    """
    RouteType lookup table - stores allowed route/schedule types.
    This ensures referential integrity and provides a single source of truth.
    """
    __tablename__ = "route_types"
    
    type_name = Column(String(20), primary_key=True, nullable=False)
    description = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    
    def __repr__(self):
        return f"<RouteType {self.type_name}>"


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
    Vehicle model - stores vehicle information synced from EERA API.
    Vehicles are automatically synced from the API, not manually added.
    """
    __tablename__ = "vehicles"
    
    vehicle_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Display information
    name = Column(String(100), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    
    # Device information (from EERA API)
    device_unique_id = Column(String(50), unique=True, nullable=False, index=True)
    company_name = Column(String(100), nullable=True)
    
    # Status (admin controlled)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    # Cached location data (from API)
    last_latitude = Column(Float, nullable=True)
    last_longitude = Column(Float, nullable=True)
    last_speed = Column(Float, nullable=True)  # Speed in km/h from API
    last_fix_time = Column(DateTime(timezone=True), nullable=True)  # When GPS location was recorded
    last_server_time = Column(DateTime(timezone=True), nullable=True)  # When server received data
    last_updated = Column(DateTime(timezone=True), nullable=True)  # When we last fetched from API
    
    # Relationship
    schedules = relationship("Schedule", back_populates="vehicle", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Vehicle {self.name} ({self.device_unique_id})>"


class Station(Base):
    """
    Station model - stores fixed station/stop coordinates.
    Stations are predefined locations where shuttles stop.
    """
    __tablename__ = "stations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)  # Display name
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    # Relationships
    route_stops = relationship("RouteStop", back_populates="station", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Station {self.id}: {self.name}>"


class Route(Base):
    """
    Route model - stores route definitions (paths between locations).
    Routes define the path a shuttle takes from one location to another.
    """
    __tablename__ = "routes"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)  # Display name "Campus → FC Road"
    from_location = Column(String(100), nullable=False)
    to_location = Column(String(100), nullable=False)
    route_type = Column(String(20), ForeignKey("route_types.type_name"), nullable=False, default="student", index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    __table_args__ = (
        CheckConstraint(
            route_type.in_(['student', 'staff', 'internal']),
            name='check_route_type'
        ),
    )
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    # Relationships
    route_stops = relationship("RouteStop", back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.stop_order")
    schedules = relationship("Schedule", back_populates="route")
    
    def __repr__(self):
        return f"<Route {self.id}: {self.name}>"


class RouteStop(Base):
    """
    RouteStop model - junction table linking routes to stations with ordering.
    Defines the sequence of stops for each route.
    """
    __tablename__ = "route_stops"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    station_id = Column(Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_order = Column(Integer, nullable=False)  # Position in sequence (0-based)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    
    # Relationships
    route = relationship("Route", back_populates="route_stops")
    station = relationship("Station", back_populates="route_stops")
    
    def __repr__(self):
        return f"<RouteStop {self.route_id} - {self.station_id} (order: {self.stop_order})>"


class Schedule(Base):
    """
    Schedule model - stores route schedules for vehicles.
    Admin creates schedules linking vehicles to routes with timing.
    Supports both one-time and recurring schedules.
    Only one active schedule allowed per vehicle at a time.
    """
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Schedule details
    start_time = Column(Time, nullable=False)  # Time only (e.g., 08:00:00)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False, index=True)
    schedule_type = Column(String(50), ForeignKey("route_types.type_name"), default="student", nullable=False, index=True)
    
    # Recurring schedule support
    is_recurring = Column(Boolean, default=False, nullable=False, index=True)
    date = Column(Date, nullable=True)  # For non-recurring: the specific date the schedule runs on. Not used for recurring schedules.
    
    __table_args__ = (
        CheckConstraint(
            schedule_type.in_(['student', 'staff', 'internal']),
            name='check_schedule_type'
        ),
    )
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    # Relationships
    vehicle = relationship("Vehicle", back_populates="schedules")
    route = relationship("Route", back_populates="schedules")
    days = relationship("ScheduleDay", back_populates="schedule", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Schedule {self.route_id} @ {self.start_time} (Vehicle {self.vehicle_id}, Recurring: {self.is_recurring})>"


class ScheduleDay(Base):
    """
    ScheduleDay model - stores days of week for recurring schedules.
    Links recurring schedules to specific days (monday, tuesday, etc.).
    Only populated for recurring schedules (is_recurring=True).
    """
    __tablename__ = "schedule_days"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    schedule_id = Column(
        Integer,
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    day_of_week = Column(String(10), nullable=False, index=True)  # monday, tuesday, wednesday, etc.
    
    __table_args__ = (
        CheckConstraint(
            day_of_week.in_(['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']),
            name='check_day_of_week'
        ),
    )
    
    # Relationship
    schedule = relationship("Schedule", back_populates="days")
    
    def __repr__(self):
        return f"<ScheduleDay {self.schedule_id} on {self.day_of_week}>"


class User(Base):
    """
    User model - stores student and staff user accounts.
    Supports multiple authentication methods: password, Google OAuth, or hybrid.
    
    Auth Provider States:
    - 'password': Email + password authentication only
    - 'google': Google OAuth only
    - 'google+password': Both methods enabled (hybrid account)
    
    Role can be NULL only during Google onboarding process.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # NULL for Google-only users
    role = Column(String(20), nullable=True, index=True)  # "student" or "staff" - NULL during onboarding
    
    # Authentication provider tracking
    auth_provider = Column(String(20), nullable=False, index=True)  # "password", "google", "google+password"
    
    # Email verification
    is_email_verified = Column(Boolean, default=False, nullable=False)
    otp = Column(String(6), nullable=True)  # Current OTP for verification
    otp_created_at = Column(DateTime(timezone=True), nullable=True)  # OTP expiry tracking
    
    # OAuth
    google_id = Column(String(100), unique=True, nullable=True, index=True)  # Google OAuth ID
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    # Relationships
    feedbacks = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email} ({self.role or 'pending'}) - {self.auth_provider}>"


class Feedback(Base):
    """
    Feedback model - stores user feedback about rides, routes, and services.
    Users can submit feedback which is reviewed by admins.
    """
    __tablename__ = "feedbacks"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # User information
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_anonymous = Column(Boolean, default=False, nullable=False)
    
    # Feedback classification
    feedback_type = Column(String(50), nullable=False, index=True)  # ride, route, general, quick_rating
    category = Column(String(50), nullable=True, index=True)  # timing, cleanliness, driver, route, app, facility, other
    
    # Related entities (nullable - not all feedback is about specific vehicle/route)
    vehicle_id = Column(Integer, ForeignKey("vehicles.vehicle_id", ondelete="SET NULL"), nullable=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="SET NULL"), nullable=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Feedback content
    rating = Column(Integer, nullable=True)  # 1-5 stars
    title = Column(String(255), nullable=True)
    description = Column(String(2000), nullable=True)
    issues = Column(String(1000), nullable=True)  # JSON string array: ["delay", "cleanliness", etc.]
    
    # Admin management
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, in_review, resolved, closed, dismissed
    priority = Column(String(20), default="medium", nullable=False)  # low, medium, high, critical
    admin_response = Column(String(2000), nullable=True)  # Response visible to user
    admin_notes = Column(String(2000), nullable=True)  # Internal notes, not visible to user
    resolved_by = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=get_ist_now)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now)
    
    # Relationships
    user = relationship("User", back_populates="feedbacks")
    vehicle = relationship("Vehicle")
    route = relationship("Route")
    schedule = relationship("Schedule")
    admin = relationship("Admin")
    
    def __repr__(self):
        return f"<Feedback {self.id} - {self.feedback_type} by User {self.user_id} ({self.status})>"
