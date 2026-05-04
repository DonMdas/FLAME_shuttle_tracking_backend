# Shuttle Tracker Backend API

A comprehensive FastAPI backend for a multi-vehicle shuttle tracking system with separate admin and client interfaces.

## 📋 Overview

This backend manages GPS tracking for multiple shuttle vehicles, providing:

- **Admin Dashboard API**: Secure endpoints for managing vehicles, configuring visibility, and testing GPS connections
- **Client App API**: Public endpoints for viewing available vehicles and their real-time locations
- **GPS Proxy Service**: Securely fetches live GPS data from EERA tracking platform without exposing tokens

## 🏗️ Architecture

```
Backend/
├── app/
│   ├── main.py                      # FastAPI application entry point
│   │
│   ├── api/
│   │   ├── admin/
│   │   │   ├── routes_admin.py      # Admin routes (JWT secured)
│   │   │   └── controllers_admin.py # Admin business logic
│   │   │
│   │   └── client/
│   │       ├── routes_client.py     # Authenticated client routes
│   │       └── controllers_client.py # Client business logic
│   │
│   ├── core/
│   │   ├── config.py                # Application configuration
│   │   └── security.py              # JWT authentication
│   │
│   ├── db/
│   │   ├── models.py                # SQLAlchemy models
│   │   ├── session.py               # Database session management
│   │   └── crud.py                  # Database operations
│   │
│   ├── services/
│   │   └── gps.py                   # EERA GPS API integration
│   │
│   └── schemas/
│       └── vehicle.py               # Pydantic validation models
│
├── requirements.txt
├── eera_api.md                      # EERA API documentation
└── README.md
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd Backend
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)

Create a `.env` file in the Backend directory:

```env
SECRET_KEY=your-super-secret-key-change-this
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
DATABASE_URL=sqlite:///./shuttle_tracker.db
DEBUG=True
```

### 3. Run the Server

```bash
# From Backend directory
cd app
python main.py
```

Or using uvicorn directly:

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Reference docs:
- [Client API documentation](copilot_files/API_DOCUMENTATION_CLIENT.md)
- [System overview and flow](copilot_files/SYSTEM_OVERVIEW_AND_FLOW.md)

## 🔐 Admin API Endpoints

All admin endpoints require JWT authentication via Bearer token.

### Authentication

**POST** `/api/admin/login`
- Login with admin credentials
- Returns JWT access token

```json
{
  "username": "admin",
  "password": "admin123"
}
```

### Vehicle Management

**GET** `/api/admin/vehicles`
- List all vehicles (including sensitive data)

**POST** `/api/admin/vehicles`
- Add a new vehicle
- Validates GPS token before creating

**GET** `/api/admin/vehicles/{id}`
- Get vehicle details

**PUT** `/api/admin/vehicles/{id}`
- Update vehicle information

**DELETE** `/api/admin/vehicles/{id}`
- Remove vehicle from system

### Vehicle Control

**POST** `/api/admin/vehicles/{id}/test`
- Test GPS connection for a vehicle

**PATCH** `/api/admin/vehicles/{id}/visibility`
- Toggle vehicle visibility for clients

**PATCH** `/api/admin/vehicles/{id}/active`
- Toggle vehicle active status

## 🌐 Client API Endpoints

All client endpoints require authentication. The authenticated user role determines which schedules and vehicles are visible.

**GET** `/api/client/vehicles`
- Get list of available vehicles for the authenticated role

**GET** `/api/client/vehicles/{id}/location`
- Get real-time location for specific vehicle

**GET** `/api/client/vehicles/{id}/status`
- Get operational status (ignition, battery, distances)

**GET** `/api/client/vehicles/locations/all`
- Get live locations for all vehicles (for map view)

**GET** `/api/client/schedules`
- Get role-filtered schedules with vehicle details

**GET** `/api/client/schedules/today`
- Get role-filtered schedules running today

**GET** `/api/client/routes/{route_id}/stops`
- Get ordered stops for a route

**GET** `/api/client/eta/upcoming`
- Get ETA for upcoming stops of a vehicle

**POST** `/api/client/eta/by-coordinates`
- Calculate ETA from an origin to multiple coordinates

**POST** `/api/client/feedback/`
- Submit client feedback

**GET** `/api/client/feedback/my-history`
- Read the authenticated user's feedback history

**PATCH** `/api/client/feedback/{feedback_id}`
- Update own feedback within the allowed window

**DELETE** `/api/client/feedback/{feedback_id}`
- Delete own feedback within the allowed window

## 🔧 Usage Examples

### Admin: Add a New Vehicle

```bash
# 1. Login and get token
curl -X POST http://localhost:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Response: {"access_token": "eyJ...", "token_type": "bearer"}

