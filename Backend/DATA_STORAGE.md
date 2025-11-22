# 📦 Data Storage Architecture

## Overview
The system stores different types of data in different locations for security and organization.

---

## 🗄️ Database Storage (SQLite)

**Location**: `Backend/app/shuttle_tracker.db`

### Vehicles Table
Stores ALL vehicle information including GPS access tokens (SECURE):

```sql
CREATE TABLE vehicles (
    -- Identity
    id                   INTEGER      PRIMARY KEY AUTOINCREMENT
    
    -- Display Information (visible to clients)
    name                 VARCHAR      NOT NULL    -- "Shuttle A", "Bus 1"
    label                VARCHAR      NULLABLE    -- Optional description
    route_destination    VARCHAR      NULLABLE    -- "Campus", "FC Road", etc.
    
    -- Device Information (ADMIN ONLY - NEVER exposed to clients)
    device_unique_id     VARCHAR      NOT NULL    -- IMEI number (unique)
    access_token         VARCHAR      NOT NULL    -- EERA GPS API token (SECURE!)
    
    -- Status Flags (admin control)
    is_active            BOOLEAN      NOT NULL    -- Vehicle enabled/disabled
    is_visible           BOOLEAN      NOT NULL    -- Show to clients or not
    
    -- Cached Location (updated after each GPS fetch)
    last_latitude        FLOAT        NULLABLE    -- Last known latitude
    last_longitude       FLOAT        NULLABLE    -- Last known longitude
    last_updated         DATETIME     NULLABLE    -- When cache was updated
    
    -- Metadata
    created_at           DATETIME     DEFAULT NOW
    updated_at           DATETIME     ON UPDATE
);
```

### What's Stored in Database:

✅ **Vehicle basic info** (name, label, route)
✅ **GPS device IMEI** (device_unique_id)
✅ **EERA API access tokens** (SECURE - never sent to clients)
✅ **Vehicle status** (active, visible)
✅ **Cached location** (last known position)
✅ **Timestamps** (when created, updated)

---

## 📝 Environment Variables (.env file)

**Location**: `Backend/.env`

### What's Stored:

```env
# Authentication Secrets
SECRET_KEY=fKTbT-OJP8SRBA_LGZlAxIN8C4otwbPGoor9seN6n8w  # JWT signing key
ALGORITHM=HS256                                          # JWT algorithm
ACCESS_TOKEN_EXPIRE_MINUTES=10080                        # Token lifetime

# Admin Login Credentials
ADMIN_USERNAME=admin                                     # Admin username
ADMIN_PASSWORD=admin123                                  # Admin password (plaintext)

# API Configuration
EERA_BASE_URL=https://track.eeragpshouse.com            # GPS API URL
EERA_ENDPOINT=/api/middleMan/getDeviceInfo              # GPS API endpoint

# Database
DATABASE_URL=sqlite:///./shuttle_tracker.db             # Database connection

# CORS
CORS_ORIGINS=*                                          # Allowed origins
```

---

## 🔑 JWT Tokens (In Memory / Client Side)

### Admin Access Tokens
**NOT stored in database** - created on-the-fly during login

**Flow**:
1. Admin logs in with username/password (from `.env`)
2. Backend creates JWT token using `SECRET_KEY` (from `.env`)
3. Token sent to admin (valid for `ACCESS_TOKEN_EXPIRE_MINUTES`)
4. Admin stores token in browser/app (client-side)
5. Admin sends token with each request (Authorization header)
6. Backend verifies token using `SECRET_KEY`

**Example JWT Token**:
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTczMjg5NzIwMH0.signature
```

**What's in the token**:
- `sub`: username ("admin")
- `exp`: expiration timestamp
- Signature (signed with SECRET_KEY)

---

## 📊 Data Storage Summary

| Data Type | Storage Location | Access Level |
|-----------|------------------|--------------|
| **Vehicle GPS Tokens** | Database (`access_token` column) | Admin only |
| **Vehicle Names/Routes** | Database (`name`, `route_destination`) | Public (clients) |
| **Device IMEI** | Database (`device_unique_id`) | Admin only |
| **Cached Location** | Database (`last_latitude`, `last_longitude`) | Public (clients) |
| **Admin Credentials** | `.env` file | Server only |
| **JWT Secret Key** | `.env` file | Server only |
| **JWT Tokens** | Client-side (browser/app) | Admin session |
| **Live GPS Data** | EERA API (not stored) | Fetched on-demand |

---

## 🔒 Security Model

### What Admin Can See:
```json
{
  "id": 1,
  "name": "Shuttle A",
  "device_unique_id": "356218600094070",
  "access_token": "BASE64_EERA_TOKEN",  // VISIBLE TO ADMIN
  "route_destination": "Campus",
  "is_active": true,
  "is_visible": true
}
```

### What Clients See:
```json
{
  "id": 1,
  "name": "Shuttle A",
  "route_destination": "Campus",
  "last_latitude": 18.444,
  "last_longitude": 73.911
  // NO access_token, NO device_unique_id
}
```

---

## 📂 File Locations

```
Backend/
├── .env                           ← Admin credentials, JWT secret, API URLs
├── app/
│   ├── shuttle_tracker.db        ← Vehicle data + GPS tokens (SECURE)
│   └── core/
│       └── config.py             ← Reads from .env
```

---

## 🔄 Data Flow Example

### Admin Adds a Vehicle:

1. **Admin logs in**:
   - Sends username/password (from `.env`)
   - Receives JWT token (signed with `SECRET_KEY`)

2. **Admin adds vehicle**:
   ```json
   POST /api/admin/vehicles
   Headers: Authorization: Bearer <JWT_TOKEN>
   Body: {
     "name": "Shuttle A",
     "device_unique_id": "356218600094070",
     "access_token": "EERA_GPS_TOKEN_HERE",  // Stored in database
     "route_destination": "Campus"
   }
   ```

3. **Stored in database**:
   - All fields saved to `vehicles` table
   - `access_token` encrypted in database

4. **Client requests location**:
   ```json
   GET /api/client/vehicles/1/location
   // No authentication needed
   ```

5. **Backend fetches GPS data**:
   - Reads `access_token` from database
   - Calls EERA API with token
   - Returns location to client (WITHOUT the token)

---

## 🛡️ What's NOT Stored

❌ **User session data** - JWT tokens are stateless
❌ **GPS history** - Only current/cached location stored
❌ **Admin password (hashed)** - Stored in `.env` as plaintext (simple auth)
❌ **Client authentication** - Clients don't need to log in

---

## 💡 Key Points

1. **GPS Tokens**: Stored in database, NEVER exposed to clients
2. **Admin Credentials**: In `.env` file, used for login only
3. **JWT Secret**: In `.env` file, used to sign/verify tokens
4. **Live Location**: Fetched from EERA API on-demand, not stored permanently
5. **Cached Location**: Stored in database for quick preview/fallback

This separation ensures clients can track vehicles without accessing sensitive GPS tokens!
