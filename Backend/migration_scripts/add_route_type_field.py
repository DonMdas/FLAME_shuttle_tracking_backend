"""
Migration script to add route_type field to routes table.
This field distinguishes between 'regular' and 'staff' routes.

Regular routes: campus-fcroad, fcroad-campus, campus-bavdhan, bavdhan-campus
Staff routes: all other routes

Run this script to update the database schema and populate initial values.
Run from Backend directory: python -m migration_scripts.add_route_type_field
"""

import sys
import os
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

# Create database connection
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_migration():
    """Add route_type column to routes table and set initial values"""
    db = SessionLocal()
    
    try:
        print("Starting migration: Add route_type field to routes table")
        
        # Step 1: Check if column already exists (SQLite compatible)
        check_column_query = text("""
            SELECT COUNT(*) 
            FROM pragma_table_info('routes')
            WHERE name = 'route_type'
        """)
        
        result = db.execute(check_column_query)
        column_exists = result.scalar() > 0
        
        if column_exists:
            print("✓ Column 'route_type' already exists in routes table")
        else:
            # Step 2: Add route_type column (SQLite compatible)
            print("Adding route_type column to routes table...")
            add_column_query = text("""
                ALTER TABLE routes 
                ADD COLUMN route_type VARCHAR(20) NOT NULL DEFAULT 'staff'
            """)
            db.execute(add_column_query)
            db.commit()
            print("✓ Added route_type column to routes table")
        
        # Step 3: Set route_type values based on route_id
        print("\nSetting route_type values based on route_id...")
        
        # Define regular routes
        regular_routes = [
            'campus-fcroad',
            'fcroad-campus',
            'campus-bavdhan',
            'bavdhan-campus'
        ]
        
        # Update regular routes
        for route_id in regular_routes:
            update_query = text("""
                UPDATE routes 
                SET route_type = 'regular' 
                WHERE route_id = :route_id
            """)
            result = db.execute(update_query, {"route_id": route_id})
            if result.rowcount > 0:
                print(f"  ✓ Set '{route_id}' as 'regular'")
            else:
                print(f"  ⚠ Route '{route_id}' not found in database")
        
        # Get all staff routes
        staff_query = text("""
            SELECT route_id, route_type 
            FROM routes 
            WHERE route_type = 'staff'
        """)
        staff_routes = db.execute(staff_query).fetchall()
        
        if staff_routes:
            print("\nStaff routes:")
            for route_id, route_type in staff_routes:
                print(f"  ✓ '{route_id}' is set as '{route_type}'")
        
        db.commit()
        print("\n✓ Successfully set all route_type values")
        
        # Step 4: Show summary
        summary_query = text("""
            SELECT route_type, COUNT(*) as count 
            FROM routes 
            GROUP BY route_type
        """)
        summary = db.execute(summary_query).fetchall()
        
        print("\n" + "="*50)
        print("Migration Summary:")
        print("="*50)
        if summary:
            for route_type, count in summary:
                print(f"  {route_type.capitalize()} routes: {count}")
        else:
            print("  No routes found in database")
        print("="*50)
        
        print("\n✓ Migration completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*50)
    print("Database Migration: Add route_type field")
    print("="*50 + "\n")
    
    try:
        run_migration()
    except Exception as e:
        sys.exit(1)
