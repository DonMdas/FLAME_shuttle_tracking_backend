from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from .models import Vehicle, Admin, Schedule, ScheduleDay, User, Station, Route, RouteStop, Feedback
from schemas.vehicle import VehicleCreate, VehicleUpdate, ScheduleCreate, ScheduleUpdate
from app.core.route_config import ROUTE_DEFINITIONS, STATIONS, haversine_distance
from app.core.config import settings
import json

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)


# ============ Admin CRUD Operations ============

def get_admin_by_username(db: Session, username: str) -> Optional[Admin]:
    """Get admin by username"""
    return db.query(Admin).filter(Admin.username == username).first()


def get_admin(db: Session, admin_id: int) -> Optional[Admin]:
    """Get admin by ID"""
    return db.query(Admin).filter(Admin.id == admin_id).first()


def get_admins(db: Session, skip: int = 0, limit: int = 100) -> List[Admin]:
    """Get all admins"""
    return db.query(Admin).offset(skip).limit(limit).all()


def create_admin(db: Session, username: str, hashed_password: str) -> Admin:
    """Create a new admin"""
    db_admin = Admin(
        username=username,
        hashed_password=hashed_password,
        is_active=True
    )
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin


def update_admin_status(db: Session, admin_id: int, is_active: bool) -> Optional[Admin]:
    """Activate or deactivate an admin"""
    db_admin = get_admin(db, admin_id)
    if not db_admin:
        return None
    
    db_admin.is_active = is_active
    db.commit()
    db.refresh(db_admin)
    return db_admin


def delete_admin(db: Session, admin_id: int) -> bool:
    """Delete an admin"""
    db_admin = get_admin(db, admin_id)
    if not db_admin:
        return False
    
    db.delete(db_admin)
    db.commit()
    return True


# ============ Vehicle CRUD Operations ============

def get_vehicle(db: Session, vehicle_id: int) -> Optional[Vehicle]:
    """Get a single vehicle by ID"""
    return db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()


def get_vehicle_by_device_id(db: Session, device_unique_id: str) -> Optional[Vehicle]:
    """Get a vehicle by its device unique ID (IMEI)"""
    return db.query(Vehicle).filter(Vehicle.device_unique_id == device_unique_id).first()


def get_vehicles(db: Session, skip: int = 0, limit: int = 100) -> List[Vehicle]:
    """Get all vehicles (admin view)"""
    return db.query(Vehicle).offset(skip).limit(limit).all()


def get_active_vehicles(db: Session) -> List[Vehicle]:
    """Get all active vehicles"""
    return db.query(Vehicle).filter(Vehicle.is_active == True).all()


def get_vehicles_with_active_schedules(db: Session) -> List[Vehicle]:
    """Get all vehicles that have active schedules (client view)"""
    return db.query(Vehicle).join(Schedule).filter(
        Vehicle.is_active == True,
        Schedule.is_active == True
    ).distinct().all()


