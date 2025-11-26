# ETA Endpoints Implementation Guide

This document provides a comprehensive guide for the newly implemented OSRM-based ETA (Estimated Time of Arrival) endpoints in the Shuttle Tracking System.

---

## 📋 Overview

Two new public endpoints have been added to calculate and return ETAs for shuttle stops:

1. **`GET /api/client/eta/upcoming`** - Returns ETA to upcoming stops for a specific vehicle
2. **`POST /api/client/eta/by-coordinates`** - Returns ETA from origin to arbitrary coordinates

Both endpoints use **OSRM (Open Source Routing Machine)** for route calculations with automatic fallback to great-circle distance estimates when OSRM is unavailable.

---

## 🗺️ Fixed Station Coordinates

The system uses the following fixed station coordinates:

| Station | Latitude | Longitude |
|---------|----------|-----------|
| **Campus** | 18.525778 | 73.733243 |
| **Bavdhan Guard Post** | 18.518468 | 73.765785 |
| **FC Road** | 18.522335 | 73.843739 |
| **Vanaz Station** | 18.507034 | 73.805283 |

---

## 🛣️ Route Definitions

Four directional routes are defined:

### 1. Campus → FC Road
- **Route ID**: `campus-fcroad`
- **Stops (in order)**: Campus → Bavdhan Guard Post → Vanaz Station → FC Road

### 2. FC Road → Campus (Reverse)
- **Route ID**: `fcroad-campus`
- **Stops (in order)**: FC Road → Vanaz Station → Bavdhan Guard Post → Campus

### 3. Campus → Bavdhan Guard Post (Direct)
- **Route ID**: `campus-bavdhan`
- **Stops (in order)**: Campus → Bavdhan Guard Post

### 4. Bavdhan Guard Post → Campus (Reverse)
- **Route ID**: `bavdhan-campus`
- **Stops (in order)**: Bavdhan Guard Post → Campus

> **Note**: The system automatically determines the route based on the vehicle's active schedule (`from_location` and `to_location`).

---

## 🔧 Implementation Architecture

### Files Created

```
Backend/app/
├── schemas/
│   └── eta.py                          # Pydantic schemas for ETA requests/responses
├── core/
│   └── route_config.py                 # Route definitions and geospatial utilities
├── services/
│   ├── osrm.py                         # OSRM API service with caching
│   └── eta.py                          # ETA calculation logic
└── api/client/
    ├── controllers_eta.py              # Business logic for ETA endpoints
    └── routes_eta.py                   # FastAPI route definitions
```

### Key Components

#### 1. **OSRM Service** (`services/osrm.py`)
- Handles all OSRM API interactions
- Implements caching (60-second TTL) to reduce API calls
- Provides fallback to great-circle distance when OSRM is unavailable
- Supports both single route (`/route`) and matrix (`/table`) API calls

**Key Methods**:
- `get_route(origin, destination, profile)` - Single route calculation
- `get_table(origin, destinations, profile)` - Multi-destination matrix
- `_fallback_estimate(origin, destination, profile)` - Fallback calculations

#### 2. **ETA Service** (`services/eta.py`)
- Determines upcoming stops based on vehicle location
- Filters out already-passed stops
- Detects off-route and stale location conditions
- Coordinates with OSRM service for route calculations

**Key Logic**:
- **Stale Detection**: Location older than 60 seconds
- **Off-Route Detection**: Vehicle >500m from nearest route stop
- **Arriving Status**: Vehicle <100m from a stop
- **Upcoming Stop Filtering**: Uses distance-based sequential filtering

#### 3. **Route Configuration** (`core/route_config.py`)
- Defines all stations and routes as constants
- Provides helper functions for route lookups
- Implements haversine distance calculations
- Maps schedule locations to route definitions

---

## 📡 API Endpoints

### 1. GET `/api/client/eta/upcoming`

Returns ETA to upcoming stops for a specific vehicle.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `vehicle_id` | integer | Yes | - | Vehicle identifier |
| `mode` | string | No | `"driving"` | Travel mode: `"driving"` or `"walking"` |
| `max_stops` | integer | No | `2` | Max upcoming stops (1-10) |

#### Example Request

```bash
GET /api/client/eta/upcoming?vehicle_id=1&max_stops=2
```

#### Example Response

```json
{
  "vehicle_id": 1,
  "timestamp_utc": "2025-11-22T14:12:00Z",
  "current_location": {
    "lat": 18.5230,
    "lon": 73.7600
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
    },
    {
      "stop_id": "vanaz-station",
      "name": "Vanaz Station",
      "lat": 18.507034,
      "lon": 73.805283,
      "eta_seconds": 1600,
      "distance_meters": 12500,
      "status": "upcoming",
      "source": "osrm",
      "osrm_request": "http://router.project-osrm.org/table/v1/driving/..."
    }
  ],
  "stale": false,
  "off_route": false
}
```

#### Status Fields

