# 🔄 Hybrid Location Caching Strategy

## Overview
The system uses a **hybrid approach** combining cached location data with live GPS fetching for optimal performance and reliability.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Client Request: GET /api/client/vehicles/1/location   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│  Backend Controller                                      │
│  1. Get vehicle from MySQL database                     │
│  2. Check: is_active && is_visible?                     │
│  3. Fetch LIVE GPS data from EERA API                   │
│  4. Update cached location in database                  │
│  5. Return live location to client                      │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Database Storage (MySQL)

### Vehicles Table Schema
```sql
CREATE TABLE vehicles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    label VARCHAR(255),
    route_destination VARCHAR(255),           -- "Campus", "FC Road", etc.
    device_unique_id VARCHAR(50) UNIQUE NOT NULL,
    access_token VARCHAR(500) NOT NULL,        -- GPS token (SECURE)
    is_active BOOLEAN DEFAULT TRUE,
    is_visible BOOLEAN DEFAULT TRUE,
    
    -- CACHED LOCATION (for fallback/preview)
    last_latitude FLOAT,
    last_longitude FLOAT,
    last_updated DATETIME,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP
);
```

---

## ⚡ How It Works

### 1️⃣ Client Requests Location
```bash
GET /api/client/vehicles/1/location
```

### 2️⃣ Backend Processing Flow
```python
async def get_vehicle_live_location(db: Session, vehicle_id: int):
    # Step 1: Get vehicle from database
    vehicle = crud.get_vehicle(db, vehicle_id)
    
    # Step 2: Verify vehicle is available
    if not vehicle.is_active or not vehicle.is_visible:
        raise HTTPException(403, "Vehicle not available")
    
    # Step 3: Fetch LIVE GPS data from EERA API
    device_data = await gps_service.get_device_info(vehicle.access_token)
    
    # Step 4: Update cached location in database
    crud.update_vehicle_location(
        db, vehicle_id,
        device_data["latitude"],
        device_data["longitude"]
    )
    
    # Step 5: Return LIVE location
    return VehicleLocation(
        vehicle_id=vehicle.id,
        name=vehicle.name,
        route_destination=vehicle.route_destination,
        latitude=device_data["latitude"],      # LIVE data
        longitude=device_data["longitude"],    # LIVE data
        speed=device_data["speed"],
        timestamp=device_data["timestamp"],
        ...
    )
```

### 3️⃣ What Gets Cached?
```python
# After every successful GPS fetch, we update:
vehicle.last_latitude = device_data["latitude"]
vehicle.last_longitude = device_data["longitude"]
vehicle.last_updated = datetime.utcnow()
db.commit()
```

---

## ✅ Benefits of Hybrid Approach

### Why Cache Location?

✅ **Fallback when GPS is offline**
- If EERA API is down, show last known location
- Better UX than "no data available"

✅ **Quick preview on vehicle list**
```bash
GET /api/client/vehicles
# Returns: [{id: 1, name: "Shuttle A", last_latitude: 18.44, last_longitude: 73.91}]
# Client can show approximate pins on map instantly
```

✅ **Debugging & monitoring**
- Admin can see "when was last update"
- Detect stuck/offline vehicles

### Why Fetch Live Data?

✅ **Always fresh**
- Location endpoint returns real-time GPS data
- No stale data issues

✅ **No background polling**
- Don't need cron jobs or scheduled tasks
- Reduces server load

✅ **On-demand updates**
- Only fetch when client requests
- Scales with actual usage

---

## 🎯 Best Practices Implemented

### 1. Cache Write Strategy
```python
# Write to cache AFTER successful GPS fetch
# Never write stale data
if gps_fetch_successful:
    update_cache(latitude, longitude, timestamp)
```

### 2. Cache Read Strategy
```python
# Read from cache for:
# - Vehicle list endpoint (quick preview)
# - Admin dashboard (last seen location)

# Fetch live data for:
# - Individual vehicle tracking
# - Real-time location updates
```

### 3. Error Handling
```python
try:
    live_data = fetch_from_gps()
    update_cache(live_data)
    return live_data
except GPSAPIError:
    # Could fallback to cache here if needed
    raise HTTPException("GPS unavailable")
```

---

## 🔄 Admin Route Destination Management

### Admin Can Update Route
```bash
PUT /api/admin/vehicles/1
Headers: Authorization: Bearer <token>
Body: {
  "route_destination": "FC Road"
}
```

### Implementation
```python
@router.put("/vehicles/{vehicle_id}")
async def update_vehicle(vehicle_id: int, vehicle: VehicleUpdate, ...):
    # Admin can change ANY field including route_destination
    return await controllers_admin.modify_vehicle(db, vehicle_id, vehicle)
```

### Client Sees Updated Route Immediately
```bash
GET /api/client/vehicles/1/location
Response: {
  "vehicle_id": 1,
  "name": "Shuttle A",
  "route_destination": "FC Road",  # Updated by admin
  "latitude": 18.444,               # Live GPS data
  "longitude": 73.911,              # Live GPS data
  ...
}
```

---

## 🚀 Usage Patterns

### Pattern 1: Map View (All Vehicles)
```javascript
// Frontend calls:
const vehicles = await fetch('/api/client/vehicles')
// Shows quick preview with cached locations

// User clicks on vehicle:
const liveLocation = await fetch('/api/client/vehicles/1/location')
// Shows real-time tracking
```

### Pattern 2: Live Tracking
```javascript
// Poll every 5 seconds for updates
setInterval(async () => {
  const location = await fetch('/api/client/vehicles/1/location')
  updateMapMarker(location)
}, 5000)
```

### Pattern 3: Admin Monitoring
```javascript
// Admin dashboard shows all vehicles with:
// - Last known location (from cache)
// - Time since last update
// - Test GPS button to force live fetch
```

---

## 📝 Summary

| Aspect | Strategy |
|--------|----------|
| **Storage** | MySQL with cached lat/lng |
| **Live Data** | Fetch from EERA API on-demand |
| **Cache Update** | After every successful GPS fetch |
| **Cache Usage** | Vehicle list preview, fallback |
| **Route Info** | Stored in DB, admin can update |
| **Best For** | Real-time tracking with reliability |

**No separate location history table needed** - we prioritize live data over historical tracking.