def sync_vehicle_from_api(db: Session, api_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync a single vehicle from EERA API data.
    Creates new vehicle if does not exist, updates if exists.
    
    Args:
        db: Database session
        api_data: Vehicle data from EERA API
        
    Returns:
        Dict with keys: vehicle, created (bool), updated (bool)
    """
    device_id = api_data.get("deviceUniqueId")
    if not device_id:
        return {"vehicle": None, "created": False, "updated": False, "error": "No device ID"}
    
    # Check if vehicle exists
    existing = get_vehicle_by_device_id(db, device_id)
    
    # Parse timestamps
    fix_time = None
    server_time = None
    
    if api_data.get("fixTime"):
        try:
            fix_time = datetime.fromisoformat(api_data["fixTime"].replace('Z', '+00:00'))
        except:
            pass
    
    if api_data.get("serverTime"):
        try:
            server_time = datetime.fromisoformat(api_data["serverTime"].replace('Z', '+00:00'))
        except:
            pass
    
    if existing:
        # Update existing vehicle (only metadata, not location - location is fetched live)
        existing.name = api_data.get("name", existing.name)
        existing.company_name = api_data.get("companyName")
        existing.last_updated = get_ist_now()
        
        # Optionally update cached location if provided
        if api_data.get("latitude") is not None:
            existing.last_latitude = api_data.get("latitude")
            existing.last_longitude = api_data.get("longitude")
            existing.last_speed = api_data.get("speed")
            existing.last_fix_time = fix_time
            existing.last_server_time = server_time
        
        db.commit()
        db.refresh(existing)
        
        # Check if vehicle reached destination and auto-deactivate schedule (only if schedule is active)
        if existing.last_latitude and existing.last_longitude:
            check_and_deactivate_schedule(
                db,
                existing.vehicle_id,
                existing.last_latitude,
                existing.last_longitude
            )
        
        return {"vehicle": existing, "created": False, "updated": True}
    else:
        # Create new vehicle
        new_vehicle = Vehicle(
            name=api_data.get("name", device_id),
            device_unique_id=device_id,
            company_name=api_data.get("companyName"),
            is_active=True,  # Default to active, admin can change later
            last_latitude=api_data.get("latitude"),
            last_longitude=api_data.get("longitude"),
            last_speed=api_data.get("speed"),
            last_fix_time=fix_time,
            last_server_time=server_time,
            last_updated=get_ist_now()
        )
        
        db.add(new_vehicle)
        db.commit()
        db.refresh(new_vehicle)
        
        return {"vehicle": new_vehicle, "created": True, "updated": False}


def update_vehicle_from_live_data(
    db: Session,
    vehicle_id: int,
    api_data: Dict[str, Any]
) -> Optional[Vehicle]:
    """
    Update vehicle with live data from API (location, speed, etc.)
    This is called when frontend requests live data.
    
    Args:
        db: Database session
        vehicle_id: Vehicle ID
        api_data: Live data from EERA API
        
    Returns:
        Updated vehicle or None
    """
    db_vehicle = get_vehicle(db, vehicle_id)
    if not db_vehicle:
        return None
    
    # Parse timestamps
    fix_time = None
    server_time = None
    
    if api_data.get("fixTime"):
        try:
            fix_time = datetime.fromisoformat(api_data["fixTime"].replace('Z', '+00:00'))
        except:
            pass
    
    if api_data.get("serverTime"):
        try:
            server_time = datetime.fromisoformat(api_data["serverTime"].replace('Z', '+00:00'))
        except:
            pass
    
    # Update cached data
    db_vehicle.last_latitude = api_data.get("latitude")
    db_vehicle.last_longitude = api_data.get("longitude")
    db_vehicle.last_speed = api_data.get("speed")
    db_vehicle.last_fix_time = fix_time
    db_vehicle.last_server_time = server_time
    db_vehicle.last_updated = get_ist_now()
    
    db.commit()
    db.refresh(db_vehicle)
    
    # Check if vehicle reached destination and auto-deactivate schedule
    if db_vehicle.last_latitude and db_vehicle.last_longitude:
        check_and_deactivate_schedule(
            db,
            vehicle_id,
            db_vehicle.last_latitude,
            db_vehicle.last_longitude
        )
    
    return db_vehicle


def create_vehicle(db: Session, vehicle: VehicleCreate) -> Vehicle:
    """
    Create a new vehicle (deprecated - vehicles are now synced from API)
    Kept for backward compatibility if needed.
    """
    db_vehicle = Vehicle(
        name=vehicle.name,
        label=vehicle.label,
        device_unique_id=vehicle.device_unique_id,
        company_name=vehicle.company_name if hasattr(vehicle, 'company_name') else None,
        is_active=vehicle.is_active
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


def update_vehicle(db: Session, vehicle_id: int, vehicle_update: VehicleUpdate) -> Optional[Vehicle]:
    """Update a vehicle"""
    db_vehicle = get_vehicle(db, vehicle_id)
    if not db_vehicle:
        return None
    
    update_data = vehicle_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_vehicle, field, value)
    
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


def delete_vehicle(db: Session, vehicle_id: int) -> bool:
    """Delete a vehicle"""
    db_vehicle = get_vehicle(db, vehicle_id)
    if not db_vehicle:
        return False
    
    db.delete(db_vehicle)
    db.commit()
    return True


def update_vehicle_location(
    db: Session,
    vehicle_id: int,
    latitude: float,
    longitude: float
) -> Optional[Vehicle]:
    """
    Update cached location for a vehicle (deprecated)
    Use update_vehicle_from_live_data instead.
    """
    db_vehicle = get_vehicle(db, vehicle_id)
    if not db_vehicle:
        return None
    
    db_vehicle.last_latitude = latitude
    db_vehicle.last_longitude = longitude
    db_vehicle.last_updated = get_ist_now()
    
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


# ============ Schedule CRUD Operations ============

def get_schedule(db: Session, schedule_id: int) -> Optional[Schedule]:
    """Get a single schedule by ID with vehicle details and recurring days"""
    return db.query(Schedule).options(
        joinedload(Schedule.vehicle),
        joinedload(Schedule.days)
    ).filter(Schedule.id == schedule_id).first()


def get_schedules(db: Session, skip: int = 0, limit: int = 100, schedule_type: Optional[str] = None) -> List[Schedule]:
    """Get all schedules with vehicle details and recurring days (admin view)"""
    query = db.query(Schedule).options(
        joinedload(Schedule.vehicle),
        joinedload(Schedule.days)
    )
    if schedule_type:
        query = query.filter(Schedule.schedule_type == schedule_type)
    return query.offset(skip).limit(limit).all()


def get_schedules_by_vehicle(db: Session, vehicle_id: int, schedule_type: Optional[str] = None) -> List[Schedule]:
    """Get all schedules for a specific vehicle with vehicle details and recurring days"""
    query = db.query(Schedule).options(
        joinedload(Schedule.vehicle),
        joinedload(Schedule.days)
    ).filter(Schedule.vehicle_id == vehicle_id)
    if schedule_type:
        query = query.filter(Schedule.schedule_type == schedule_type)
    return query.all()


def get_active_schedules(db: Session, schedule_type: Optional[str] = None) -> List[Schedule]:
    """Get all active schedules with vehicle details and recurring days (client view)"""
    query = db.query(Schedule).options(
        joinedload(Schedule.vehicle),
        joinedload(Schedule.days)
    ).filter(Schedule.is_active == True)
    if schedule_type:
        query = query.filter(Schedule.schedule_type == schedule_type)
    return query.all()


def create_schedule(db: Session, schedule: ScheduleCreate) -> Schedule:
    """
    Create a new schedule with optional recurring days.
    Only one active schedule allowed per vehicle at a time.
    """
    # If creating an active schedule, deactivate any existing active schedules for this vehicle
    if schedule.is_active:
        existing_active = db.query(Schedule).filter(
            Schedule.vehicle_id == schedule.vehicle_id,
            Schedule.is_active == True
        ).all()
        
        if existing_active:
            # Deactivate all existing active schedules for this vehicle
            for existing in existing_active:
                existing.is_active = False
    
    # Create the schedule
    db_schedule = Schedule(
        vehicle_id=schedule.vehicle_id,
        start_time=schedule.start_time,
        route_id=schedule.route_id,
        schedule_type=schedule.schedule_type,
        is_active=schedule.is_active,
        is_recurring=schedule.is_recurring,
        date=schedule.date
    )
    db.add(db_schedule)
    db.flush()  # Flush to get the schedule ID
    
    # Add recurring days if applicable
    if schedule.is_recurring and schedule.repeat_days:
        for day in schedule.repeat_days:
            db_day = ScheduleDay(
                schedule_id=db_schedule.id,
                day_of_week=day.lower()
            )
            db.add(db_day)
    
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


def update_schedule(db: Session, schedule_id: int, schedule_update: ScheduleUpdate) -> Optional[Schedule]:
    """
    Update a schedule and its recurring days.
    Only one active schedule allowed per vehicle at a time.
    """
    db_schedule = get_schedule(db, schedule_id)
    if not db_schedule:
        return None
    
    update_data = schedule_update.dict(exclude_unset=True)
    
    # If updating to active, deactivate any other active schedules for this vehicle
    if update_data.get('is_active') == True:
        existing_active = db.query(Schedule).filter(
            Schedule.vehicle_id == db_schedule.vehicle_id,
            Schedule.is_active == True,
            Schedule.id != schedule_id  # Exclude current schedule
        ).all()
        
        if existing_active:
            # Deactivate all other active schedules for this vehicle
            for existing in existing_active:
                existing.is_active = False
    
    # Handle repeat_days update separately
    repeat_days = update_data.pop('repeat_days', None)
    
    # Update schedule fields
    for field, value in update_data.items():
        setattr(db_schedule, field, value)
    
    # Update recurring days if provided
    if repeat_days is not None:
        # Delete existing days
        db.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == schedule_id
        ).delete()
        
        # Add new days
        for day in repeat_days:
            db_day = ScheduleDay(
                schedule_id=schedule_id,
                day_of_week=day.lower()
            )
            db.add(db_day)
    
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


def delete_schedule(db: Session, schedule_id: int) -> bool:
    """Delete a schedule (cascade deletes schedule_days automatically)"""    
    db_schedule = get_schedule(db, schedule_id)
    if not db_schedule:
        return False
    
    db.delete(db_schedule)
    db.commit()
    return True


def get_schedules_for_day(db: Session, day_of_week: str, schedule_type: Optional[str] = None) -> List[Schedule]:
    # Get all active schedules for a specific day of the week
    # Includes both recurring schedules for that day and non-recurring schedules
    from datetime import date as date_type
    
    # Normalize day name
    day_of_week = day_of_week.lower()
    today = date_type.today()
    
    # Query for recurring schedules with this day
    recurring_query = (
        db.query(Schedule)
        .join(ScheduleDay)
        .options(
            joinedload(Schedule.vehicle),
            joinedload(Schedule.days)
        )
        .filter(
            Schedule.is_active == True,
            Schedule.is_recurring == True,
            ScheduleDay.day_of_week == day_of_week
        )
    )
    
    # No date range filter needed for recurring schedules — they run indefinitely on specified days
    
    # Apply schedule type filter if provided
    if schedule_type:
        recurring_query = recurring_query.filter(Schedule.schedule_type == schedule_type)
    
    recurring_schedules = recurring_query.all()
    
    # Query for non-recurring schedules with date = today
    non_recurring_query = (
        db.query(Schedule)
        .options(
            joinedload(Schedule.vehicle),
            joinedload(Schedule.days)
        )
        .filter(
            Schedule.is_active == True,
            Schedule.is_recurring == False,
            Schedule.date == today
        )
    )
    
    if schedule_type:
        non_recurring_query = non_recurring_query.filter(Schedule.schedule_type == schedule_type)
    
    non_recurring_schedules = non_recurring_query.all()
    
    # Combine and return
    return recurring_schedules + non_recurring_schedules


def get_schedules_for_today(db: Session, schedule_type: Optional[str] = None) -> List[Schedule]:
    # Get all active schedules for today
    # Convenience function that determines current day and calls get_schedules_for_day
    from datetime import datetime
    
    # Get current day name
    today_name = datetime.now().strftime('%A').lower()  # 'monday', 'tuesday', etc.
    
    return get_schedules_for_day(db, today_name, schedule_type)


def check_and_deactivate_schedule(
    db: Session,
    vehicle_id: int,
    current_lat: float,
    current_lon: float,
    distance_threshold_meters: Optional[float] = None
) -> Optional[Schedule]:
    """
    Check if vehicle has reached its destination and deactivate the schedule if so.
    
    Args:
        db: Database session
        vehicle_id: Vehicle ID
        current_lat: Current latitude
        current_lon: Current longitude
        distance_threshold_meters: Distance threshold to consider reached (uses DESTINATION_PROXIMITY_THRESHOLD from env if not provided)
        
    Returns:
        Deactivated schedule if any, None otherwise
    """
    # Use env config if not provided
    if distance_threshold_meters is None:
        distance_threshold_meters = settings.DESTINATION_PROXIMITY_THRESHOLD
    # Get active schedule for this vehicle
    active_schedule = db.query(Schedule).filter(
        Schedule.vehicle_id == vehicle_id,
        Schedule.is_active == True
    ).first()
    
    if not active_schedule:
        return None
    
    # Get route definition
    route_def = ROUTE_DEFINITIONS.get(active_schedule.route_id)
    if not route_def:
        return None
    
    # Get final destination (last stop in route)
    stop_ids = route_def["stops"]
    if not stop_ids:
        return None
    
    final_stop_id = stop_ids[-1]
    final_station = STATIONS.get(final_stop_id)
    
    if not final_station:
        return None
    
    # Calculate distance to destination
    distance = haversine_distance(
        current_lat,
        current_lon,
        final_station.lat,
        final_station.lon
    )
    
    # If within threshold, deactivate schedule
    if distance <= distance_threshold_meters:
        active_schedule.is_active = False
        db.commit()
        db.refresh(active_schedule)
        return active_schedule
    
    return None


# ============ User CRUD Operations ============

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_google_id(db: Session, google_id: str) -> Optional[User]:
    """Get user by Google OAuth ID"""
    return db.query(User).filter(User.google_id == google_id).first()


def get_user(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 1000, role: Optional[str] = None) -> List[User]:
    """Get all users with optional role filter"""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.offset(skip).limit(limit).all()


def create_user(
    db: Session, 
    email: str, 
    hashed_password: Optional[str], 
    role: Optional[str], 
    auth_provider: str,
    google_id: Optional[str] = None,
    is_email_verified: bool = False
) -> User:
    """
    Create a new user with specified authentication provider.
    
    Args:
        db: Database session
        email: User email
        hashed_password: Hashed password (None for Google-only users)
        role: User role (None for Google users during onboarding)
        auth_provider: 'password', 'google', or 'google+password'
        google_id: Google OAuth ID (for Google users)
        is_email_verified: Whether email is verified (True for Google users)
    """
    db_user = User(
        email=email.lower(),
        hashed_password=hashed_password,
        role=role.lower() if role else None,
        auth_provider=auth_provider,
        google_id=google_id,
        is_email_verified=is_email_verified,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_otp(db: Session, user_id: int, otp: str) -> Optional[User]:
    """Update user OTP for verification"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    db_user.otp = otp
    db_user.otp_created_at = get_ist_now()
    db.commit()
    db.refresh(db_user)
    return db_user


def verify_user(db: Session, user_id: int) -> Optional[User]:
    """Mark user as verified and clear OTP"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    db_user.is_email_verified = True
    db_user.otp = None
    db_user.otp_created_at = None
    db.commit()
    db.refresh(db_user)
    return db_user


def set_user_role(db: Session, user_id: int, role: str) -> Optional[User]:
    """
    Set user role (one-time operation during onboarding).
    Only works if role is currently NULL.
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    if db_user.role is not None:
        return None  # Role already set, cannot change via this method
    
    db_user.role = role.lower()
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_role(db: Session, user_id: int, role: str) -> Optional[User]:
    """Update user role (admin only - can change existing roles)"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    db_user.role = role.lower()
    db.commit()
    db.refresh(db_user)
    return db_user


def set_user_password(db: Session, user_id: int, hashed_password: str) -> Optional[User]:
    """
    Set password for a user (Google users enabling password login).
    Updates auth_provider from 'google' to 'google+password'.
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    if db_user.hashed_password is not None:
        return None  # Password already exists
    
    db_user.hashed_password = hashed_password
    
    # Update auth provider
    if db_user.auth_provider == "google":
        db_user.auth_provider = "google+password"
    
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_password(db: Session, user_id: int, hashed_password: str) -> Optional[User]:
    """
    Update existing password (for password reset or change password).
    User must already have a password set.
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    if db_user.hashed_password is None:
        return None  # No password to update
    
    db_user.hashed_password = hashed_password
    db.commit()
    db.refresh(db_user)
    return db_user


def link_google_account(db: Session, user_id: int, google_id: str) -> Optional[User]:
    """
    Link Google account to existing password-based user.
    Updates auth_provider from 'password' to 'google+password'.
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    if db_user.google_id is not None:
        return None  # Google already linked
    
    db_user.google_id = google_id
    db_user.is_email_verified = True  # Google accounts are email-verified
    
    # Update auth provider
    if db_user.auth_provider == "password":
        db_user.auth_provider = "google+password"
    
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_status(db: Session, user_id: int, is_active: bool) -> Optional[User]:
    """Activate or deactivate a user"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    db_user.is_active = is_active
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user"""
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    
    db.delete(db_user)
    db.commit()
    return True


# ============ Station CRUD Operations ============

def get_station(db: Session, station_id: int) -> Optional[Station]:
    """Get station by ID"""
    return db.query(Station).filter(Station.id == station_id).first()


def get_all_stations(db: Session, active_only: bool = True) -> List[Station]:
    """Get all stations, optionally filtered by active status"""
    query = db.query(Station)
    if active_only:
        query = query.filter(Station.is_active == True)
    return query.order_by(Station.name).all()


def get_stations_by_ids(db: Session, station_ids: List[int]) -> List[Station]:
    """Get multiple stations by their IDs"""
    return db.query(Station).filter(Station.id.in_(station_ids)).all()


def create_station(db: Session, name: str, latitude: float, longitude: float) -> Station:
    """Create a new station"""
    db_station = Station(
        name=name,
        latitude=latitude,
        longitude=longitude,
        is_active=True
    )
    db.add(db_station)
    db.commit()
    db.refresh(db_station)
    return db_station


def update_station(db: Session, station_id: int, name: Optional[str] = None, 
                   latitude: Optional[float] = None, longitude: Optional[float] = None,
                   is_active: Optional[bool] = None) -> Optional[Station]:
    """Update station details"""
    db_station = get_station(db, station_id)
    if not db_station:
        return None
    
    if name is not None:
        db_station.name = name
    if latitude is not None:
        db_station.latitude = latitude
    if longitude is not None:
        db_station.longitude = longitude
    if is_active is not None:
        db_station.is_active = is_active
    
    db.commit()
    db.refresh(db_station)
    return db_station


def delete_station(db: Session, station_id: int) -> bool:
    """Delete a station (will fail if referenced by route_stops due to FK constraint)"""
    db_station = get_station(db, station_id)
    if not db_station:
        return False
    
    db.delete(db_station)
    db.commit()
    return True


# ============ Route CRUD Operations ============

def get_route(db: Session, route_id: int) -> Optional[Route]:
    """Get route by route_id with stops loaded"""
    return db.query(Route).filter(Route.id == route_id).first()


def get_route_with_stops(db: Session, route_id: int) -> Optional[Route]:
    """Get route by route_id with stops eagerly loaded"""
    return db.query(Route)\
        .options(joinedload(Route.route_stops).joinedload(RouteStop.station))\
        .filter(Route.id == route_id)\
        .first()


def get_all_routes(db: Session, active_only: bool = True) -> List[Route]:
    """Get all routes, optionally filtered by active status"""
    query = db.query(Route)
    if active_only:
        query = query.filter(Route.is_active == True)
    return query.order_by(Route.name).all()


def get_routes_with_stops(db: Session, active_only: bool = True) -> List[Route]:
    """Get all routes with stops eagerly loaded"""
    query = db.query(Route)\
        .options(joinedload(Route.route_stops).joinedload(RouteStop.station))
    if active_only:
        query = query.filter(Route.is_active == True)
    return query.order_by(Route.name).all()


def get_route_stops_ordered(db: Session, route_id: int) -> List[Dict[str, Any]]:
    """Get ordered list of stops for a route with station details"""
    route_stops = db.query(RouteStop, Station)\
        .join(Station, RouteStop.station_id == Station.id)\
        .filter(RouteStop.route_id == route_id)\
        .order_by(RouteStop.stop_order)\
        .all()
    
    return [
        {
            "stop_order": rs.stop_order,
            "station_id": rs.station_id,
            "station_name": station.name,
            "latitude": station.latitude,
            "longitude": station.longitude
        }
        for rs, station in route_stops
    ]


def get_routes_by_station(db: Session, station_id: int) -> List[Route]:
    """Get all routes that pass through a specific station"""
    return db.query(Route)\
        .join(RouteStop, Route.id == RouteStop.route_id)\
        .filter(RouteStop.station_id == station_id)\
        .distinct()\
        .all()


def create_route(db: Session, name: str, from_location: str, 
                to_location: str, route_type: str, stop_ids: List[int]) -> Optional[Route]:
    """Create a new route with stops"""
    # Create route
    db_route = Route(
        name=name,
        from_location=from_location,
        to_location=to_location,
        route_type=route_type,
        is_active=True
    )
    db.add(db_route)
    db.flush()  # Flush to get route created before adding stops
    
    # Create route stops
    for order, station_id in enumerate(stop_ids):
        # Verify station exists
        station = get_station(db, station_id)
        if not station:
            db.rollback()
            return None
        
        db_route_stop = RouteStop(
            route_id=db_route.id,
            station_id=station_id,
            stop_order=order
        )
        db.add(db_route_stop)
    
    db.commit()
    db.refresh(db_route)
    return db_route


def update_route(db: Session, route_id: int, name: Optional[str] = None,
                from_location: Optional[str] = None, to_location: Optional[str] = None,
                route_type: Optional[str] = None, is_active: Optional[bool] = None, 
                stop_ids: Optional[List[int]] = None) -> Optional[Route]:
    """Update route details and/or stops"""
    db_route = get_route(db, route_id)
    if not db_route:
        return None
    
    # Update basic fields
    if name is not None:
        db_route.name = name
    if from_location is not None:
        db_route.from_location = from_location
    if to_location is not None:
        db_route.to_location = to_location
    if route_type is not None:
        db_route.route_type = route_type
    if is_active is not None:
        db_route.is_active = is_active
    
    # Update stops if provided
    if stop_ids is not None:
        # Delete existing stops
        db.query(RouteStop).filter(RouteStop.route_id == route_id).delete()
        
        # Add new stops
        for order, station_id in enumerate(stop_ids):
            station = get_station(db, station_id)
            if not station:
                db.rollback()
                return None
            
            db_route_stop = RouteStop(
                route_id=db_route.id,
                station_id=station_id,
                stop_order=order
            )
            db.add(db_route_stop)
    
    db.commit()
    db.refresh(db_route)
    return db_route


def delete_route(db: Session, route_id: int) -> bool:
    """Delete a route (will fail if referenced by schedules due to FK constraint)"""
    db_route = get_route(db, route_id)
    if not db_route:
        return False
    
    db.delete(db_route)
    db.commit()
    return True


# ============ Feedback CRUD Operations ============

def create_feedback(db: Session, user_id: int, feedback_data: Dict[str, Any]) -> Feedback:
    """Create new feedback"""
    # Convert issues list to JSON string if present
    issues = feedback_data.get("issues")
    if issues:
        feedback_data["issues"] = json.dumps(issues)
    
    db_feedback = Feedback(
        user_id=user_id,
        **feedback_data
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


def get_feedback(db: Session, feedback_id: int) -> Optional[Feedback]:
    """Get feedback by ID"""
    return db.query(Feedback).filter(Feedback.id == feedback_id).first()


def get_feedback_with_details(db: Session, feedback_id: int) -> Optional[Dict[str, Any]]:
    """Get feedback with related entity details"""
    feedback = db.query(Feedback)\
        .options(
            joinedload(Feedback.user),
            joinedload(Feedback.vehicle),
            joinedload(Feedback.route),
            joinedload(Feedback.schedule),
            joinedload(Feedback.admin)
        )\
        .filter(Feedback.id == feedback_id)\
        .first()
    
    if not feedback:
        return None
    
    # Parse issues from JSON
    issues = None
    if feedback.issues:
        try:
            issues = json.loads(feedback.issues)
        except:
            issues = []
    
    result = {
        "id": feedback.id,
        "user_id": feedback.user_id,
        "user_email": feedback.user.email if feedback.user and not feedback.is_anonymous else None,
        "is_anonymous": feedback.is_anonymous,
        "feedback_type": feedback.feedback_type,
        "category": feedback.category,
        "vehicle_id": feedback.vehicle_id,
        "vehicle_name": feedback.vehicle.name if feedback.vehicle else None,
        "route_id": feedback.route_id,
        "route_name": feedback.route.name if feedback.route else None,
        "schedule_id": feedback.schedule_id,
        "rating": feedback.rating,
        "title": feedback.title,
        "description": feedback.description,
        "issues": issues,
        "status": feedback.status,
        "priority": feedback.priority,
        "admin_response": feedback.admin_response,
        "admin_notes": feedback.admin_notes,
        "resolved_by": feedback.resolved_by,
        "resolved_at": feedback.resolved_at,
        "created_at": feedback.created_at,
        "updated_at": feedback.updated_at
    }
    
    return result


def get_user_feedbacks(db: Session, user_id: int, status: Optional[str] = None, 
                       skip: int = 0, limit: int = 100) -> List[Feedback]:
    """Get all feedback by a specific user"""
    query = db.query(Feedback).filter(Feedback.user_id == user_id)
    
    if status:
        query = query.filter(Feedback.status == status)
    
    return query.order_by(Feedback.created_at.desc()).offset(skip).limit(limit).all()


def get_all_feedbacks(db: Session, filters: Optional[Dict[str, Any]] = None,
                      skip: int = 0, limit: int = 100) -> tuple[List[Feedback], int]:
    """Get all feedbacks with optional filters (admin view)"""
    query = db.query(Feedback)
    
    if filters:
        if filters.get("status"):
            query = query.filter(Feedback.status == filters["status"])
        if filters.get("feedback_type"):
            query = query.filter(Feedback.feedback_type == filters["feedback_type"])
        if filters.get("category"):
            query = query.filter(Feedback.category == filters["category"])
        if filters.get("priority"):
            query = query.filter(Feedback.priority == filters["priority"])
        if filters.get("route_id"):
            query = query.filter(Feedback.route_id == filters["route_id"])
        if filters.get("vehicle_id"):
            query = query.filter(Feedback.vehicle_id == filters["vehicle_id"])
        if filters.get("rating"):
            query = query.filter(Feedback.rating == filters["rating"])
        if filters.get("date_from"):
            query = query.filter(Feedback.created_at >= filters["date_from"])
        if filters.get("date_to"):
            query = query.filter(Feedback.created_at <= filters["date_to"])
    
    # Get total count before pagination
    total = query.count()
    
    # Apply ordering and pagination
    feedbacks = query.order_by(Feedback.created_at.desc()).offset(skip).limit(limit).all()
    
    return feedbacks, total


def update_feedback(db: Session, feedback_id: int, update_data: Dict[str, Any]) -> Optional[Feedback]:
    """Update feedback (for user to edit their own feedback)"""
    feedback = get_feedback(db, feedback_id)
    if not feedback:
        return None
    
    # Convert issues list to JSON string if present
    if "issues" in update_data and update_data["issues"]:
        update_data["issues"] = json.dumps(update_data["issues"])
    
    for key, value in update_data.items():
        if value is not None and hasattr(feedback, key):
            setattr(feedback, key, value)
    
    db.commit()
    db.refresh(feedback)
    return feedback


def update_feedback_status(db: Session, feedback_id: int, status: str, 
                           priority: Optional[str] = None, admin_notes: Optional[str] = None,
                           admin_id: Optional[int] = None) -> Optional[Feedback]:
    """Update feedback status (admin action)"""
    feedback = get_feedback(db, feedback_id)
    if not feedback:
        return None
    
    feedback.status = status
    
    if priority:
        feedback.priority = priority
    
    if admin_notes:
        feedback.admin_notes = admin_notes
    
    # If marking as resolved or closed, record who and when
    if status in ["resolved", "closed"] and admin_id:
        feedback.resolved_by = admin_id
        feedback.resolved_at = get_ist_now()
    
    db.commit()
    db.refresh(feedback)
    return feedback


def add_admin_response(db: Session, feedback_id: int, admin_response: str, 
                       admin_id: int) -> Optional[Feedback]:
    """Add admin response to feedback"""
    feedback = get_feedback(db, feedback_id)
    if not feedback:
        return None
    
    feedback.admin_response = admin_response
    feedback.status = "in_review"  # Automatically move to in_review when admin responds
    
    db.commit()
    db.refresh(feedback)
    return feedback


def delete_feedback(db: Session, feedback_id: int) -> bool:
    """Delete feedback"""
    feedback = get_feedback(db, feedback_id)
    if not feedback:
        return False
    
    db.delete(feedback)
    db.commit()
    return True


def bulk_update_feedback_status(db: Session, feedback_ids: List[int], status: str,
                                admin_notes: Optional[str] = None, 
                                admin_id: Optional[int] = None) -> Dict[str, Any]:
    """Bulk update feedback status"""
    updated_ids = []
    failed_ids = []
    
    for feedback_id in feedback_ids:
        feedback = update_feedback_status(db, feedback_id, status, 
                                         admin_notes=admin_notes, admin_id=admin_id)
        if feedback:
            updated_ids.append(feedback_id)
        else:
            failed_ids.append(feedback_id)
    
    return {
        "success_count": len(updated_ids),
        "failed_count": len(failed_ids),
        "updated_ids": updated_ids,
        "failed_ids": failed_ids
    }


def get_feedback_stats(db: Session) -> Dict[str, Any]:
    """Get overall feedback statistics"""
    from sqlalchemy import func
    
    total = db.query(func.count(Feedback.id)).scalar()
    
    # Count by status
    by_status = {}
    status_counts = db.query(Feedback.status, func.count(Feedback.id))\
        .group_by(Feedback.status).all()
    for status, count in status_counts:
        by_status[status] = count
    
    # Count by type
    by_type = {}
    type_counts = db.query(Feedback.feedback_type, func.count(Feedback.id))\
        .group_by(Feedback.feedback_type).all()
    for ftype, count in type_counts:
        by_type[ftype] = count
    
    # Count by category
    by_category = {}
    category_counts = db.query(Feedback.category, func.count(Feedback.id))\
        .filter(Feedback.category.isnot(None))\
        .group_by(Feedback.category).all()
    for category, count in category_counts:
        by_category[category] = count
    
    # Count by priority
    by_priority = {}
    priority_counts = db.query(Feedback.priority, func.count(Feedback.id))\
        .group_by(Feedback.priority).all()
    for priority, count in priority_counts:
        by_priority[priority] = count
    
    # Average rating
    avg_rating = db.query(func.avg(Feedback.rating))\
        .filter(Feedback.rating.isnot(None)).scalar()
    
    total_with_rating = db.query(func.count(Feedback.id))\
        .filter(Feedback.rating.isnot(None)).scalar()
    
    return {
        "total_feedback": total,
        "by_status": by_status,
        "by_type": by_type,
        "by_category": by_category,
        "by_priority": by_priority,
        "average_rating": float(avg_rating) if avg_rating else None,
        "total_with_rating": total_with_rating
    }


def get_feedback_analytics(db: Session, date_from: Optional[datetime] = None,
                           date_to: Optional[datetime] = None) -> Dict[str, Any]:
    # Get detailed feedback analytics
    from sqlalchemy import func
    
    query = db.query(Feedback)
    
    if date_from:
        query = query.filter(Feedback.created_at >= date_from)
    if date_to:
        query = query.filter(Feedback.created_at <= date_to)
    
    total = query.count()
    
    # Average rating in date range
    avg_rating = query.filter(Feedback.rating.isnot(None))\
        .with_entities(func.avg(Feedback.rating)).scalar()
    
    # By route
    by_route = []
    route_data = query.filter(Feedback.route_id.isnot(None))\
        .join(Route)\
        .group_by(Feedback.route_id, Route.name)\
        .with_entities(
            Feedback.route_id,
            Route.name,
            func.count(Feedback.id).label('count'),
            func.avg(Feedback.rating).label('avg_rating')
        ).all()
    
    for route_id, route_name, count, rating in route_data:
        by_route.append({
            "route_id": route_id,
            "route_name": route_name,
            "feedback_count": count,
            "average_rating": float(rating) if rating else None
        })
    
    # By vehicle
    by_vehicle = []
    vehicle_data = query.filter(Feedback.vehicle_id.isnot(None))\
        .join(Vehicle)\
        .group_by(Feedback.vehicle_id, Vehicle.name)\
        .with_entities(
            Feedback.vehicle_id,
            Vehicle.name,
            func.count(Feedback.id).label('count'),
            func.avg(Feedback.rating).label('avg_rating')
        ).all()
    
    for vehicle_id, vehicle_name, count, rating in vehicle_data:
        by_vehicle.append({
            "vehicle_id": vehicle_id,
            "vehicle_name": vehicle_name,
            "feedback_count": count,
            "average_rating": float(rating) if rating else None
        })
    
    # By category
    by_category = {}
    category_counts = query.filter(Feedback.category.isnot(None))\
        .group_by(Feedback.category)\
        .with_entities(Feedback.category, func.count(Feedback.id)).all()
    for category, count in category_counts:
        by_category[category] = count
    
    # Rating distribution
    rating_distribution = {}
    rating_counts = query.filter(Feedback.rating.isnot(None))\
        .group_by(Feedback.rating)\
        .with_entities(Feedback.rating, func.count(Feedback.id)).all()
    for rating, count in rating_counts:
        rating_distribution[str(rating)] = count
    
    # Common issues (parse JSON)
    common_issues = {}
    feedbacks_with_issues = query.filter(Feedback.issues.isnot(None)).all()
    for feedback in feedbacks_with_issues:
        try:
            issues = json.loads(feedback.issues)
            for issue in issues:
                common_issues[issue] = common_issues.get(issue, 0) + 1
        except:
            pass
    
    # Convert to list and sort
    common_issues_list = [{"issue": k, "count": v} for k, v in common_issues.items()]
    common_issues_list.sort(key=lambda x: x["count"], reverse=True)
    
    return {
        "date_range": {
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None
        },
        "total_feedback": total,
        "average_rating": float(avg_rating) if avg_rating else None,
        "by_route": by_route,
        "by_vehicle": by_vehicle,
        "by_category": by_category,
        "common_issues": common_issues_list[:10],  # Top 10 issues
        "rating_distribution": rating_distribution
    }

