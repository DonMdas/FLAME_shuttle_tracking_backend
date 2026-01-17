"""
Database Migration Script: Add User Table
Creates the users table for user authentication with email verification.
Works with both MySQL and SQLite.
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings
from app.core.logger import logger

def get_create_table_sql(dialect_name):
    """Get appropriate CREATE TABLE SQL based on database dialect"""
    
    if dialect_name == 'mysql':
        # MySQL syntax
        return """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) NOT NULL UNIQUE,
                hashed_password VARCHAR(255),
                role VARCHAR(20) NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE NOT NULL,
                otp VARCHAR(6),
                otp_created_at TIMESTAMP NULL,
                google_id VARCHAR(100) UNIQUE,
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_email (email),
                INDEX idx_role (role),
                INDEX idx_google_id (google_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    else:
        # SQLite syntax (and PostgreSQL compatible)
        return """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(100) NOT NULL UNIQUE,
                hashed_password VARCHAR(255),
                role VARCHAR(20) NOT NULL,
                is_verified BOOLEAN DEFAULT 0 NOT NULL,
                otp VARCHAR(6),
                otp_created_at TIMESTAMP NULL,
                google_id VARCHAR(100) UNIQUE,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """

def create_indexes_sqlite(connection):
    """Create indexes separately for SQLite"""
    try:
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_email ON users(email)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_role ON users(role)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_google_id ON users(google_id)"))
        logger.info("✅ Indexes created successfully")
    except Exception as e:
        logger.warning(f"Index creation warning: {str(e)}")

def migrate():
    """Add users table to database"""
    
    engine = create_engine(settings.DATABASE_URL)
    dialect_name = engine.dialect.name
    
    logger.info(f"Database type detected: {dialect_name}")
    
    with engine.connect() as connection:
        # Start transaction
        trans = connection.begin()
        
        try:
            # Check if table already exists
            inspector = inspect(engine)
            if 'users' in inspector.get_table_names():
                logger.info("⚠️  Users table already exists, skipping creation")
                trans.commit()
                print("\n⚠️  Users table already exists!")
                return
            
            logger.info("Creating users table...")
            
            # Create users table with appropriate syntax
            create_table_sql = get_create_table_sql(dialect_name)
            connection.execute(text(create_table_sql))
            
            logger.info("✅ Users table created successfully")
            
            # Create indexes separately for SQLite
            if dialect_name == 'sqlite':
                create_indexes_sqlite(connection)
            
            # Commit transaction
            trans.commit()
            logger.info("✅ Migration completed successfully")
            
            print("\n✅ Database migration completed successfully!")
            print(f"   - Database type: {dialect_name}")
            print("   - Created users table")
            if dialect_name == 'sqlite':
                print("   - Created indexes")
            print("\n📋 Next steps:")
            if dialect_name == 'sqlite':
                print("   ⚠️  Note: You're using SQLite. For production, consider using MySQL.")
            print("   1. Add SMTP configuration to .env file (optional):")
            print("      SMTP_SERVER=smtp.gmail.com")
            print("      SMTP_PORT=587")
            print("      SMTP_USERNAME=your-email@gmail.com")
            print("      SMTP_PASSWORD=your-app-password")
            print("      FROM_EMAIL=your-email@gmail.com")
            print("      FROM_NAME=Shuttle Tracker")
            print("   2. Restart the application")
            print("   3. Test user signup at /api/auth/signup")
            
        except Exception as e:
            trans.rollback()
            logger.error(f"❌ Migration failed: {str(e)}")
            print(f"\n❌ Migration failed: {str(e)}")
            raise

if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: Add User Table")
    print("=" * 60)
    migrate()
