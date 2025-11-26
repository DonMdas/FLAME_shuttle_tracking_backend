# Quick Start Guide - ETA Endpoints

## 🚀 Running the Server

Before running the server, ensure you have a `.env` file configured in the `Backend` directory. If you don't have one, create it with the required settings (see ENV_CONFIG.md).

### Start the FastAPI server:

```powershell
cd c:\courses_internship\IMP\Shuttle_tracker_client\Backend
uv run uvicorn app.main:app --reload
```

The server will start at `http://localhost:8000`

### Access API Documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🧪 Testing the ETA Endpoints

### Endpoint 1: GET `/api/client/eta/upcoming`

Get ETA to upcoming stops for a vehicle.

#### Prerequisites:
1. Vehicle must exist in database with `vehicle_id`
2. Vehicle must have an active schedule
3. GPS device must be responding

#### Basic Test:
```bash
curl "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1"
```

#### With Parameters:
```bash
curl "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1&max_stops=3&mode=driving"
```

#### Using PowerShell:
```powershell
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1&max_stops=2" -Method Get
$response | ConvertTo-Json -Depth 10
```

#### Expected Response:
```json
{
  "vehicle_id": 1,
  "timestamp_utc": "2025-11-22T14:30:00Z",
  "current_location": {
    "lat": 18.523000,
    "lon": 73.760000
  },
  "route_id": "campus-fcroad",
  "direction": "Campus → FC Road",
  "upcoming_stops": [
    {
      "stop_id": "bavdhan-guard-post",
      "name": "Bavdhan Guard post",
      "lat": 18.518468,
      "lon": 73.765785,
      "eta_seconds": 310,
      "distance_meters": 4200,
      "status": "upcoming",
      "source": "osrm",
      "osrm_request": "http://router.project-osrm.org/table/v1/driving/..."
    }
  ],
  "stale": false,
  "off_route": false
}
```

---

### Endpoint 2: POST `/api/client/eta/by-coordinates`

Calculate ETA from origin to custom coordinates.

#### Using cURL:
```bash
curl -X POST "http://localhost:8000/api/client/eta/by-coordinates" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": {"lat": 18.525778, "lon": 73.733243},
    "targets": [
      {"id": "bavdhan", "lat": 18.518468, "lon": 73.765785},
      {"id": "vanaz", "lat": 18.507034, "lon": 73.805283}
    ],
    "mode": "driving"
  }'
```

#### Using PowerShell:
```powershell
$body = @{
    origin = @{
        lat = 18.525778
        lon = 73.733243
    }
    targets = @(
        @{
            id = "bavdhan"
            lat = 18.518468
            lon = 73.765785
        },
        @{
            id = "vanaz"
            lat = 18.507034
            lon = 73.805283
        }
    )
    mode = "driving"
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/client/eta/by-coordinates" -Method Post -Body $body -ContentType "application/json"
$response | ConvertTo-Json -Depth 10
```

#### Expected Response:
```json
{
  "timestamp_utc": "2025-11-22T14:35:00Z",
  "origin": {
    "lat": 18.525778,
    "lon": 73.733243
  },
  "mode": "driving",
  "targets": [
    {
      "id": "bavdhan",
      "lat": 18.518468,
      "lon": 73.765785,
      "eta_seconds": 450,
      "distance_meters": 3800,
      "source": "osrm",
      "osrm_request": "http://router.project-osrm.org/route/v1/driving/..."
    },
    {
      "id": "vanaz",
      "lat": 18.507034,
      "lon": 73.805283,
      "eta_seconds": 1200,
      "distance_meters": 9500,
      "source": "osrm",
      "osrm_request": "http://router.project-osrm.org/table/v1/driving/..."
    }
  ]
}
```

---

## 🧩 Testing Different Scenarios

### Scenario 1: Test Walking Mode
```bash
curl "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1&mode=walking"
```

### Scenario 2: Test Maximum Stops
```bash
curl "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1&max_stops=10"
```

### Scenario 3: Test Invalid Vehicle
```bash
curl "http://localhost:8000/api/client/eta/upcoming?vehicle_id=999"
# Expected: 404 Not Found
```

### Scenario 4: Test OSRM Fallback
To test fallback logic, temporarily change the OSRM URL in `services/osrm.py` to an invalid URL, then make a request. The system should return estimates with `"source": "estimate_fallback"`.

---

## 📊 Interpreting Results

### Status Indicators

#### `stale` flag:
- `false` - Location is fresh (< 60 seconds old)
- `true` - Location is stale (≥ 60 seconds old)

