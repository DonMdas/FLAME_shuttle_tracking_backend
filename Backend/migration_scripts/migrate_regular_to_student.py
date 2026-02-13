"""
Migration Script: Change 'regular' to 'internal' in route_type and schedule_type
==================================================================================

This script updates existing database records to change:
1. Routes table: route_type 'regular' → 'internal'
2. Schedules table: schedule_type 'regular' → 'internal'

This aligns the database with the new type system where:
- 'student' is the default for student shuttles (mapped to student user role)
- 'staff' is for staff/faculty transportation (mapped to staff user role)
- 'internal' is for internal/administrative routes (special access)

**IMPORTANT**: Backup your database before running this migration!

Run this AFTER running migrate_to_integer_ids.py if you haven't already.
"""

import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shuttle_tracker.db")
db_path = DATABASE_URL.replace("sqlite:///", "")

def migrate_regular_to_internal():
    """Update 'regular' to 'internal' in routes and schedules"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting migration: 'regular' → 'internal'...")
        print(f"Database: {db_path}")
        print("=" * 70)
        
        # Check current state
        print("\n📊 Current State:")
        print("-" * 70)
        
        cursor.execute("SELECT COUNT(*) FROM routes WHERE route_type = 'regular'")
        routes_regular_count = cursor.fetchone()[0]
        print(f"Routes with route_type='regular': {routes_regular_count}")
        
        cursor.execute("SELECT COUNT(*) FROM schedules WHERE schedule_type = 'regular'")
        schedules_regular_count = cursor.fetchone()[0]
        print(f"Schedules with schedule_type='regular': {schedules_regular_count}")
        
        if routes_regular_count == 0 and schedules_regular_count == 0:
            print("\n✅ No 'regular' types found. Migration not needed.")
            return
        
        # Confirm migration
        print("\n⚠️  This will update:")
        print(f"   - {routes_regular_count} route(s) from 'regular' to 'internal'")
        print(f"   - {schedules_regular_count} schedule(s) from 'regular' to 'internal'")
        
        response = input("\n❓ Proceed with migration? (yes/no): ").strip().lower()
        if response != 'yes':
            print("❌ Migration cancelled.")
            return
        
        # Start transaction
        print("\n🔄 Performing migration...")
        print("-" * 70)
        
        # Update routes
        if routes_regular_count > 0:
            cursor.execute("""
                UPDATE routes 
                SET route_type = 'internal',
                    updated_at = CURRENT_TIMESTAMP
                WHERE route_type = 'regular'
            """)
            print(f"✅ Updated {cursor.rowcount} route(s)")
        
        # Update schedules
        if schedules_regular_count > 0:
            cursor.execute("""
                UPDATE schedules 
                SET schedule_type = 'internal',
                    updated_at = CURRENT_TIMESTAMP
                WHERE schedule_type = 'regular'
            """)
            print(f"✅ Updated {cursor.rowcount} schedule(s)")
        
        # Commit changes
        conn.commit()
        
        # Verify results
        print("\n📊 After Migration:")
        print("-" * 70)
        
        cursor.execute("SELECT COUNT(*) FROM routes WHERE route_type = 'regular'")
        routes_regular_after = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM routes WHERE route_type = 'internal'")
        routes_internal_after = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM schedules WHERE schedule_type = 'regular'")
        schedules_regular_after = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM schedules WHERE schedule_type = 'internal'")
        schedules_internal_after = cursor.fetchone()[0]
        
        print(f"Routes with route_type='regular': {routes_regular_after}")
        print(f"Routes with route_type='internal': {routes_internal_after}")
        print(f"Schedules with schedule_type='regular': {schedules_regular_after}")
        print(f"Schedules with schedule_type='internal': {schedules_internal_after}")
        
        print("\n" + "=" * 70)
        print("✅ Migration completed successfully!")
        print("=" * 70)
        
        print("\n📝 Summary:")
        print(f"   - Changed {routes_regular_count} route(s) to 'internal' type")
        print(f"   - Changed {schedules_regular_count} schedule(s) to 'internal' type")
        print(f"   - Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during migration: {e}")
        print("⚠️  Changes have been rolled back.")
        raise
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("DATABASE MIGRATION: 'regular' → 'internal'")
    print("=" * 70)
    print("\n⚠️  BACKUP YOUR DATABASE FIRST! ⚠️\n")
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file not found at {db_path}")
        print("Please check your DATABASE_URL in .env file")
        exit(1)
    
    try:
        migrate_regular_to_internal()
    except KeyboardInterrupt:
        print("\n\n❌ Migration interrupted by user.")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        exit(1)
