# Quick Start Guide - New API-Driven System

## Prerequisites
- EERA API key with access to all vehicles

## Setup Steps

### 1. Update Environment Variables
Edit your `.env` file and add:
```env
# Replace with your actual EERA API key
EERA_API_KEY=your-eera-api-key-from-dashboard

# Optional - adjust if needed (defaults shown)
GPS_DATA_STALE_THRESHOLD=30
VEHICLE_SYNC_INTERVAL=300
```

### 2. Handle Database Migration

**Option A: Fresh Start (Development)**
```powershell
# Delete old database
Remove-Item shuttle_tracker.db -ErrorAction SilentlyContinue

# Database will be recreated on server start
```

**Option B: Keep Existing Data**
See `DATABASE_MIGRATION.md` for SQL migration scripts.

### 3. Install Dependencies (if needed)
```powershell
pip install -r requirements.txt
```

### 4. Start the Server
```powershell
# From the Backend directory
python -m uvicorn app.main:app --reload
```

You should see:
```
✅ Database initialized
✅ Vehicle sync service started (300s interval)
✅ Shuttle Tracker API v2.0.0 started
```

### 5. Test the System

#### A. Admin Login
```http
POST http://localhost:8000/api/admin/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

Save the `csrf_token` from the response.

#### B. Trigger Vehicle Sync
```http
POST http://localhost:8000/api/admin/vehicles/sync
X-CSRF-Token: <your-csrf-token>
Cookie: access_token=<from-cookie>
```

Response:
```json
{
  "success": true,
  "vehicles_synced": 10,
  "new_vehicles": 10,
  "updated_vehicles": 0,
  "timestamp": "2025-12-04T..."
}
```

#### C. View All Vehicles
```http
GET http://localhost:8000/api/admin/vehicles
Cookie: access_token=<from-cookie>
```

You should see all vehicles from your EERA API.

#### D. Toggle Vehicle Active Status
```http
PATCH http://localhost:8000/api/admin/vehicles/1/active?active=true
X-CSRF-Token: <your-csrf-token>
Cookie: access_token=<from-cookie>
```

#### E. Get Live Vehicle Location (Client Endpoint)
```http
GET http://localhost:8000/api/client/vehicles/1/location
```

This fetches fresh data from EERA API every time it's called.

## Frontend Integration

### Recommended Polling Intervals

**Vehicle List (Rarely Changes)**
```javascript
// Check for new vehicles every 5-10 minutes
setInterval(() => {
  fetchAvailableVehicles();
}, 300000); // 5 minutes
```

**Live Location (Real-time Tracking)**
```javascript
// Poll location when user is viewing the map
if (userIsViewingMap) {
  setInterval(() => {
    fetchVehicleLocation(vehicleId);
  }, 3000); // 3 seconds
}
```

**Stop Polling When Not Needed**
```javascript
// Stop when user navigates away
clearInterval(locationPollingInterval);
```

## Monitoring

### Check Background Sync
The vehicle sync runs automatically every 5 minutes (configurable via `VEHICLE_SYNC_INTERVAL`).

Check logs:
```
logs/shuttle_tracker_YYYYMMDD.log
```

Look for:
```
[INFO] Vehicle sync completed: 10 total, 0 new, 0 updated
```

### Manual Sync
You can trigger manual sync anytime via:
```http
POST /api/admin/vehicles/sync
```

## Troubleshooting

### No Vehicles Appear
1. Check EERA_API_KEY in .env is correct
2. Check logs for API errors
3. Manually trigger sync: `POST /api/admin/vehicles/sync`
4. Verify API key works at https://track.eeragpshouse.com

### "Vehicle not found"
1. Check vehicle is_active = true
2. Check vehicle has active schedules (for client endpoints)
3. Verify vehicle exists: `GET /api/admin/vehicles`

### Stale Location Data
- Check GPS_DATA_STALE_THRESHOLD (default: 30 seconds)
- If device hasn't sent data recently, fallback speed is used
- Check EERA dashboard for device connectivity

### ETA Using Fixed Speed Instead of API Speed
This is normal when:
- Vehicle is stationary (speed = 0)
- GPS data is older than 30 seconds
- Vehicle hasn't sent location update recently

## API Endpoints Reference

### Admin Endpoints (Require Authentication)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/admin/vehicles` | List all vehicles |
| POST | `/api/admin/vehicles/sync` | Manual sync from API |
| GET | `/api/admin/vehicles/{id}` | Get vehicle with live data |
| PATCH | `/api/admin/vehicles/{id}/active` | Toggle active status |
| PUT | `/api/admin/vehicles/{id}` | Update label/active |
| POST | `/api/admin/vehicles/{id}/test` | Test API connection |

### Client Endpoints (Public)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/client/vehicles` | List available vehicles |
| GET | `/api/client/vehicles/{id}/location` | Live location (poll every 3-5s) |
| GET | `/api/client/vehicles/{id}/status` | Operational status |
| GET | `/api/client/schedules` | Active schedules |

### ETA Endpoints (Public)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/client/eta/upcoming/{vehicle_id}` | ETA to upcoming stops |

## Next Steps

1. ✅ Verify EERA_API_KEY works
2. ✅ Sync vehicles successfully
3. ✅ Test live location fetching
4. ✅ Create schedules for vehicles
5. ✅ Update frontend to poll location every 3-5 seconds
6. ✅ Monitor background sync in logs

## Documentation

- Full API docs: http://localhost:8000/docs
- Implementation details: `IMPLEMENTATION_SUMMARY.md`
- Database migration: `DATABASE_MIGRATION.md`
