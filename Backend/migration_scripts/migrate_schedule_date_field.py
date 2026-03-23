"""
Migration Script: Replace start_date + end_date with single date field
Date: 2026-02-13
Description: 
    - Removes start_date and end_date from schedules table
    - Adds a single 'date' column
    - For non-recurring schedules: copies start_date -> date
    - For recurring schedules: date is set to NULL (not used)
    
IMPORTANT: 
    - Backup your database before running this migration
    - Recurring schedules no longer have date boundaries (they run indefinitely until deactivated)
    - Non-recurring schedules require a specific date to appear on
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import os
import shutil


def backup_database():
    """Create a backup of the database before migration"""
    db_path = "shuttle_tracker.db"
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup_before_date_migration"
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return True
    return False


def run_migration():
    """Run the migration to replace start_date/end_date with single date field"""
    
    print("=" * 60)
    print("MIGRATION: Replace start_date + end_date with single date field")
    print("=" * 60)
    
    # Create backup
    print("\n1. Creating database backup...")
    backup_database()
    
    # Connect to database
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Check current columns
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('schedules')]
        print(f"\n2. Current schedules columns: {columns}")
        
        has_start_date = 'start_date' in columns
        has_end_date = 'end_date' in columns
        has_date = 'date' in columns
        
        if has_date and not has_start_date and not has_end_date:
            print("\n✅ Migration already applied. Nothing to do.")
            return
        
        if not has_start_date:
            print("\n⚠️  start_date column not found. Cannot migrate.")
            return
        
        # SQLite doesn't support DROP COLUMN directly, so we recreate the table
        print("\n3. Migrating schedules table...")
        
        # Step 1: Read all existing data
        result = conn.execute(text("SELECT * FROM schedules"))
        rows = result.fetchall()
        col_names = result.keys()
        schedules_data = [dict(zip(col_names, row)) for row in rows]
        print(f"   Found {len(schedules_data)} existing schedules")
        
        # Step 2: Read schedule_days data
        result = conn.execute(text("SELECT * FROM schedule_days"))
        rows = result.fetchall()
        col_names = result.keys()
        days_data = [dict(zip(col_names, row)) for row in rows]
        print(f"   Found {len(days_data)} schedule day entries")
        
        # Step 3: Drop old tables (schedule_days has FK to schedules)
        print("\n4. Recreating tables with new schema...")
        conn.execute(text("DROP TABLE IF EXISTS schedule_days"))
        conn.execute(text("DROP TABLE IF EXISTS schedules"))
        
        # Step 4: Create new schedules table with 'date' instead of 'start_date'/'end_date'
        conn.execute(text("""
            CREATE TABLE schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                start_time TIME NOT NULL,
                route_id INTEGER NOT NULL,
                schedule_type VARCHAR(50) NOT NULL DEFAULT 'student',
                is_recurring BOOLEAN NOT NULL DEFAULT 0,
                date DATE,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE RESTRICT,
                FOREIGN KEY (schedule_type) REFERENCES route_types(type_name),
                CHECK (schedule_type IN ('student', 'staff', 'internal'))
            )
        """))
        
        # Step 5: Create schedule_days table
        conn.execute(text("""
            CREATE TABLE schedule_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                day_of_week VARCHAR(20) NOT NULL,
                FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE,
                CHECK (day_of_week IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'))
            )
        """))
        
        # Step 6: Re-insert schedules with data migration
        print("\n5. Migrating schedule data...")
        migrated = 0
        for s in schedules_data:
            # For non-recurring: date = start_date (the execution date)
            # For recurring: date = NULL (runs indefinitely on specified days)
            if s.get('is_recurring'):
                new_date = None
            else:
                new_date = s.get('start_date')
            
            conn.execute(text("""
                INSERT INTO schedules (id, vehicle_id, start_time, route_id, schedule_type,
                                       is_recurring, date, is_active, created_at, updated_at)
                VALUES (:id, :vehicle_id, :start_time, :route_id, :schedule_type,
                        :is_recurring, :date, :is_active, :created_at, :updated_at)
            """), {
                'id': s['id'],
                'vehicle_id': s['vehicle_id'],
                'start_time': s['start_time'],
                'route_id': s['route_id'],
                'schedule_type': s.get('schedule_type', 'student'),
                'is_recurring': s.get('is_recurring', False),
                'date': new_date,
                'is_active': s.get('is_active', True),
                'created_at': s.get('created_at'),
                'updated_at': s.get('updated_at')
            })
            migrated += 1
        
        print(f"   Migrated {migrated} schedules")
        
        # Step 7: Re-insert schedule_days
        for d in days_data:
            conn.execute(text("""
                INSERT INTO schedule_days (id, schedule_id, day_of_week)
                VALUES (:id, :schedule_id, :day_of_week)
            """), {
                'id': d['id'],
                'schedule_id': d['schedule_id'],
                'day_of_week': d['day_of_week']
            })
        
        print(f"   Restored {len(days_data)} schedule day entries")
        
        # Step 8: Create indexes
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_schedules_vehicle_id ON schedules(vehicle_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_schedules_route_id ON schedules(route_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_schedules_is_recurring ON schedules(is_recurring)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_schedules_schedule_type ON schedules(schedule_type)"))
        
        conn.commit()
        
        # Verify
        result = conn.execute(text("SELECT * FROM schedules LIMIT 5"))
        rows = result.fetchall()
        col_names = result.keys()
        
        print(f"\n6. Verification - new columns: {list(col_names)}")
        print(f"   Sample rows: {len(rows)}")
        for row in rows:
            d = dict(zip(col_names, row))
            print(f"   Schedule #{d['id']}: recurring={d['is_recurring']}, date={d.get('date')}")
    
    print("\n" + "=" * 60)
    print("✅ Migration completed successfully!")
    print("=" * 60)
    print("\nSummary of changes:")
    print("  - Removed: start_date, end_date columns")
    print("  - Added: date column")
    print("  - Non-recurring schedules: date = their specific execution date")
    print("  - Recurring schedules: date = NULL (run indefinitely on specified days)")
    print("  - To stop a recurring schedule, set is_active=false")


if __name__ == "__main__":
    run_migration()
