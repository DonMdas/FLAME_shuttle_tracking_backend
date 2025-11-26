# Shuttle Tracker API - Complete Endpoint Documentation

**Version:** 2.0.0  
**Base URL:** `http://localhost:8000` (or your deployed URL)  
**API Documentation:** `/docs` (Swagger UI) | `/redoc` (ReDoc)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Public Client Endpoints](#public-client-endpoints)
4. [Admin Endpoints](#admin-endpoints)
5. [Security Model](#security-model)
6. [Error Responses](#error-responses)

---

## 🎯 Overview

The Shuttle Tracker API provides two distinct sets of endpoints:

### **Client Endpoints** (`/api/client/*`)
- 🌐 **Public** - No authentication required
- 👥 Used by end-users (students, staff)
- 📱 Suitable for mobile apps and public dashboards
- 🔒 Only exposes vehicles with **active schedules**

### **Admin Endpoints** (`/api/admin/*`)
- 🔐 **Protected** - Requires JWT authentication
- 👨‍💼 Used by administrators
- ⚙️ Full CRUD operations on vehicles, schedules, and admins
- 🔑 Two roles: **Super Admin** and **Admin**

---

## 🔐 Authentication

### Admin Roles

| Role | Source | Capabilities |
|------|--------|-------------|
| **Super Admin** | `.env` file (`ADMIN_USERNAME`, `ADMIN_PASSWORD`) | Create/delete admins, manage all vehicles and schedules |
| **Admin** | Database (created by Super Admin) | Manage vehicles and schedules only |

### Login Flow

1. **POST** `/api/admin/login` with credentials
2. Receive JWT token
3. Include token in subsequent requests: `Authorization: Bearer <token>`

---

## 🌐 Public Client Endpoints

All client endpoints are **public** and require **no authentication**. They only expose vehicles that have **active schedules** (controlled by admin).

### 1️⃣ Get Active Schedules

**Endpoint:** `GET /api/client/schedules`

**Description:** Get all active schedules with vehicle details.

**Response Example:**
```json
[
  {
    "id": 1,
    "vehicle_id": 1,
    "start_time": "2025-11-23T07:00:00+05:30",
    "from_location": "Campus",
    "to_location": "FC Road",
    "is_active": true,
    "created_at": "2025-11-20T10:00:00+05:30",
    "vehicle": {
      "vehicle_id": 1,
      "name": "Shuttle-01",
      "label": "Morning Route",
      "last_latitude": 18.525778,
      "last_longitude": 73.733243,
      "last_updated": "2025-11-23T08:30:00+05:30"
    }
  }
]
```

**Use Case:** Display available shuttle routes to users.

---

### 2️⃣ Get Available Vehicles

**Endpoint:** `GET /api/client/vehicles`

**Description:** Get list of vehicles that have active schedules.

**Response Example:**
```json
[
  {
    "vehicle_id": 1,
    "name": "Shuttle-01",
    "label": "Morning Route",
    "last_latitude": 18.525778,
    "last_longitude": 73.733243,
    "last_updated": "2025-11-23T08:30:00+05:30"
  }
]
```

**Use Case:** List all active shuttles for user selection.

---

### 3️⃣ Get Vehicle Location

**Endpoint:** `GET /api/client/vehicles/{vehicle_id}/location`

**Description:** Get real-time GPS location for a specific vehicle.

**Security:** Only works if vehicle has an active schedule.

**Parameters:**
- `vehicle_id` (path) - Integer, required

**Response Example:**
```json
{
  "vehicle_id": 1,
  "name": "Shuttle-01",
  "label": "Morning Route",
  "latitude": 18.523000,
  "longitude": 73.760000,
  "speed": 35.5,
  "course": 180,
  "timestamp": "2025-11-23T08:30:15Z",
  "valid": true,
  "ignition": true,
  "motion": true
}
```

**Use Case:** Track shuttle in real-time on a map.

**Error Responses:**
- `404` - Vehicle not found or not currently available
- `500` - GPS service error

---

### 4️⃣ Get Vehicle Status

**Endpoint:** `GET /api/client/vehicles/{vehicle_id}/status`

**Description:** Get operational status (battery, distance, etc.) for a vehicle.

**Security:** Only works if vehicle has an active schedule.

**Parameters:**
- `vehicle_id` (path) - Integer, required

**Response Example:**
```json
{
  "vehicle_id": 1,
  "name": "Shuttle-01",
  "ignition": true,
  "motion": true,
  "charge": false,
  "batteryLevel": 85,
  "totalDistance": 125000.5,
  "todayDistance": 45.3,
  "timestamp": "2025-11-23T08:30:15Z"
}
```

**Use Case:** Monitor vehicle health and operational status.

---

### 5️⃣ Get All Vehicle Locations

**Endpoint:** `GET /api/client/vehicles/locations/all`

**Description:** Get real-time locations for all available vehicles.

**Response Example:**
```json
[
  {
    "vehicle_id": 1,
    "name": "Shuttle-01",
    "label": "Morning Route",
    "latitude": 18.523000,
    "longitude": 73.760000,
    "speed": 35.5,
    "course": 180,
    "timestamp": "2025-11-23T08:30:15Z",
    "valid": true,
    "ignition": true,
    "motion": true
  },
  {
    "vehicle_id": 2,
    "name": "Shuttle-02",
    "label": "Evening Route",
    "latitude": 18.518468,
    "longitude": 73.765785,
    "speed": 0.0,
    "course": 0,
    "timestamp": "2025-11-23T08:30:10Z",
    "valid": true,
    "ignition": false,
    "motion": false
  }
]
```

**Use Case:** Display all active shuttles on a map simultaneously.

**Behavior:** Skips vehicles that fail to fetch GPS data (no error thrown).

---

### 6️⃣ Get ETA to Upcoming Stops

**Endpoint:** `GET /api/client/eta/upcoming`

**Description:** Get estimated time of arrival to upcoming stops for a vehicle on its route.

**Security:** Only works if vehicle has an active schedule.

**Parameters:**
- `vehicle_id` (query) - Integer, required - Vehicle ID
- `mode` (query) - String, optional - Travel mode: `"driving"` or `"walking"` (default: `"driving"`)
- `max_stops` (query) - Integer, optional - Number of upcoming stops (default: 2, max: 10)

**Response Example:**
```json
{
  "vehicle_id": 1,
  "timestamp_utc": "2025-11-23T03:00:00Z",
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

**Response Fields:**
- `eta_seconds` - Time to arrival in seconds
- `distance_meters` - Distance to stop in meters
- `status` - `"upcoming"`, `"arriving"` (< 100m), `"off_route"`, or `"skipped"`
- `source` - `"osrm"` (routing engine) or `"estimate_fallback"` (straight-line estimate)
- `stale` - `true` if location data is older than 60 seconds
- `off_route` - `true` if vehicle is > 500m from expected route

**Use Case:** Show users "Your shuttle arrives in 5 minutes" notifications.

**Direction-Aware Filtering:** Uses the scheduled route direction to correctly identify which stops are upcoming vs. already passed.

**Error Responses:**
- `404` - Vehicle not found or not currently available
- `500` - Unable to fetch vehicle location
- `503` - OSRM service unavailable (falls back to estimates)

---

### 7️⃣ Calculate ETA by Coordinates

**Endpoint:** `POST /api/client/eta/by-coordinates`

**Description:** Calculate ETA from an origin to arbitrary target coordinates.

**Request Body:**
```json
{
  "origin": {
    "lat": 18.525778,
    "lon": 73.733243
  },
  "targets": [
    {
      "id": "stop1",
      "lat": 18.518468,
      "lon": 73.765785
    },
    {
      "id": "stop2",
      "lat": 18.507034,
      "lon": 73.805283
    }
  ],
  "mode": "driving"
}
```

**Response Example:**
```json
{
  "timestamp_utc": "2025-11-23T03:00:00Z",
  "origin": {
    "lat": 18.525778,
    "lon": 73.733243
  },
  "mode": "driving",
  "targets": [
    {
      "id": "stop1",
      "lat": 18.518468,
      "lon": 73.765785,
      "eta_seconds": 450,
      "distance_meters": 3800,
      "source": "osrm",
      "osrm_request": "http://router.project-osrm.org/route/v1/driving/..."
    },
    {
      "id": "stop2",
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

**Use Case:** Calculate travel times for custom locations, debugging, or route planning.

**Performance:** Uses OSRM Table API for multiple targets (more efficient than individual route calls).

---

## 🔐 Admin Endpoints

All admin endpoints require **JWT authentication**. Include the token in the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

### Authentication Endpoints

#### Login

**Endpoint:** `POST /api/admin/login`

**Request Body:**
```json
{
  "username": "admin",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**
- `401` - Incorrect username or password

---

#### Logout

**Endpoint:** `POST /api/admin/logout`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "message": "Logged out successfully",
  "detail": "Please delete the JWT token from client storage"
}
```

**Note:** JWT tokens are stateless. Logout is handled client-side by deleting the token.

---

### Admin Management (Super Admin Only)

#### Create Admin

**Endpoint:** `POST /api/admin/admins`

**Headers:** `Authorization: Bearer <super_admin_token>`

**Request Body:**
```json
{
  "username": "new_admin",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "id": 2,
  "username": "new_admin",
  "is_active": true,
  "created_at": "2025-11-23T08:00:00+05:30",
  "updated_at": null
}
```

---

#### List All Admins

**Endpoint:** `GET /api/admin/admins`

**Headers:** `Authorization: Bearer <super_admin_token>`

**Response:**
```json
[
  {
    "id": 1,
    "username": "admin",
    "is_active": true,
    "created_at": "2025-11-20T10:00:00+05:30"
  },
  {
    "id": 2,
    "username": "new_admin",
    "is_active": true,
    "created_at": "2025-11-23T08:00:00+05:30"
  }
]
```

---

#### Delete Admin

**Endpoint:** `DELETE /api/admin/admins/{admin_id}`

**Headers:** `Authorization: Bearer <super_admin_token>`

**Response:**
```json
{
  "message": "Admin deleted successfully"
}
```

---

#### Update Admin Status

**Endpoint:** `PATCH /api/admin/admins/{admin_id}/status`

**Headers:** `Authorization: Bearer <super_admin_token>`

**Query Parameters:**
- `is_active` (query) - Boolean, required

**Response:**
```json
{
  "message": "Admin activated successfully"
}
```

---

### Vehicle Management (All Admins)

#### List All Vehicles

**Endpoint:** `GET /api/admin/vehicles`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
[
  {
    "vehicle_id": 1,
    "name": "Shuttle-01",
    "label": "Morning Route",
    "device_unique_id": "IMEI123456789",
    "access_token": "your_gps_access_token",
    "is_active": true,
    "last_latitude": 18.525778,
    "last_longitude": 73.733243,
    "last_updated": "2025-11-23T08:30:00+05:30",
    "created_at": "2025-11-20T10:00:00+05:30",
    "updated_at": null
  }
]
```

**Note:** Admin view includes sensitive data like `access_token`.

---

#### Get Vehicle Details

**Endpoint:** `GET /api/admin/vehicles/{vehicle_id}`

**Headers:** `Authorization: Bearer <token>`

---

#### Create Vehicle

**Endpoint:** `POST /api/admin/vehicles`

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "name": "Shuttle-02",
  "label": "Evening Route",
  "device_unique_id": "IMEI987654321",
  "access_token": "gps_device_token_here",
  "is_active": true
}
```

**Response:** `201 Created` with vehicle details

**Validation:** Automatically tests GPS connection before creating vehicle.

---

#### Update Vehicle

**Endpoint:** `PUT /api/admin/vehicles/{vehicle_id}`

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "name": "Shuttle-02-Updated",
  "label": "Evening Express",
  "access_token": "new_token_if_changed",
  "is_active": true
}
```

---

#### Delete Vehicle

**Endpoint:** `DELETE /api/admin/vehicles/{vehicle_id}`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "message": "Vehicle deleted successfully"
}
```

**Cascade:** Deletes all associated schedules.

---

#### Test GPS Connection

**Endpoint:** `POST /api/admin/vehicles/{vehicle_id}/test`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "message": "GPS connection successful",
  "vehicle_id": 1,
  "device_data": {
    "latitude": 18.525778,
    "longitude": 73.733243,
    "speed": 0.0,
    "valid": true
  }
}
```

**Use Case:** Verify GPS device is working correctly.

---

#### Toggle Vehicle Active Status

**Endpoint:** `PATCH /api/admin/vehicles/{vehicle_id}/active`

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `active` (query) - Boolean, required

**Response:**
```json
{
  "message": "Vehicle activated"
}
```

---

### Schedule Management (All Admins)

#### List All Schedules

**Endpoint:** `GET /api/admin/schedules`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
[
  {
    "id": 1,
    "vehicle_id": 1,
    "start_time": "2025-11-23T07:00:00+05:30",
    "from_location": "Campus",
    "to_location": "FC Road",
    "is_active": true,
    "created_at": "2025-11-20T10:00:00+05:30",
    "updated_at": null
  }
]
```

---

#### Get Schedule Details

**Endpoint:** `GET /api/admin/schedules/{schedule_id}`

**Headers:** `Authorization: Bearer <token>`

---

#### Get Vehicle Schedules

**Endpoint:** `GET /api/admin/vehicles/{vehicle_id}/schedules`

**Headers:** `Authorization: Bearer <token>`

**Response:** List of schedules for the specified vehicle

---

#### Create Schedule

**Endpoint:** `POST /api/admin/schedules`

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "vehicle_id": 1,
  "start_time": "2025-11-23T07:00:00+05:30",
  "from_location": "Campus",
  "to_location": "FC Road",
  "is_active": true
}
```

**Response:** `201 Created` with schedule details

**Validation:** Verifies vehicle exists before creating schedule.

---

#### Update Schedule

**Endpoint:** `PUT /api/admin/schedules/{schedule_id}`

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "start_time": "2025-11-23T08:00:00+05:30",
  "from_location": "FC Road",
  "to_location": "Campus",
  "is_active": true
}
```

---

#### Delete Schedule

**Endpoint:** `DELETE /api/admin/schedules/{schedule_id}`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "message": "Schedule deleted successfully"
}
```

---

#### Toggle Schedule Status

**Endpoint:** `PATCH /api/admin/schedules/{schedule_id}/active`

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `is_active` (query) - Boolean, required

**Response:**
```json
{
  "message": "Schedule activated successfully"
}
```

**Use Case:** Quickly enable/disable routes without deleting them.

---

## 🔒 Security Model

### Visibility Control

The API implements a **two-tier visibility system**:

#### Tier 1: Vehicle Active Status
- `vehicle.is_active = false` → Vehicle hidden from all public endpoints

#### Tier 2: Schedule Active Status
- `schedule.is_active = false` → Vehicle hidden from public endpoints, even if vehicle itself is active

**Result:** Public endpoints only show vehicles that are:
1. Active (`vehicle.is_active = true`), AND
2. Have at least one active schedule (`schedule.is_active = true`)

### Security Checks in Client Endpoints

All client endpoints that accept a `vehicle_id` parameter implement the following check:

```python
# Get all active schedules
active_schedules = crud.get_active_schedules(db)
vehicle_ids_with_active_schedules = {s.vehicle_id for s in active_schedules}

# Reject if vehicle doesn't have active schedule
if vehicle_id not in vehicle_ids_with_active_schedules:
    raise HTTPException(status_code=404, detail="Vehicle not found or not currently available")
```

**Benefits:**
- ✅ Users cannot probe for vehicle IDs
- ✅ Admins control exactly what is publicly visible
- ✅ No information leakage (same error for non-existent and inactive vehicles)
- ✅ Consistent across all client endpoints

---

## ⚠️ Error Responses

### Standard Error Format

```json
{
  "detail": "Error message description"
}
```

### Common HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| `200` | Success | Data retrieved successfully |
| `201` | Created | Resource created successfully |
| `400` | Bad Request | Invalid input data |
| `401` | Unauthorized | Invalid or missing authentication token |
| `403` | Forbidden | Valid token but insufficient permissions |
| `404` | Not Found | Resource doesn't exist or not available |
| `500` | Internal Server Error | GPS API failure, database error |
| `503` | Service Unavailable | OSRM routing service down |

---

## 🚀 Quick Start Examples

### For Frontend Developers

#### Fetch Active Shuttles
```javascript
const response = await fetch('http://localhost:8000/api/client/vehicles');
const vehicles = await response.json();
console.log('Active shuttles:', vehicles);
```

#### Track a Shuttle in Real-Time
```javascript
async function trackShuttle(vehicleId) {
  const response = await fetch(
    `http://localhost:8000/api/client/vehicles/${vehicleId}/location`
  );
  const location = await response.json();
  
  // Update map marker
  updateMapMarker(location.latitude, location.longitude);
  console.log(`Shuttle at ${location.latitude}, ${location.longitude}`);
}

// Poll every 5 seconds
setInterval(() => trackShuttle(1), 5000);
```

#### Get ETA to Stops
```javascript
const response = await fetch(
  'http://localhost:8000/api/client/eta/upcoming?vehicle_id=1&max_stops=3'
);
const eta = await response.json();

eta.upcoming_stops.forEach(stop => {
  const minutes = Math.round(stop.eta_seconds / 60);
  console.log(`${stop.name}: ${minutes} minutes`);
});
```

### For Admin Panel Developers

#### Login
```javascript
const response = await fetch('http://localhost:8000/api/admin/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'password'
  })
});
const { access_token } = await response.json();
localStorage.setItem('token', access_token);
```

#### Create Vehicle
```javascript
const token = localStorage.getItem('token');