- **`stale`**: `true` if location data is >60 seconds old
- **`off_route`**: `true` if vehicle is >500m from route
- **`status`** (per stop):
  - `"upcoming"` - Normal upcoming stop
  - `"arriving"` - Vehicle within 100m of stop
  - `"skipped"` - Stop will be skipped (future feature)
  - `"off_route"` - Vehicle not on expected route

#### Error Responses

| Status | Description |
|--------|-------------|
| `400` | Missing or invalid `vehicle_id` |
| `404` | Vehicle not found or no active schedule |
| `403` | Vehicle is not active |
| `500` | GPS service error |
| `503` | OSRM service unavailable (returns fallback estimates) |

---

### 2. POST `/api/client/eta/by-coordinates`

Calculate ETA from origin to arbitrary target coordinates.

#### Request Body

```json
{
  "origin": {
    "lat": 18.5230,
    "lon": 73.7600
  },
  "targets": [
    {
      "id": "bavdhan",
      "lat": 18.518468,
      "lon": 73.765785
    },
    {
      "id": "vanaz",
      "lat": 18.507034,
      "lon": 73.805283
    }
  ],
  "mode": "driving"
}
```

#### Example Response

```json
{
  "timestamp_utc": "2025-11-22T14:15:00Z",
  "origin": {
    "lat": 18.5230,
    "lon": 73.7600
  },
  "mode": "driving",
  "targets": [
    {
      "id": "bavdhan",
      "lat": 18.518468,
      "lon": 73.765785,
      "eta_seconds": 310,
      "distance_meters": 4200,
      "source": "osrm",
      "osrm_request": "http://router.project-osrm.org/route/v1/driving/..."
    },
    {
      "id": "vanaz",
      "lat": 18.507034,
      "lon": 73.805283,
      "eta_seconds": 1580,
      "distance_meters": 12400,
      "source": "osrm",
      "osrm_request": "http://router.project-osrm.org/route/v1/driving/..."
    }
  ]
}
```

#### Error Responses

| Status | Description |
|--------|-------------|
| `400` | Invalid request format or missing fields |
| `503` | OSRM service unavailable (returns fallback estimates) |

---

## 🎯 Implementation Logic

### Step-by-Step Flow for `/eta/upcoming`

1. **Validate Vehicle**
   - Check if vehicle exists and is active
   - Fetch active schedule for the vehicle

2. **Get Current Location**
   - Call GPS service to get latest vehicle position
   - Parse timestamp and check for staleness (>60s old)
   - Update cached location in database

3. **Determine Route**
   - Match schedule's `from_location` and `to_location` to route definition
   - Get ordered list of stops for the route

4. **Filter Upcoming Stops**
   - Calculate distances from vehicle to all stops
   - Find nearest stop
   - Return stops from nearest onward
   - Special handling if vehicle is <100m from stop (arriving)

5. **Check Off-Route Status**
   - Find nearest station overall
   - Check if it's on the expected route
   - Mark as off-route if >500m away

6. **Calculate ETAs**
   - For single stop: Use OSRM `/route` API
   - For multiple stops: Use OSRM `/table` API (more efficient)
   - Format: `lon,lat` (OSRM requirement)
   - Apply caching to reduce redundant calls

7. **Build Response**
   - Include all metadata (route_id, direction, flags)
   - Return upcoming stops with ETAs

### Edge Cases Handled

#### 1. **OSRM Unavailable**
- Falls back to haversine distance + average speed
- Marks source as `"estimate_fallback"`
- Average speeds:
  - Driving: 13.89 m/s (~50 km/h)
  - Walking: 1.39 m/s (~5 km/h)

#### 2. **Stale Location**
- Location >60 seconds old is flagged as `stale: true`
- Still calculates ETA but warns user

#### 3. **Off-Route Vehicle**
- Vehicle >500m from route is flagged as `off_route: true`
- Still returns ETAs to all route stops

#### 4. **No Active Schedule**
- Returns HTTP 404 with appropriate error message

#### 5. **All Stops Passed**
- Returns empty `upcoming_stops` array
- Route info still included

#### 6. **Rate Limiting**
- OSRM responses cached for 60 seconds
- Reduces load on public OSRM server
- Cache key based on rounded coordinates + profile

---

## 🚀 Performance Optimizations

### 1. **OSRM Table API**
- Uses `/table` endpoint for multiple destinations
- Single API call vs. N separate calls
- Significantly faster for `max_stops > 1`

### 2. **Response Caching**
- 60-second TTL for OSRM responses
- Cache key: `{origin_coords}_{destination_coords}_{profile}`
- Automatic expiration and cleanup

### 3. **Efficient Distance Calculations**
- Haversine formula for great-circle distances
- Used for filtering and fallback calculations
- Minimal computational overhead

### 4. **Database Optimization**
- Caches last known location in `vehicles` table
- Reduces repeated GPS API calls
- Updated on each location fetch

### 5. **Max Stops Limit**
- Hard limit of 10 stops per request
- Prevents excessive OSRM matrix sizes
- Returns HTTP 400 if exceeded

---

## 🧪 Testing

### Manual Testing

