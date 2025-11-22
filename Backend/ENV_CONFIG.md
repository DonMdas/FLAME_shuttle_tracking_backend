# Environment Variables Configuration

## 📋 Overview

All sensitive configuration and API settings are stored in the `.env` file located in the `Backend/` directory.

## 🔧 Setup

1. The `.env` file is already created in `Backend/.env`
2. Update the values as needed (especially `SECRET_KEY` and admin credentials)
3. Never commit `.env` to version control (already in `.gitignore`)

## 📝 Environment Variables

### Application Settings
```env
APP_NAME=Shuttle Tracker API
APP_VERSION=2.0.0
DEBUG=True
```

### Security & Authentication
```env
# SECRET_KEY: Used for JWT token signing (MUST be at least 32 characters)
SECRET_KEY=your-super-secret-key-change-this-min-32-characters-long

# ALGORITHM: JWT encoding algorithm
ALGORITHM=HS256

# ACCESS_TOKEN_EXPIRE_MINUTES: JWT token expiration time in minutes
# Default: 10080 (7 days)
ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

### Admin Credentials
```env
# Initial admin login credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

⚠️ **IMPORTANT**: Change these credentials in production!

### Database
```env
# SQLite database path (relative to app/ directory)
DATABASE_URL=sqlite:///./shuttle_tracker.db

# For MySQL (if switching):
# DATABASE_URL=mysql+pymysql://username:password@localhost/shuttle_tracker
```

### EERA GPS API
```env
# Base URL for EERA GPS tracking platform
EERA_BASE_URL=https://track.eeragpshouse.com

# API endpoint path
EERA_ENDPOINT=/api/middleMan/getDeviceInfo
```

### CORS Settings
```env
# Allowed origins for CORS (comma-separated or * for all)
CORS_ORIGINS=*

# Production example:
# CORS_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
```

## 🔒 Security Best Practices

### 1. Generate a Strong Secret Key

Use Python to generate a secure random key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output and update `SECRET_KEY` in `.env`

### 2. Change Admin Credentials

Update in `.env`:
```env
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_secure_password_here
```

### 3. Restrict CORS in Production

```env
# Development (allow all)
CORS_ORIGINS=*

# Production (specific domains only)
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

## 📂 File Location

```
Backend/
├── .env                    ← Environment variables here
├── app/
│   ├── main.py
│   └── core/
│       └── config.py       ← Reads from .env
```

## 🔄 How It Works

1. **`.env` file** contains all configuration
2. **`config.py`** reads values using `pydantic-settings`
3. **Rest of app** imports `settings` from `config.py`

```python
from core.config import settings

# Use anywhere in the app:
print(settings.SECRET_KEY)
print(settings.EERA_BASE_URL)
print(settings.ADMIN_USERNAME)
```

## 🚫 .gitignore

Make sure `.env` is in `.gitignore`:

```
# Environment files
.env
.env.local
.env.*.local
```

## 📋 Environment Variables Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | string | Shuttle Tracker API | Application name |
| `APP_VERSION` | string | 2.0.0 | API version |
| `DEBUG` | boolean | True | Debug mode |
| `SECRET_KEY` | string | *required* | JWT signing key (32+ chars) |
| `ALGORITHM` | string | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | 10080 | Token expiration (7 days) |
| `ADMIN_USERNAME` | string | admin | Admin login username |
| `ADMIN_PASSWORD` | string | admin123 | Admin login password |
| `DATABASE_URL` | string | sqlite:///./shuttle_tracker.db | Database connection |
| `EERA_BASE_URL` | string | https://track.eeragpshouse.com | GPS API base URL |
| `EERA_ENDPOINT` | string | /api/middleMan/getDeviceInfo | GPS API endpoint |
| `CORS_ORIGINS` | string | * | Allowed CORS origins |

## 🧪 Testing Configuration

To verify your configuration is loaded correctly:

```bash
cd Backend/app
python -c "from core.config import settings; print('Secret Key:', settings.SECRET_KEY[:10] + '...'); print('Admin User:', settings.ADMIN_USERNAME); print('GPS URL:', settings.EERA_BASE_URL)"
```

## 🔧 Example Configurations

### Development
```env
DEBUG=True
SECRET_KEY=dev-secret-key-min-32-chars-long-for-development
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
CORS_ORIGINS=*
```

### Production
```env
DEBUG=False
SECRET_KEY=prod-super-secure-random-key-generated-with-secrets-module-min-32-chars
ADMIN_USERNAME=production_admin
ADMIN_PASSWORD=VerySecurePassword123!@#
CORS_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
DATABASE_URL=mysql+pymysql://user:password@production-db-server/shuttle_tracker
```

## ⚠️ Important Notes

- **Never commit `.env` to Git**
- **Change all default passwords before deploying**
- **Use environment-specific `.env` files** for dev/staging/production
- **Keep `.env` file permissions restricted** (readable only by application user)
- **Rotate SECRET_KEY periodically** in production
