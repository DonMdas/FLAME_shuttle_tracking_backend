"""
Database Migration: Add auth_provider field and modify role to nullable

This migration:
1. Adds auth_provider column to users table
2. Makes role column nullable
3. Sets default auth_provider based on existing data
4. Renames is_verified to is_email_verified for clarity

Run this script to migrate existing database.
Supports both SQLite and MySQL/MariaDB.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.db.session import engine, SessionLocal
from app.core.logger import logger


def get_database_type():
    """Detect database type (sqlite or mysql)"""
    dialect_name = engine.dialect.name.lower()
    return dialect_name


def column_exists(db, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (works for both SQLite and MySQL)"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Run database migration"""
    db = SessionLocal()
    db_type = get_database_type()
    
    try:
        logger.info(f"Starting database migration: add_auth_provider_field (Database: {db_type})")
        
        # Check if auth_provider column already exists
        if column_exists(db, 'users', 'auth_provider'):
            logger.info("auth_provider column already exists, skipping migration")
            return
        
        # Step 1: Add auth_provider column (nullable temporarily)
        logger.info("Adding auth_provider column...")
        if db_type == 'sqlite':
            db.execute(text("""
                ALTER TABLE users 
                ADD COLUMN auth_provider VARCHAR(20)
            """))
        else:  # MySQL
            db.execute(text("""
                ALTER TABLE users 
                ADD COLUMN auth_provider VARCHAR(20) NULL
            """))
        db.commit()
        
        # Step 2: Set auth_provider based on existing data
        logger.info("Setting auth_provider values based on existing data...")
        
        # Users with google_id AND hashed_password -> google+password
        db.execute(text("""
            UPDATE users 
            SET auth_provider = 'google+password'
            WHERE google_id IS NOT NULL AND hashed_password IS NOT NULL
        """))
        
        # Users with only google_id -> google
        db.execute(text("""
            UPDATE users 
            SET auth_provider = 'google'
            WHERE google_id IS NOT NULL AND hashed_password IS NULL
        """))
        
        # Users with only hashed_password -> password
        db.execute(text("""
            UPDATE users 
            SET auth_provider = 'password'
            WHERE google_id IS NULL AND hashed_password IS NOT NULL
        """))
        
        db.commit()
        
        # Step 3: Make auth_provider NOT NULL now that all values are set
        logger.info("Making auth_provider NOT NULL...")
        if db_type == 'sqlite':
            # SQLite doesn't support MODIFY COLUMN, need to recreate table
            # For now, we'll skip this as SQLite allows NULL by default and validates at app level
            logger.info("SQLite: Skipping NOT NULL constraint (enforced at application level)")
        else:  # MySQL
            db.execute(text("""
                ALTER TABLE users 
                MODIFY COLUMN auth_provider VARCHAR(20) NOT NULL
            """))
            db.commit()
        
        # Step 4: Make role nullable (was NOT NULL before)
        logger.info("Making role column nullable...")
        if db_type == 'sqlite':
            # SQLite doesn't support MODIFY COLUMN easily
            logger.info("SQLite: Role column should already allow NULL")
        else:  # MySQL
            db.execute(text("""
                ALTER TABLE users 
                MODIFY COLUMN role VARCHAR(20) NULL
            """))
            db.commit()
        
        # Step 5: Rename is_verified to is_email_verified for clarity
        logger.info("Checking if is_verified needs to be renamed to is_email_verified...")
        
        if column_exists(db, 'users', 'is_verified'):
            logger.info("Renaming is_verified to is_email_verified...")
            if db_type == 'sqlite':
                # SQLite supports RENAME COLUMN from version 3.25.0+
                db.execute(text("""
                    ALTER TABLE users 
                    RENAME COLUMN is_verified TO is_email_verified
                """))
            else:  # MySQL
                db.execute(text("""
                    ALTER TABLE users 
                    CHANGE COLUMN is_verified is_email_verified BOOLEAN NOT NULL DEFAULT 0
                """))
            db.commit()
        
        # Step 6: Add index on auth_provider for better query performance
        logger.info("Adding index on auth_provider...")
        try:
            if db_type == 'sqlite':
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider)
                """))
            else:  # MySQL
                db.execute(text("""
                    CREATE INDEX idx_users_auth_provider ON users(auth_provider)
                """))
            db.commit()
        except Exception as e:
            logger.warning(f"Index may already exist: {e}")
            db.rollback()
        
        logger.info("✅ Migration completed successfully!")
        
        # Display summary
        try:
            result = db.execute(text("""
                SELECT 
                    auth_provider,
                    COUNT(*) as count,
                    SUM(CASE WHEN role IS NULL THEN 1 ELSE 0 END) as null_role_count
                FROM users 
                GROUP BY auth_provider
            """))
            
            print("\n" + "="*60)
            print("Migration Summary:")
            print("="*60)
            for row in result:
                print(f"  {row.auth_provider:20} | Users: {row.count:3} | Null roles: {row.null_role_count}")
            print("="*60)
        except Exception as e:
            logger.warning(f"Could not generate summary (no users yet?): {e}")
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def rollback():
    """Rollback migration (use with caution)"""
    db = SessionLocal()
    db_type = get_database_type()
    
    try:
        logger.info(f"Rolling back migration: add_auth_provider_field (Database: {db_type})")
        
        # Remove auth_provider column
        logger.info("Removing auth_provider column...")
        if db_type == 'sqlite':
            db.execute(text("""
                ALTER TABLE users 
                DROP COLUMN auth_provider
            """))
        else:  # MySQL
            db.execute(text("""
                ALTER TABLE users 
                DROP COLUMN IF EXISTS auth_provider
            """))
        db.commit()
        
        # Make role NOT NULL again (set default value first)
        logger.info("Making role NOT NULL again...")
        db.execute(text("""
            UPDATE users SET role = 'student' WHERE role IS NULL
        """))
        db.commit()
        
        if db_type == 'mysql':
            db.execute(text("""
                ALTER TABLE users 
                MODIFY COLUMN role VARCHAR(20) NOT NULL
            """))
            db.commit()
        
        # Rename back if needed
        if column_exists(db, 'users', 'is_email_verified'):
            logger.info("Renaming is_email_verified back to is_verified...")
            if db_type == 'sqlite':
                db.execute(text("""
                    ALTER TABLE users 
                    RENAME COLUMN is_email_verified TO is_verified
                """))
            else:  # MySQL
                db.execute(text("""
                    ALTER TABLE users 
                    CHANGE COLUMN is_email_verified is_verified BOOLEAN NOT NULL DEFAULT 0
                """))
            db.commit()
        
        logger.info("✅ Rollback completed successfully!")
        
    except Exception as e:
        logger.error(f"Rollback failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration for auth_provider field")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()
    
    if args.rollback:
        confirm = input("⚠️  Are you sure you want to rollback? This may cause data loss. (yes/no): ")
        if confirm.lower() == "yes":
            rollback()
        else:
            print("Rollback cancelled.")
    else:
        migrate()