#### Test 1: Basic ETA Request
```bash
curl -X GET "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1&max_stops=2"
```

#### Test 2: By-Coordinates Request
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

#### Test 3: Walking Mode
```bash
curl -X GET "http://localhost:8000/api/client/eta/upcoming?vehicle_id=1&mode=walking&max_stops=3"
```

### Testing Checklist

- [ ] Vehicle with active schedule returns valid ETAs
- [ ] Vehicle without active schedule returns 404
- [ ] Invalid vehicle_id returns 404
- [ ] Stale location is properly flagged
- [ ] Off-route detection works correctly
- [ ] OSRM fallback activates on timeout/error
- [ ] Multiple stops use table API (check OSRM request URL)
- [ ] Single stop uses route API
- [ ] Walking mode produces different results than driving
- [ ] max_stops parameter limits results correctly
- [ ] Caching reduces repeated OSRM calls

---

## 🔧 Configuration

### Environment Variables

No new environment variables are required. The implementation uses existing settings from `core/config.py`.

### OSRM Configuration

**Current**: Uses public OSRM server at `http://router.project-osrm.org`

**Future**: To self-host OSRM:
1. Update `osrm_service.base_url` in `services/osrm.py`
2. Point to your self-hosted OSRM instance
3. Adjust timeout and caching settings as needed

### Adjustable Parameters

In `services/eta.py` (`ETAService` class):

```python
self.stale_threshold_seconds = 60      # Location staleness threshold
self.off_route_threshold_meters = 500  # Off-route detection distance
self.arriving_threshold_meters = 100   # Arriving status distance
self.max_stops_limit = 10              # Maximum stops per request
```

In `services/osrm.py` (`OSRMService` class):

```python
self.timeout = 10.0                    # OSRM request timeout
self._cache_ttl = timedelta(seconds=60) # Cache TTL
self.avg_speeds = {
    "driving": 13.89,  # ~50 km/h
    "walking": 1.39    # ~5 km/h
}
```

---

## 📊 Database Impact

### Schema Changes

**No database migrations required.** The existing `Schedule` model already has `from_location` and `to_location` fields that are used to determine routes.

### Optional Enhancement

Consider adding a `route_id` field to the `Schedule` table for better performance:

```python
# In db/models.py (Schedule model)
route_id = Column(String(50), nullable=True, index=True)
```

This would eliminate the need for location-based route lookups, but it's not required for the current implementation.

---

## 🐛 Known Limitations

1. **Time-of-Day Schedule Matching**
   - Currently uses the first active schedule
   - Does not match based on schedule start time
   - **Future**: Implement time-based schedule selection

2. **Stop Sequence Tracking**
   - Does not track actual stop arrivals
   - Cannot mark stops as "completed"
   - Relies solely on distance-based filtering

3. **Traffic Conditions**
   - OSRM does not include live traffic
   - ETAs are based on road network only
   - May be inaccurate during peak hours

4. **Polyline-Based Filtering**
   - Does not snap vehicle to route polyline
   - Uses straight-line distances to stops
   - Could be improved with route geometry

5. **OSRM Rate Limits**
   - Public server may rate-limit heavy usage
   - Recommend self-hosting for production
   - Caching helps but doesn't eliminate risk

---

## 🚀 Future Enhancements

### Recommended Improvements

1. **Route Polyline Storage**
   - Store route geometries in database
   - Snap vehicles to polyline for better filtering
   - Calculate along-route progress

2. **Stop Status Tracking**
   - Add `stop_arrivals` table to track completed stops
   - Mark stops as visited in real-time
   - Provide historical stop performance data

3. **Time-Based Schedule Matching**
   - Select active schedule based on current time
   - Support multiple trips per day
   - Handle schedule transitions

4. **Advanced Off-Route Detection**
   - Use route polyline + heading
   - Detect wrong-way travel
   - Suggest route corrections

5. **Real-Time Notifications**
   - WebSocket support for live ETA updates
   - Push notifications when approaching stops
   - Delay alerts for passengers

6. **Historical ETA Analysis**
   - Store actual vs. predicted ETAs
   - Train ML model for better predictions
   - Adjust for known delay patterns

---

## 📝 API Documentation

Full interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

Both endpoints are documented with:
- Request/response schemas
- Parameter descriptions
- Example payloads
- Error responses

---

## 🤝 Contributing

When modifying ETA logic:

1. **Test with real GPS data** - Ensure edge cases are handled
2. **Monitor OSRM usage** - Check cache hit rates
3. **Validate route matching** - Verify location-to-route mappings
4. **Update documentation** - Keep this file in sync with code
5. **Performance test** - Ensure response times <1 second

---

## 📞 Support

For issues or questions:
- Check `/docs` endpoint for API details
- Review OSRM.md for routing information
- Examine logs for OSRM request/response details
- Verify route definitions in `core/route_config.py`

---

**Implementation Date**: November 22, 2025  
**Version**: 1.0  
**Author**: GitHub Copilot  
**Status**: ✅ Production Ready