const response = await fetch('http://localhost:8000/api/admin/vehicles', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    name: 'Shuttle-03',
    label: 'Night Route',
    device_unique_id: 'IMEI123456789',
    access_token: 'gps_token_here',
    is_active: true
  })
});

const vehicle = await response.json();
console.log('Created vehicle:', vehicle);
```

---

## 📊 Route Configuration

### Fixed Stations

| Station | Coordinates |
|---------|-------------|
| Campus | `18.525778, 73.733243` |
| Bavdhan Guard post | `18.518468, 73.765785` |
| FC Road | `18.522335, 73.843739` |
| Vanaz Station | `18.507034, 73.805283` |

### Predefined Routes

| Route ID | Direction | Stops (in order) |
|----------|-----------|------------------|
| `campus-fcroad` | Campus → FC Road | Campus → Bavdhan Guard post → Vanaz Station → FC Road |
| `fcroad-campus` | FC Road → Campus | FC Road → Vanaz Station → Bavdhan Guard post → Campus |
| `campus-bavdhan` | Campus → Bavdhan | Campus → Bavdhan Guard post |
| `bavdhan-campus` | Bavdhan → Campus | Bavdhan Guard post → Campus |

**Note:** Routes are direction-aware for accurate ETA calculations.

---

## 🛠️ Technical Details

### Technologies Used
- **Framework:** FastAPI 0.104.1
- **Database:** SQLite (SQLAlchemy ORM)
- **Authentication:** JWT (python-jose)
- **Password Hashing:** bcrypt
- **GPS Integration:** EERA GPS House API
- **Routing:** OSRM (Open Source Routing Machine)
- **HTTP Client:** httpx (async)

### Performance Features
- ✅ OSRM response caching (60-second TTL)
- ✅ Efficient batch routing (OSRM Table API)
- ✅ Async/await for non-blocking I/O
- ✅ Connection pooling for database
- ✅ Fallback estimates when OSRM unavailable

### Rate Limiting & Quotas
- **OSRM Public Server:** Best-effort, shared by all users
- **Max Stops per ETA Request:** 10
- **Cache TTL:** 60 seconds
- **Token Expiry:** 7 days (configurable)

---

## 📞 Support & Resources

- **API Documentation:** http://localhost:8000/docs
- **Environment Setup:** See `ENV_CONFIG.md`
- **OSRM Guide:** See `OSRM.md`
- **Quick Start:** See `ETA_QUICK_START.md`

---

**Document Version:** 1.0.0  
**Last Updated:** November 23, 2025