#### `off_route` flag:
- `false` - Vehicle is on expected route
- `true` - Vehicle is >500m from route

#### Stop `status`:
- `"upcoming"` - Normal upcoming stop
- `"arriving"` - Vehicle within 100m of stop
- `"off_route"` - Vehicle not on route
- `"skipped"` - Stop will be skipped (future feature)

#### `source`:
- `"osrm"` - ETA from OSRM routing engine
- `"estimate_fallback"` - Estimate based on straight-line distance

---

## 🔍 Debugging

### Check Server Logs
```powershell
# Server logs will show:
# - Route determination
# - OSRM API calls
# - Cache hits/misses
# - Errors and warnings
```

### Verify Vehicle Data
```bash
# Get vehicle location
curl "http://localhost:8000/api/client/vehicles/1/location"

# Get vehicle schedule
curl "http://localhost:8000/api/client/schedules"
```

### Test OSRM Directly
```bash
# Test OSRM public server
curl "http://router.project-osrm.org/route/v1/driving/73.733243,18.525778;73.765785,18.518468?overview=false"
```

### Common Issues

#### Issue: "Vehicle not found"
- **Solution**: Check if vehicle exists with correct ID in database

#### Issue: "No active schedule found"
- **Solution**: Ensure vehicle has a schedule with `is_active=True`

#### Issue: "Unable to fetch vehicle location"
- **Solution**: Verify GPS device token and EERA API connectivity

#### Issue: "OSRM service unavailable"
- **Solution**: System will use fallback estimates automatically

#### Issue: Empty `upcoming_stops` array
- **Possible causes**:
  1. Vehicle has passed all stops
  2. Route not properly defined
  3. Vehicle significantly off-route

---

## 📈 Performance Testing

### Single Request Timing
```powershell
Measure-Command {
    Invoke-RestMethod -Uri "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1"
}
```

Expected: < 1 second for first request, < 0.5 seconds for cached requests

### Cache Testing
```powershell
# First request (uncached)
Invoke-RestMethod -Uri "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1"

# Second request (should be cached)
Invoke-RestMethod -Uri "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1"

# After 60 seconds, cache expires and request goes to OSRM again
```

---

## 🛠️ Integration with Frontend

### JavaScript/TypeScript Example:

```typescript
// Fetch upcoming stops for a vehicle
async function fetchUpcomingStops(vehicleId: number) {
  const response = await fetch(
    `http://localhost:8000/api/client/eta/upcoming?vehicle_id=${vehicleId}&max_stops=3`
  );
  const data = await response.json();
  
  console.log('Route:', data.direction);
  console.log('Upcoming stops:', data.upcoming_stops);
  
  // Display ETAs
  data.upcoming_stops.forEach(stop => {
    const etaMinutes = Math.round(stop.eta_seconds / 60);
    console.log(`${stop.name}: ${etaMinutes} minutes`);
  });
  
  // Check warnings
  if (data.stale) {
    console.warn('Location data is stale');
  }
  if (data.off_route) {
    console.warn('Vehicle appears to be off route');
  }
}

// Calculate ETA to custom locations
async function calculateETA(origin, targets) {
  const response = await fetch(
    'http://localhost:8000/api/client/eta/by-coordinates',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ origin, targets, mode: 'driving' })
    }
  );
  const data = await response.json();
  
  data.targets.forEach(target => {
    const etaMinutes = Math.round(target.eta_seconds / 60);
    const distanceKm = (target.distance_meters / 1000).toFixed(1);
    console.log(`${target.id}: ${etaMinutes} min (${distanceKm} km)`);
  });
}
```

---

## ✅ Pre-Deployment Checklist

Before deploying to production:

- [ ] Environment variables configured (`.env` file)
- [ ] Database initialized with vehicles and schedules
- [ ] GPS devices configured and responding
- [ ] OSRM service accessible (public or self-hosted)
- [ ] API endpoints tested with real data
- [ ] Error handling verified (404, 503, etc.)
- [ ] Cache performance acceptable
- [ ] Response times < 1 second
- [ ] Frontend integration tested
- [ ] CORS settings configured for frontend domain
- [ ] API documentation reviewed
- [ ] Monitoring/logging configured

---

## 📚 Additional Resources

- **Full Documentation**: See `ETA_IMPLEMENTATION.md`
- **OSRM Guide**: See `OSRM.md`
- **API Docs**: http://localhost:8000/docs
- **Route Config**: `app/core/route_config.py`
- **Service Logic**: `app/services/eta.py`

---

**Happy Testing! 🚀**
