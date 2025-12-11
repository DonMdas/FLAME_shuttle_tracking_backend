from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta

from app.db.session import get_db
from app.core.config import settings
from app.core.logger import logger, log_request, log_success, log_error
from app.core.route_config import ROUTE_DEFINITIONS, get_all_route_ids
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
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleWithVehicleAdmin
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
    schedule_type: str = "regular",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all schedules. Defaults to regular schedules. Pass schedule_type=staff for staff schedules. Admin only."""
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
    schedule_type: str = "regular",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all schedules for a specific vehicle. Defaults to regular schedules. Pass schedule_type=staff for staff schedules. Admin only."""
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
    """Create a new schedule. Admin only."""
    # Verify route_id is valid
    if schedule.route_id not in ROUTE_DEFINITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid route_id '{schedule.route_id}'. Valid routes: {', '.join(get_all_route_ids())}"
        )
    
    # Verify vehicle exists
    vehicle = crud.get_vehicle(db, schedule.vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with ID {schedule.vehicle_id} not found"
        )
    return crud.create_schedule(db, schedule)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule_update: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a schedule. Admin only."""
    # If route_id is being updated, verify it's valid
    if schedule_update.route_id is not None:
        if schedule_update.route_id not in ROUTE_DEFINITIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid route_id '{schedule_update.route_id}'. Valid routes: {', '.join(get_all_route_ids())}"
            )
    
    # If vehicle_id is being updated, verify it exists
    if schedule_update.vehicle_id is not None:
        vehicle = crud.get_vehicle(db, schedule_update.vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with ID {schedule_update.vehicle_id} not found"
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

@router.get("/routes")
async def get_available_routes(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all available route definitions for creating schedules.
    Admin only.
    
    Returns list of routes with their IDs, names, and stops.
    """
    routes = []
    for route_id, route_def in ROUTE_DEFINITIONS.items():
        routes.append({
            "route_id": route_id,
            "name": route_def["name"],
            "from_location": route_def["from_location"],
            "to_location": route_def["to_location"],
            "stops": route_def["stops"]
        })
    return {"routes": routes}



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
