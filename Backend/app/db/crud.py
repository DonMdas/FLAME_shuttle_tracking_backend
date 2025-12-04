from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from .models import Vehicle, Admin, Schedule
from schemas.vehicle import VehicleCreate, VehicleUpdate, ScheduleCreate, ScheduleUpdate

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
    Creates new vehicle if doesn't exist, updates if exists.
    
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
    """Get a single schedule by ID"""
    return db.query(Schedule).filter(Schedule.id == schedule_id).first()


def get_schedules(db: Session, skip: int = 0, limit: int = 100) -> List[Schedule]:
    """Get all schedules (admin view)"""
    return db.query(Schedule).offset(skip).limit(limit).all()


def get_schedules_by_vehicle(db: Session, vehicle_id: int) -> List[Schedule]:
    """Get all schedules for a specific vehicle"""
    return db.query(Schedule).filter(Schedule.vehicle_id == vehicle_id).all()


def get_active_schedules(db: Session) -> List[Schedule]:
    """Get all active schedules (client view)"""
    return db.query(Schedule).filter(Schedule.is_active == True).all()


def create_schedule(db: Session, schedule: ScheduleCreate) -> Schedule:
    """Create a new schedule"""
    db_schedule = Schedule(
        vehicle_id=schedule.vehicle_id,
        start_time=schedule.start_time,
        route_id=schedule.route_id,
        is_active=schedule.is_active
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


def update_schedule(db: Session, schedule_id: int, schedule_update: ScheduleUpdate) -> Optional[Schedule]:
    """Update a schedule"""
    db_schedule = get_schedule(db, schedule_id)
    if not db_schedule:
        return None
    
    update_data = schedule_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_schedule, field, value)
    
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


def delete_schedule(db: Session, schedule_id: int) -> bool:
    """Delete a schedule"""
    db_schedule = get_schedule(db, schedule_id)
    if not db_schedule:
        return False
    
    db.delete(db_schedule)
    db.commit()
    return True