# 2. Add vehicle
curl -X POST http://localhost:8000/api/admin/vehicles \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Shuttle A",
    "label": "Main Campus Route",
    "device_unique_id": "356218600094070",
    "access_token": "BASE64_GPS_TOKEN",
    "is_active": true,
    "is_visible": true
  }'
```

### Client: Get Available Vehicles

```bash
# No authentication needed
curl http://localhost:8000/api/client/vehicles
```

### Client: Track a Vehicle

```bash
# Get live location
curl http://localhost:8000/api/client/vehicles/1/location

# Response example:
{
  "vehicle_id": 1,
  "name": "Shuttle A",
  "label": "Main Campus Route",
  "latitude": 18.4439288888889,
  "longitude": 73.9106077777778,
  "speed": 45.5,
  "course": 213,
  "timestamp": "2025-11-22T11:31:54.062+00:00",
  "valid": true,
  "ignition": true,
  "motion": true
}
```

## 🗄️ Database Schema

### Vehicle Model

- `id`: Primary key
- `name`: Display name (e.g., "Shuttle A")
- `label`: Optional description
- `device_unique_id`: GPS device IMEI (unique)
- `access_token`: EERA API token (secured, not exposed to clients)
- `is_active`: Admin control flag
- `is_visible`: Show to clients or not
- `last_latitude`, `last_longitude`: Cached location
- `created_at`, `updated_at`: Timestamps

## 🔒 Security Features

✅ **JWT Authentication**: Admin endpoints protected with Bearer tokens  
✅ **Token Isolation**: GPS device tokens never exposed to client apps  
✅ **Role Separation**: Clear boundary between admin and public endpoints  
✅ **CORS Configured**: Ready for frontend integration  
✅ **Password Hashing**: Bcrypt for credential storage (production ready)

## 🛠️ Configuration

Edit `app/core/config.py` or use environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | JWT signing key |
| `ADMIN_USERNAME` | `admin` | Default admin username |
| `ADMIN_PASSWORD` | `admin123` | Default admin password |
| `DATABASE_URL` | `sqlite:///./shuttle_tracker.db` | Database connection |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | JWT expiration |
| `EERA_BASE_URL` | `https://track.eeragpshouse.com` | GPS API base URL |

## 📦 Database Initialization

The database is automatically created on first run. Tables are created using SQLAlchemy on startup.

To reset the database:
```bash
rm app/shuttle_tracker.db
cd app
python main.py
```

## 🚦 Development vs Production

**Development** (current setup):
- SQLite database
- Simple admin authentication
- CORS allows all origins
- Debug mode enabled

**Production recommendations**:
- Use PostgreSQL or MySQL
- Implement proper user management with database
- Restrict CORS origins
- Set strong SECRET_KEY
- Use environment variables for sensitive data
- Enable HTTPS
- Add rate limiting
- Implement logging and monitoring

## 📝 Notes

- Only vehicles marked as `is_active=True` and `is_visible=True` appear in client endpoints
- GPS tokens are validated when adding a new vehicle
- Location data is cached in the database for performance
- The system supports unlimited vehicles

## 🐛 Troubleshooting

**Database errors**: Delete `app/shuttle_tracker.db` and restart  
**Authentication errors**: Check SECRET_KEY in config  
**GPS connection failed**: Verify EERA access token is valid  
**CORS errors**: Update `CORS_ORIGINS` in config  
**Import errors**: Make sure you're running from the `app/` directory
