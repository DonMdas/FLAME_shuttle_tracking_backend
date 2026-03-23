from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta

from app.db.session import get_db
from app.core.config import settings
from app.core.logger import logger, log_request, log_success, log_error
from app.core.route_config import ROUTE_DEFINITIONS, get_all_route_ids
from app.core.constants import RouteType
from app.core.security import (
    authenticate_user, 
    create_access_token, 
    get_current_user,
    get_current_user_no_csrf,
    get_super_admin,
    get_password_hash,
    generate_csrf_token
)
from app.core.config import settings
from app.core.logger import logger, log_request, log_success, log_error
from app.schemas.vehicle import (
    AdminLogin,
    TokenResponse,
    AdminCreate,
    AdminResponse,
    VehicleCreate,
    VehicleUpdate,
    VehicleAdmin,
    VehicleSyncResponse,
    VehicleInfoComplete,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleWithVehicleAdmin
)
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.route import (
    StationCreate, StationUpdate, StationResponse,
    RouteCreate, RouteUpdate, RouteResponse, RouteWithStopsResponse,
    RouteStopCreate
)
from app.api.admin import controllers_admin
from app.db import crud

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============ Authentication ============

@router.post("/login")
async def admin_login(credentials: AdminLogin, response: Response, db: Session = Depends(get_db)):
    """
    Admin login endpoint.
    Supports both Super Admin (from .env) and normal admins (from database).
    Sets HTTP-only cookie with JWT token and returns CSRF token.
    """
    try:
        log_request("/admin/login", "POST", credentials.username)
        
        # Validate input
        if not credentials.username or not credentials.password:
            logger.warning(f"Login attempt with empty credentials")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username and password are required"
            )
        
        # Authenticate user
        user = authenticate_user(db, credentials.username, credentials.password)
        if not user:
            # Generic error message for security (don't reveal if username exists)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password. Please check your credentials and try again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate CSRF token
        csrf_token = generate_csrf_token()
        
        # Create access token with CSRF token embedded
        access_token = create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            csrf_token=csrf_token
        )
        
        # Set HTTP-only cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,  # Cannot be accessed by JavaScript
            secure=False,  # Allow on HTTP for local development (set to True in production)
            samesite="lax",  # CSRF protection
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
            path="/",
            domain=None  # Allow any domain in development
        )
        
        log_success("/admin/login", f"User '{user['username']}' logged in as {user['role']}", user["username"])
        
        logger.info(f"🍪 Cookie set: access_token (httponly=True, secure=False, samesite=lax, max_age={settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60})")
        
        # Return CSRF token AND access token (for clients that can't use cookies)
        return {
            "message": "Login successful",
            "csrf_token": csrf_token,
            "access_token": access_token,  # Return token for Bearer auth fallback
            "token_type": "bearer",
            "username": user["username"],
            "role": user["role"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/login", e, credentials.username)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login. Please try again later."
        )


@router.post("/logout")
async def admin_logout(response: Response, current_user: dict = Depends(get_current_user_no_csrf)):
    """
    Admin logout endpoint.
    Clears the HTTP-only cookie.
    Note: CSRF validation is disabled for logout since it's a low-risk operation.
    """
    try:
        username = current_user.get("username", "unknown")
        log_request("/admin/logout", "POST", username)
        
        # Clear the cookie
        response.delete_cookie(
            key="access_token",
            path="/",
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        
        log_success("/admin/logout", f"User '{username}' logged out successfully", username)
        
        return {
            "message": "Logged out successfully"
        }
        
    except Exception as e:
        log_error("/admin/logout", e, current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout. Please try again."
        )


# ============ Admin Management (Super Admin Only) ============

@router.post("/admins", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def create_new_admin(
    admin_data: AdminCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_super_admin)
):
    """
    Create a new admin account.
    Only Super Admin can create new admins.
    """
    # Check if username already exists
    existing_admin = crud.get_admin_by_username(db, admin_data.username)
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{admin_data.username}' already exists"
        )
    
    # Hash password and create admin
    hashed_password = get_password_hash(admin_data.password)
    new_admin = crud.create_admin(
        db, 
        username=admin_data.username,
        hashed_password=hashed_password
    )
    
    return new_admin


@router.get("/admins", response_model=List[AdminResponse])
async def list_admins(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_super_admin)
):
    """
    List all admin accounts.
    Only Super Admin can view all admins.
    """
    return crud.get_admins(db)


