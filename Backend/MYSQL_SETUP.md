# MySQL Database Setup Guide

## 🔧 Prerequisites
- MySQL Server installed on your machine
- MySQL running on localhost

## 📝 Setup Steps

### 1. Create Database

Open MySQL command line or MySQL Workbench and run:

```sql
CREATE DATABASE shuttle_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Update Configuration

Edit `Backend/app/core/config.py` and update the DATABASE_URL:

```python
# Default (no password):
DATABASE_URL = "mysql+pymysql://root:@localhost/shuttle_tracker"

# With password:
DATABASE_URL = "mysql+pymysql://root:your_password@localhost/shuttle_tracker"

# Custom host/port:
DATABASE_URL = "mysql+pymysql://username:password@localhost:3306/shuttle_tracker"
```

### 3. Verify MySQL Connection

Create a `.env` file in `Backend/` directory (optional):

```env
# MySQL Configuration
DATABASE_URL=mysql+pymysql://root:@localhost/shuttle_tracker

# Admin Credentials (CHANGE THESE!)
SECRET_KEY=your-super-secret-key-min-32-chars
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# EERA GPS API
EERA_BASE_URL=https://track.eeragpshouse.com
EERA_ENDPOINT=/api/middleMan/getDeviceInfo
```

### 4. Install Dependencies

```bash
cd Backend
uv add pymysql cryptography
```

### 5. Start the Server

The database tables will be created automatically on first run!

```bash
cd Backend/app
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📊 Database Schema

The following table will be auto-created:

```sql
CREATE TABLE vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Display Info
    name VARCHAR(100) NOT NULL,
    label VARCHAR(255),
    route_destination VARCHAR(255),           -- "Campus", "FC Road", etc.
    
    -- Device Info (Secure)
    device_unique_id VARCHAR(50) UNIQUE NOT NULL,
    access_token VARCHAR(500) NOT NULL,
    
    -- Status Flags
    is_active BOOLEAN DEFAULT TRUE,
    is_visible BOOLEAN DEFAULT TRUE,
    
    -- Cached Location (Updated on each GPS fetch)
    last_latitude FLOAT,
    last_longitude FLOAT,
    last_updated DATETIME,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_name (name),
    INDEX idx_device_id (device_unique_id)
);
```

## 🧪 Test MySQL Connection

You can test the connection using this Python script:

```python
from sqlalchemy import create_engine

# Update with your credentials
DATABASE_URL = "mysql+pymysql://root:@localhost/shuttle_tracker"

try:
    engine = create_engine(DATABASE_URL)
    connection = engine.connect()
    print("✅ MySQL connection successful!")
    connection.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

## 🔍 Verify Tables Were Created

After starting the server, check in MySQL:

```sql
USE shuttle_tracker;
SHOW TABLES;
DESCRIBE vehicles;
```

You should see the `vehicles` table with all columns.

## 🐛 Troubleshooting

### Error: "Can't connect to MySQL server"
- Verify MySQL is running: `mysql --version`
- Check port: MySQL usually runs on 3306

### Error: "Access denied for user"
- Update password in DATABASE_URL
- Grant privileges: `GRANT ALL PRIVILEGES ON shuttle_tracker.* TO 'root'@'localhost';`

### Error: "Unknown database 'shuttle_tracker'"
- Create the database first: `CREATE DATABASE shuttle_tracker;`

### Error: "No module named 'pymysql'"
- Install: `uv add pymysql cryptography`

## 📋 Next Steps

1. ✅ Create MySQL database
2. ✅ Update DATABASE_URL in config
3. ✅ Start the server (tables auto-create)
4. 🎯 Login as admin and add your first vehicle!

## 🔐 Admin First Login

```bash
# Login
POST http://localhost:8000/api/admin/login
Body: {"username": "admin", "password": "admin123"}

# Add vehicle with route
POST http://localhost:8000/api/admin/vehicles
Headers: Authorization: Bearer <token>
Body: {
  "name": "Shuttle A",
  "label": "Morning Route",
  "route_destination": "Campus",
  "device_unique_id": "356218600094070",
  "access_token": "YOUR_EERA_GPS_TOKEN",
  "is_active": true,
  "is_visible": true
}
```

The admin can update `route_destination` anytime using PUT endpoint!
