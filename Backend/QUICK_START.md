# 🚀 Shuttle Tracker Backend - Quick Start Guide

## ✅ What Was Created

A complete multi-vehicle GPS tracking backend with:

### 📁 Architecture
```
Backend/
├── app/                          # Main application directory
│   ├── main.py                   # FastAPI app entry point
│   ├── api/
│   │   ├── admin/               # Admin endpoints (secured)
│   │   │   ├── routes_admin.py
│   │   │   └── controllers_admin.py
│   │   └── client/              # Public endpoints
│   │       ├── routes_client.py
│   │       └── controllers_client.py
│   ├── core/
│   │   ├── config.py            # Configuration settings
│   │   └── security.py          # JWT authentication
│   ├── db/
│   │   ├── models.py            # Vehicle database model
│   │   ├── session.py           # DB connection
│   │   └── crud.py              # Database operations
│   ├── services/
│   │   └── gps.py               # EERA GPS API integration
│   └── schemas/
│       └── vehicle.py           # Request/response models
├── requirements.txt
├── eera_api.md
└── README.md
```

## 🎯 Key Features

### For Admins (Secured with JWT)
✅ Add/remove vehicles from tracking system
✅ Manage vehicle visibility (show/hide from clients)
✅ Test GPS connections
✅ Update vehicle information
✅ View all vehicle data including GPS tokens

### For Clients (Public - No Auth)
✅ View list of available vehicles
✅ Get real-time location for any vehicle
✅ Check vehicle status (ignition, battery, motion)
✅ View all vehicles on map

## 🏃 How to Run

```bash
# Install dependencies (already done)
cd Backend
uv add -r requirements.txt

# Start server
cd app
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Server URL**: http://localhost:8000
**API Docs**: http://localhost:8000/docs

## 📱 API Endpoints Overview

### Admin Endpoints (Require JWT Token)

**Login:**
```bash
POST /api/admin/login
Body: {"username": "admin", "password": "admin123"}
```

**Add Vehicle:**
```bash
POST /api/admin/vehicles
Headers: Authorization: Bearer <token>
Body: {
  "name": "Shuttle A",
  "label": "Main Route",
  "device_unique_id": "356218600094070",
  "access_token": "YOUR_GPS_TOKEN",
  "is_active": true,
  "is_visible": true
}
```

**List All Vehicles:**
```bash
GET /api/admin/vehicles
Headers: Authorization: Bearer <token>
```

**Test GPS Connection:**
```bash
POST /api/admin/vehicles/{id}/test
Headers: Authorization: Bearer <token>
```

### Client Endpoints (Public - No Token Needed)

**Get Available Vehicles:**
```bash
GET /api/client/vehicles
```

**Get Vehicle Location:**
```bash
GET /api/client/vehicles/{id}/location
```

**Get Vehicle Status:**
```bash
GET /api/client/vehicles/{id}/status
```

**Get All Vehicle Locations:**
```bash
GET /api/client/vehicles/locations/all
```

## 🔐 Security Model

```
┌─────────────────────────────────────────────────┐
│  Admin Dashboard (with JWT)                     │
│  • Manages which vehicles are visible           │
│  • Has access to GPS tokens                     │
│  • Full CRUD operations                         │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  Backend Database                                │
│  • Stores vehicle info + GPS tokens             │
│  • Only visible vehicles shown to clients       │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  Client App (Public - No Auth)                  │
│  • Sees only active & visible vehicles          │
│  • Gets live location data                      │
│  • NO access to GPS tokens                      │
└─────────────────────────────────────────────────┘
```

## 📊 Database

**SQLite** (auto-created on first run)
Location: `Backend/app/shuttle_tracker.db`

**Vehicle Table:**
- id (primary key)
- name (display name)
- label (optional description)
- device_unique_id (IMEI - unique)
- access_token (GPS token - SECURE)
- is_active (admin control)
- is_visible (show to clients)
- last_latitude, last_longitude (cached)
- timestamps

## 🧪 Testing the System

### 1. Start Server
```bash
cd Backend/app
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Login as Admin
Open http://localhost:8000/docs
- Click on `/api/admin/login`
- Use: `admin` / `admin123`
- Copy the access_token

### 3. Add a Vehicle
- Click on `/api/admin/vehicles` POST
- Click "Authorize" button (top right)
- Paste token
- Add vehicle with real GPS token

### 4. Test Client Access
- Open `/api/client/vehicles` GET
- See your vehicle in the list
- Try `/api/client/vehicles/1/location`

## 🔄 Workflow Example

```
1. Admin logs in → Gets JWT token
2. Admin adds vehicle with GPS token → Stored in DB
3. Admin sets vehicle as visible → is_visible=true
4. Client app calls /api/client/vehicles → Sees the vehicle
5. Client calls /api/client/vehicles/1/location → Gets live GPS data
6. Backend fetches from EERA API using stored token
7. Client receives location (but never sees the token)
```

## ⚙️ Configuration

Default settings in `app/core/config.py`:

```python
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # Change this!
SECRET_KEY = "your-secret-key-change-in-production"
DATABASE_URL = "sqlite:///./shuttle_tracker.db"
```

**For Production**: Create `.env` file in `Backend/` directory

## 🎨 Next Steps

1. **Change admin password** in config.py
2. **Add your first vehicle** via admin API
3. **Test client endpoints** to see live data
4. **Build admin dashboard** (React/Vue/etc)
5. **Build client app** to show vehicle locations on map

## 📖 Full Documentation

See `Backend/README.md` for complete API reference and examples.
