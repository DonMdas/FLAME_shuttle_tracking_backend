from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import timedelta

from db.session import get_db
from core.security import (
    authenticate_user, 
    create_access_token, 
    get_current_user, 
    get_super_admin,
    get_password_hash
)
from core.config import settings
from schemas.vehicle import (
    AdminLogin,
    TokenResponse,
    AdminCreate,
    AdminResponse,
    VehicleCreate,
    VehicleUpdate,
    VehicleAdmin,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse
)
from api.admin import controllers_admin
from db import crud

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============ Authentication ============

@router.post("/login", response_model=TokenResponse)
async def admin_login(credentials: AdminLogin, db: Session = Depends(get_db)):
    """
    Admin login endpoint.
    Supports both Super Admin (from .env) and normal admins (from database).
    Returns a JWT token for authenticated access.
    """
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def admin_logout(current_user: dict = Depends(get_current_user)):
    """
    Admin logout endpoint.
    Since JWT tokens are stateless, logout is handled client-side by deleting the token.
    This endpoint simply confirms the token is valid.
    """
    return {
        "message": "Logged out successfully",
        "detail": "Please delete the JWT token from client storage"
    }


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
    Get all vehicles with full details including access tokens.
    Admin only - requires authentication.
    """
    return await controllers_admin.list_all_vehicles(db)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleAdmin)
async def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific vehicle by ID. Admin only."""
    return await controllers_admin.get_vehicle_details(db, vehicle_id)


@router.post("/vehicles", response_model=VehicleAdmin, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    vehicle: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Add a new vehicle to the tracking system.
    Validates the GPS access token before creating.
    Admin only.
    """
    return await controllers_admin.add_vehicle(db, vehicle)


@router.put("/vehicles/{vehicle_id}", response_model=VehicleAdmin)
async def update_vehicle(
    vehicle_id: int,
    vehicle: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update vehicle information. Admin only."""
    return await controllers_admin.modify_vehicle(db, vehicle_id, vehicle)


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Remove a vehicle from the system. Admin only."""
    return await controllers_admin.remove_vehicle(db, vehicle_id)


# ============ Vehicle Control ============

@router.post("/vehicles/{vehicle_id}/test")
async def test_gps_connection(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Test GPS connection for a vehicle.
    Fetches live data to verify the access token is working.
    Admin only.
    """
    return await controllers_admin.test_vehicle_connection(db, vehicle_id)


@router.patch("/vehicles/{vehicle_id}/active")
async def set_vehicle_active(
    vehicle_id: int,
    active: bool,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Toggle vehicle active status. Admin only."""
    return await controllers_admin.toggle_vehicle_active(db, vehicle_id, active)


# ============ Schedule Management ============

@router.get("/schedules", response_model=List[ScheduleResponse])
async def get_all_schedules(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all schedules. Admin only."""
    schedules = crud.get_schedules(db)
    return schedules


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
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


@router.get("/vehicles/{vehicle_id}/schedules", response_model=List[ScheduleResponse])
async def get_vehicle_schedules(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all schedules for a specific vehicle. Admin only."""
    # Verify vehicle exists
    vehicle = crud.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    return crud.get_schedules_by_vehicle(db, vehicle_id)


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new schedule. Admin only."""
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