@router.delete("/admins/{admin_id}")
async def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_super_admin)
):
    """
    Delete an admin account.
    Only Super Admin can delete admins.
    """
    success = crud.delete_admin(db, admin_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    return {"message": "Admin deleted successfully"}


@router.patch("/admins/{admin_id}/status")
async def update_admin_status(
    admin_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_super_admin)
):
    """
    Activate or deactivate an admin account.
    Only Super Admin can update admin status.
    """
    admin = crud.update_admin_status(db, admin_id, is_active)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    return {"message": f"Admin {'activated' if is_active else 'deactivated'} successfully"}


# ============ Vehicle Management (All Admins) ============

@router.get("/vehicles", response_model=List[VehicleAdmin])
async def get_all_vehicles(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all vehicles with full details.
    Vehicles are automatically synced from EERA API.
    Admin only - requires authentication.
    """
    return await controllers_admin.list_all_vehicles(db)


@router.get("/vehicles-info", response_model=List[VehicleInfoComplete])
async def get_all_vehicles_info(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get complete real-time information for all vehicles from EERA API.
    
    Returns comprehensive vehicle data including:
    - Device attributes (ignition, battery, distance, etc.)
    - Real-time location (latitude, longitude, altitude)
    - Movement data (speed, course, motion)
    - Timestamps (device time, server time, fix time)
    - Device identification (name, IMEI, company)
    
    **Note**: This fetches live data directly from EERA API.
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request("/admin/vehicles-info", "GET", current_user.get("username"))
        vehicles_info = await controllers_admin.get_all_vehicles_info(db)
        log_success("/admin/vehicles-info", f"Retrieved {len(vehicles_info)} vehicles info", current_user.get("username"))
        return vehicles_info
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/vehicles-info", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch vehicles information"
        )


@router.post("/vehicles/sync", response_model=VehicleSyncResponse)
async def sync_vehicles(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Manually trigger vehicle sync from EERA API.
    Fetches all vehicles and updates database.
    Note: Automatic sync runs every 5 minutes in background.
    Admin only.
    """
    return await controllers_admin.sync_vehicles_from_api(db)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleAdmin)
async def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific vehicle by ID with live data from API.
    Admin only.
    """
    return await controllers_admin.get_vehicle_details(db, vehicle_id)


@router.patch("/vehicles/{vehicle_id}/active", response_model=VehicleAdmin)
async def set_vehicle_active(
    vehicle_id: int,
    active: bool,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Toggle vehicle active status.
    Only active vehicles are visible to clients.
    Admin only.
    """
    return await controllers_admin.toggle_vehicle_active(db, vehicle_id, active)


