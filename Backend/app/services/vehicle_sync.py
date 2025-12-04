"""
Vehicle Sync Service

Background service that periodically syncs vehicle list from EERA API.
This runs every 5-10 minutes to check for new/updated vehicles (metadata only).
Live location/speed data is fetched on-demand by frontend requests.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.services.gps import gps_service
from app.db.session import SessionLocal
from app.db import crud


class VehicleSyncService:
    """Service for syncing vehicle list from EERA API"""
    
    def __init__(self):
        self.sync_interval = settings.VEHICLE_SYNC_INTERVAL
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
    
    async def sync_vehicles(self, db: Session) -> dict:
        """
        Sync vehicles from EERA API to database.
        Updates existing vehicles and adds new ones.
        
        Args:
            db: Database session
            
        Returns:
            Dict with sync statistics
        """
        try:
            logger.info("Starting vehicle sync from EERA API")
            
            # Check if database tables exist before attempting sync
            from sqlalchemy import inspect
            inspector = inspect(db.bind)
            if 'vehicles' not in inspector.get_table_names():
                logger.warning("Database tables not yet created, skipping sync")
                return {
                    "success": False,
                    "vehicles_synced": 0,
                    "new_vehicles": 0,
                    "updated_vehicles": 0,
                    "message": "Database not initialized yet"
                }
            
            # Fetch all vehicles from API
            api_vehicles = await gps_service.get_all_vehicles_info()
            
            if not api_vehicles:
                logger.warning("No vehicles returned from API")
                return {
                    "success": True,
                    "vehicles_synced": 0,
                    "new_vehicles": 0,
                    "updated_vehicles": 0,
                    "message": "No vehicles found in API"
                }
            
            # Sync each vehicle
            new_count = 0
            updated_count = 0
            
            for api_vehicle in api_vehicles:
                result = crud.sync_vehicle_from_api(db, api_vehicle)
                
                if result["created"]:
                    new_count += 1
                elif result["updated"]:
                    updated_count += 1
            
            logger.info(f"Vehicle sync completed: {len(api_vehicles)} total, {new_count} new, {updated_count} updated")
            
            return {
                "success": True,
                "vehicles_synced": len(api_vehicles),
                "new_vehicles": new_count,
                "updated_vehicles": updated_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Vehicle sync failed: {type(e).__name__} - {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _periodic_sync(self):
        """Background task that runs periodic vehicle sync"""
        logger.info(f"Vehicle sync service started (interval: {self.sync_interval}s)")
        
        # Wait a bit on first start to ensure database is initialized
        await asyncio.sleep(5)
        
        while self.is_running:
            try:
                # Create database session
                db = SessionLocal()
                try:
                    await self.sync_vehicles(db)
                finally:
                    db.close()
                
                # Wait for next sync interval
                await asyncio.sleep(self.sync_interval)
                
            except asyncio.CancelledError:
                logger.info("Vehicle sync service cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic sync: {type(e).__name__} - {str(e)}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(60)
    
    async def start(self):
        """Start the background sync service"""
        if self.is_running:
            logger.warning("Vehicle sync service already running")
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._periodic_sync())
        logger.info("Vehicle sync service task created")
    
    async def stop(self):
        """Stop the background sync service"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Vehicle sync service stopped")


# Singleton instance
vehicle_sync_service = VehicleSyncService()