@router.put("/vehicles/{vehicle_id}", response_model=VehicleAdmin)
async def update_vehicle(
    vehicle_id: int,
    vehicle: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update vehicle (label and is_active only).
    Other fields are synced from API.
    Admin only.
    """
    return await controllers_admin.modify_vehicle(db, vehicle_id, vehicle)


# ============ Vehicle Control ============

@router.post("/vehicles/{vehicle_id}/test")
async def test_gps_connection(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Test GPS connection for a vehicle.
    Fetches live data from EERA API.
    Admin only.
    """
    return await controllers_admin.test_vehicle_connection(db, vehicle_id)


# ============ Deprecated Routes (for backward compatibility) ============

@router.post("/vehicles", response_model=VehicleAdmin, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    vehicle: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    DEPRECATED: Manual vehicle creation is no longer supported.
    Use /vehicles/sync instead.
    """
    return await controllers_admin.add_vehicle(db, vehicle)


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    DEPRECATED: Use PATCH /vehicles/{id}/active instead.
    """
    return await controllers_admin.remove_vehicle(db, vehicle_id)


# ============ Schedule Management ============

@router.get("/schedules", response_model=List[ScheduleWithVehicleAdmin])
async def get_all_schedules(
    schedule_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all schedules. Pass schedule_type=staff or schedule_type=regular to filter. Admin only."""
    schedules = crud.get_schedules(db, schedule_type=schedule_type)
    return schedules


@router.get("/schedules/{schedule_id}", response_model=ScheduleWithVehicleAdmin)
async def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific schedule by ID. Admin only."""
    schedule = crud.get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    return schedule


@router.get("/vehicles/{vehicle_id}/schedules", response_model=List[ScheduleWithVehicleAdmin])
async def get_vehicle_schedules(
    vehicle_id: int,
    schedule_type: str = RouteType.STUDENT.value,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all schedules for a specific vehicle. Defaults to student schedules. Pass schedule_type=staff or internal for other types. Admin only."""
    # Verify vehicle exists
    vehicle = crud.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    return crud.get_schedules_by_vehicle(db, vehicle_id, schedule_type=schedule_type)


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new schedule (supports both one-time and recurring). Admin only."""
    # Verify route exists in database
    route = crud.get_route(db, schedule.route_id)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route with ID {schedule.route_id} not found"
        )
    
    # Verify vehicle exists
    vehicle = crud.get_vehicle(db, schedule.vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with ID {schedule.vehicle_id} not found"
        )
    
    # Additional validation for recurring schedules
    if schedule.is_recurring and not schedule.repeat_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repeat_days must be provided for recurring schedules"
        )
    
    return crud.create_schedule(db, schedule)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule_update: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a schedule (including recurring days). Admin only."""
    # If route_id is being updated, verify it exists
    if schedule_update.route_id is not None:
        route = crud.get_route(db, schedule_update.route_id)
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route with ID {schedule_update.route_id} not found"
            )
    
    # Additional validation for recurring schedules
    if schedule_update.is_recurring is True and schedule_update.repeat_days is not None:
        if not schedule_update.repeat_days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="repeat_days cannot be empty for recurring schedules"
            )
    
    updated_schedule = crud.update_schedule(db, schedule_id, schedule_update)
    if not updated_schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    return updated_schedule


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a schedule. Admin only."""
    success = crud.delete_schedule(db, schedule_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    return {"message": "Schedule deleted successfully"}


# ============ Route Definitions (Read-Only) ============
# Note: The proper /routes endpoint is defined later with database integration
# This section is for legacy route definitions if needed



@router.patch("/schedules/{schedule_id}/active")
async def toggle_schedule_status(
    schedule_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Activate or deactivate a schedule. Admin only."""
    schedule = crud.update_schedule(db, schedule_id, ScheduleUpdate(is_active=is_active))
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    return {"message": f"Schedule {'activated' if is_active else 'deactivated'} successfully"}


@router.get("/schedules/day/{day_of_week}", response_model=List[ScheduleWithVehicleAdmin])
async def get_schedules_for_day(
    day_of_week: str,
    schedule_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all active schedules for a specific day of the week.
    Includes both recurring schedules for that day and one-time schedules.
    Valid days: monday, tuesday, wednesday, thursday, friday, saturday, sunday.
    Admin only.
    """
    valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    day_lower = day_of_week.lower()
    
    if day_lower not in valid_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid day_of_week. Must be one of: {', '.join(valid_days)}"
        )
    
    return crud.get_schedules_for_day(db, day_lower, schedule_type=schedule_type)


@router.get("/schedules/today/active", response_model=List[ScheduleWithVehicleAdmin])
async def get_today_schedules(
    schedule_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all active schedules for today.
    Automatically determines current day and returns relevant schedules.
    Admin only.
    """
    return crud.get_schedules_for_today(db, schedule_type=schedule_type)


# ============ User Management (Admin Only) ============

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    role: Optional[str] = None,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all users with optional role filter.
    Admin endpoint to view all registered users.
    
    Query Parameters:
    - role: Filter by role (student/staff)
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records to return
    """
    try:
        log_request("/admin/users", "GET", current_user.get("username"))
        users = await controllers_admin.list_all_users(db, role=role, skip=skip, limit=limit)
        log_success("/admin/users", f"Retrieved {len(users)} users", current_user.get("username"))
        return users
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/users", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific user by ID. Admin only."""
    try:
        log_request("/admin/users/{user_id}", "GET", current_user.get("username"))
        user = await controllers_admin.get_user_details(db, user_id)
        log_success("/admin/users/{user_id}", f"Retrieved user: {user.email}", current_user.get("username"))
        return user
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/users/{user_id}", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update user's role.
    Admin only - users cannot change their own roles.
    
    Body:
    - role: New role (student/staff)
    """
    try:
        log_request("/admin/users/{user_id}/role", "PUT", current_user.get("username"))
        updated_user = await controllers_admin.update_user_role_by_admin(db, user_id, role_data)
        log_success("/admin/users/{user_id}/role", f"Updated user role: {updated_user.email} -> {role_data.role}", current_user.get("username"))
        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/users/{user_id}/role", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role"
        )


@router.patch("/users/{user_id}/active")
async def toggle_user_status(
    user_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Activate or deactivate a user account. Admin only."""
    try:
        log_request("/admin/users/{user_id}/active", "PATCH", current_user.get("username"))
        updated_user = await controllers_admin.toggle_user_active(db, user_id, is_active)
        log_success("/admin/users/{user_id}/active", f"User {'activated' if is_active else 'deactivated'}: {updated_user.email}", current_user.get("username"))
        return {"message": f"User {'activated' if is_active else 'deactivated'} successfully"}
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/users/{user_id}/active", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a user permanently. Admin only.
    
    **Warning**: This action cannot be undone. Consider using PATCH /users/{user_id}/active
    to deactivate the user instead.
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request("/admin/users/{user_id}", "DELETE", current_user.get("username"))
        result = await controllers_admin.delete_user_by_admin(db, user_id)
        log_success("/admin/users/{user_id}", f"User {user_id} deleted", current_user.get("username"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/users/{user_id}", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


# ============ Station Management ============

@router.post("/stations", response_model=StationResponse)
async def create_station(
    station_data: StationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new station/stop. Admin only.
    
    **Request Body**:
    - `id`: Unique station ID (e.g., "campus", "fc-road")
    - `name`: Display name (e.g., "FLAME Campus", "FC Road")
    - `latitude`: Latitude coordinate
    - `longitude`: Longitude coordinate
    
    **Returns**: Created station details
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request("/admin/stations", "POST", current_user.get("username"))
        station = await controllers_admin.create_station_admin(db, station_data)
        log_success("/admin/stations", f"Station created: {station.id}", current_user.get("username"))
        return station
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/stations", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create station"
        )


@router.get("/stations", response_model=List[StationResponse])
async def list_stations(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all stations. Admin only.
    
    **Query Parameters**:
    - `active_only`: If true, only return active stations (default: false)
    
    **Returns**: List of all stations
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request("/admin/stations", "GET", current_user.get("username"))
        stations = await controllers_admin.list_all_stations(db, active_only)
        log_success("/admin/stations", f"Retrieved {len(stations)} stations", current_user.get("username"))
        return stations
    except Exception as e:
        log_error("/admin/stations", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve stations"
        )


@router.get("/stations/{station_id}", response_model=StationResponse)
async def get_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific station by ID. Admin only.
    
    **Returns**: Station details
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request(f"/admin/stations/{station_id}", "GET", current_user.get("username"))
        station = await controllers_admin.get_station_details(db, station_id)
        log_success(f"/admin/stations/{station_id}", f"Retrieved station: {station.name}", current_user.get("username"))
        return station
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"/admin/stations/{station_id}", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve station"
        )


@router.patch("/stations/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: int,
    station_data: StationUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a station. Admin only.
    
    **Request Body** (all fields optional):
    - `name`: Display name
    - `latitude`: Latitude coordinate
    - `longitude`: Longitude coordinate
    - `is_active`: Active status
    
    **Returns**: Updated station details
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request(f"/admin/stations/{station_id}", "PATCH", current_user.get("username"))
        station = await controllers_admin.update_station_admin(db, station_id, station_data)
        log_success(f"/admin/stations/{station_id}", f"Station updated: {station.name}", current_user.get("username"))
        return station
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"/admin/stations/{station_id}", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update station"
        )


@router.delete("/stations/{station_id}")
async def delete_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a station. Admin only.
    
    **Warning**: Will fail if the station is referenced by any routes.
    Remove the station from all routes before deleting.
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request(f"/admin/stations/{station_id}", "DELETE", current_user.get("username"))
        result = await controllers_admin.delete_station_admin(db, station_id)
        log_success(f"/admin/stations/{station_id}", f"Station deleted: {station_id}", current_user.get("username"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"/admin/stations/{station_id}", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete station. It may be referenced by routes."
        )


# ============ Route Management ============

@router.post("/routes", response_model=RouteWithStopsResponse)
async def create_route(
    route_data: RouteCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new route with stops. Admin only.
    
    **Route Types**: 'student' (default), 'staff', or 'internal'
    
    **Two methods supported:**
    
    **Method 1: Using existing station IDs**
    ```json
    {
        "name": "Campus → FC Road",
        "from_location": "Campus",
        "to_location": "FC Road",
        "route_type": "student",
        "stop_ids": [1, 2, 3]
    }
    ```
    
    **Method 2: Create stations inline**
    ```json
    {
        "name": "Campus → FC Road",
        "from_location": "Campus",
        "to_location": "FC Road",
        "route_type": "student",
        "stops": [
            {"name": "FLAME Campus", "latitude": 18.525778, "longitude": 73.733243},
            {"name": "Bavdhan Check Post", "latitude": 18.518468, "longitude": 73.765785},
            {"name": "FC Road", "latitude": 18.522552, "longitude": 73.848186}
        ]
    }
    ```
    
    When using `stops`, the system will:
    - Check if a station with the same name exists
    - If exists and location matches: reuse it
    - If exists but location differs: create new with unique name
    - If doesn't exist: create new station
    
    **Returns**: Created route with stops
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request("/admin/routes", "POST", current_user.get("username"))
        route = await controllers_admin.create_route_admin(db, route_data)
        log_success("/admin/routes", f"Route created: {route.name}", current_user.get("username"))
        return route
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/routes", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create route"
        )


@router.get("/routes", response_model=List[RouteWithStopsResponse])
async def list_routes(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all routes with stops. Admin only.
    
    **Query Parameters**:
    - `active_only`: If true, only return active routes (default: false)
    
    **Returns**: List of all routes with their stops
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request("/admin/routes", "GET", current_user.get("username"))
        routes = await controllers_admin.list_all_routes_admin(db, active_only)
        log_success("/admin/routes", f"Retrieved {len(routes)} routes", current_user.get("username"))
        return routes
    except Exception as e:
        log_error("/admin/routes", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve routes"
        )


@router.get("/routes/{route_id}", response_model=RouteWithStopsResponse)
async def get_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific route by ID with stops. Admin only.
    
    **Returns**: Route details with stops
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request(f"/admin/routes/{route_id}", "GET", current_user.get("username"))
        route = await controllers_admin.get_route_details_admin(db, route_id)
        log_success(f"/admin/routes/{route_id}", f"Retrieved route: {route.name}", current_user.get("username"))
        return route
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"/admin/routes/{route_id}", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve route"
        )


@router.patch("/routes/{route_id}", response_model=RouteWithStopsResponse)
async def update_route(
    route_id: int,
    route_data: RouteUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a route. Admin only.
    
    **Route Types**: 'student', 'staff', or 'internal'
    
    **All fields optional. Two methods for updating stops:**
    
    **Method 1: Using existing station IDs**
    ```json
    {
        "name": "Updated Route Name",
        "route_type": "staff",
        "stop_ids": [1, 3, 5]
    }
    ```
    
    **Method 2: Update stations inline**
    ```json
    {
        "name": "Updated Route Name",
        "stops": [
            {"name": "New Station A", "latitude": 18.52, "longitude": 73.73},
            {"name": "Existing Station", "latitude": 18.51, "longitude": 73.74}
        ]
    }
    ```
    
    When using `stops`, the system will find or create stations automatically.
    
    **Returns**: Updated route with stops
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request(f"/admin/routes/{route_id}", "PATCH", current_user.get("username"))
        route = await controllers_admin.update_route_admin(db, route_id, route_data)
        log_success(f"/admin/routes/{route_id}", f"Route updated: {route.name}", current_user.get("username"))
        return route
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"/admin/routes/{route_id}", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update route"
        )


@router.delete("/routes/{route_id}")
async def delete_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a route. Admin only.
    
    **Warning**: Will fail if the route is referenced by any schedules.
    Delete or update schedules first before deleting the route.
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request(f"/admin/routes/{route_id}", "DELETE", current_user.get("username"))
        result = await controllers_admin.delete_route_admin(db, route_id)
        log_success(f"/admin/routes/{route_id}", f"Route deleted: {route_id}", current_user.get("username"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"/admin/routes/{route_id}", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete route. It may be referenced by schedules."
        )


# ============ Route Stop Management ============

@router.post("/routes/stops", response_model=RouteWithStopsResponse)
async def add_stop_to_route(
    stop_data: RouteStopCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Add a stop to an existing route. Admin only.
    
    **Request Body**:
    - `route_id`: Route ID to add stop to
    - `station_id`: Station ID to add
    - `stop_order`: Position in route (0-based index)
    
    **Example**: To insert a station as the 2nd stop, use `stop_order: 1`
    
    **Returns**: Updated route with all stops
    
    **Security**: Requires admin authentication.
    """
    try:
        log_request("/admin/routes/stops", "POST", current_user.get("username"))
        route = await controllers_admin.add_stop_to_route(db, stop_data)
        log_success("/admin/routes/stops", f"Stop added to route {route.route_id}", current_user.get("username"))
        return route
    except HTTPException:
        raise
    except Exception as e:
        log_error("/admin/routes/stops", e, current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add stop to route"
        )

