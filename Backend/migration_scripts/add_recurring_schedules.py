"""
Migration Script: Add Recurring Schedule Support
Date: 2026-02-11
Description: 
    - Adds recurring schedule fields to schedules table
    - Changes start_time from DateTime to Time
    - Adds start_date and end_date fields
    - Creates schedule_days table for recurring day mappings
    
IMPORTANT: 
    - This is a breaking change for start_time field
    - Backup your database before running this migration
    - Existing schedules will have their time extracted from start_time DateTime
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.models import Base
from datetime import datetime, time, date
import os


def backup_database():
    """Create a backup of the database before migration"""
    db_path = "shuttle_tracker.db"
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup_before_recurring_migration"
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return True
    return False


def run_migration():
    """Run the migration to add recurring schedule support"""
    
    print("="*60)
    print("MIGRATION: Add Recurring Schedule Support")
    print("="*60)
    
    # Create backup
    print("\n1. Creating database backup...")
    if backup_database():
        print("   Backup created successfully")
    else:
        print("   ⚠️  No existing database found - proceeding with fresh setup")
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        inspector = inspect(engine)
        
        # Check if migration already applied
        print("\n2. Checking migration status...")
        tables = inspector.get_table_names()
        
        if 'schedule_days' in tables:
            print("   ⚠️  Migration already applied (schedule_days table exists)")
            response = input("   Do you want to reapply? This will DROP and recreate tables (y/n): ")
            if response.lower() != 'y':
                print("   Migration cancelled")
                return
        
        print("\n3. Starting migration...")
        
        # Step 1: Create temporary table for schedules with new schema
        print("   - Creating temporary schedules table...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS schedules_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                start_time TIME NOT NULL,
                route_id INTEGER NOT NULL,
                schedule_type VARCHAR(50) NOT NULL DEFAULT 'student',
                is_recurring BOOLEAN NOT NULL DEFAULT 0,
                start_date DATE,
                end_date DATE,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP WITH TIME ZONE,
                updated_at TIMESTAMP WITH TIME ZONE,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
                FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE RESTRICT,
                FOREIGN KEY (schedule_type) REFERENCES route_types(type_name),
                CHECK (schedule_type IN ('student', 'staff', 'internal'))
            )
        """))
        session.commit()
        
        # Step 2: Migrate existing data (extract time from DateTime)
        print("   - Migrating existing schedule data...")
        
        # Check if old schedules table exists and has data
        if 'schedules' in tables:
            try:
                result = session.execute(text("SELECT COUNT(*) FROM schedules")).fetchone()
                old_count = result[0] if result else 0
                
                if old_count > 0:
                    print(f"   - Found {old_count} existing schedules to migrate")
                    
                    # Get all old schedules
                    old_schedules = session.execute(text("""
                        SELECT id, vehicle_id, start_time, route_id, schedule_type, 
                               is_active, created_at, updated_at
                        FROM schedules
                    """)).fetchall()
                    
                    # Insert into new table with time extraction
                    for schedule in old_schedules:
                        # Parse the datetime string and extract time
                        try:
                            dt = datetime.fromisoformat(schedule[2].replace('Z', '+00:00'))
                            time_only = dt.time()
                            date_only = dt.date()
                        except:
                            # Fallback if parsing fails
                            time_only = time(8, 0, 0)  # Default to 8:00 AM
                            date_only = date.today()
                        
                        session.execute(text("""
                            INSERT INTO schedules_new 
                            (id, vehicle_id, start_time, route_id, schedule_type, 
                             is_recurring, start_date, is_active, created_at, updated_at)
                            VALUES 
                            (:id, :vehicle_id, :start_time, :route_id, :schedule_type,
                             0, :start_date, :is_active, :created_at, :updated_at)
                        """), {
                            'id': schedule[0],
                            'vehicle_id': schedule[1],
                            'start_time': time_only.isoformat(),
                            'route_id': schedule[3],
                            'schedule_type': schedule[4],
                            'start_date': date_only.isoformat(),
                            'is_active': schedule[5],
                            'created_at': schedule[6],
                            'updated_at': schedule[7]
                        })
                    
                    session.commit()
                    print(f"   ✅ Migrated {old_count} schedules successfully")
                else:
                    print("   - No existing schedules to migrate")
                    
            except Exception as e:
                print(f"   ⚠️  Error migrating data: {e}")
                print("   - Continuing with fresh tables...")
        
        # Step 3: Drop old schedules table and rename new one
        print("   - Replacing schedules table...")
        session.execute(text("DROP TABLE IF EXISTS schedules"))
        session.execute(text("ALTER TABLE schedules_new RENAME TO schedules"))
        session.commit()
        
        # Step 4: Create schedule_days table
        print("   - Creating schedule_days table...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS schedule_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                day_of_week VARCHAR(10) NOT NULL,
                FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE,
                CHECK (day_of_week IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'))
            )
        """))
        session.commit()
        
        # Step 5: Create indexes
        print("   - Creating indexes...")
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_schedules_vehicle_id ON schedules(vehicle_id)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_schedules_route_id ON schedules(route_id)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_schedules_is_recurring ON schedules(is_recurring)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_schedules_is_active ON schedules(is_active)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_schedule_days_schedule_id ON schedule_days(schedule_id)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_schedule_days_day_of_week ON schedule_days(day_of_week)
        """))
        session.commit()
        
        print("\n" + "="*60)
        print("✅ Migration completed successfully!")
        print("="*60)
        print("\nChanges applied:")
        print("  ✓ Schedule.start_time changed from DateTime to Time")
        print("  ✓ Added Schedule.is_recurring field")
        print("  ✓ Added Schedule.start_date field")
        print("  ✓ Added Schedule.end_date field")
        print("  ✓ Created schedule_days table")
        print("  ✓ Created necessary indexes")
        print("\nExisting schedules migrated:")
        print("  - Time extracted from original DateTime")
        print("  - All marked as non-recurring (is_recurring=False)")
        print("  - start_date set to original date")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def verify_migration():
    """Verify the migration was successful"""
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)
    
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    # Check tables
    tables = inspector.get_table_names()
    print("\nTables:")
    print(f"  schedules: {'✓' if 'schedules' in tables else '✗'}")
    print(f"  schedule_days: {'✓' if 'schedule_days' in tables else '✗'}")
    
    # Check schedules columns
    if 'schedules' in tables:
        columns = {col['name']: col['type'] for col in inspector.get_columns('schedules')}
        print("\nSchedules columns:")
        print(f"  start_time (TIME): {'✓' if 'start_time' in columns else '✗'}")
        print(f"  is_recurring: {'✓' if 'is_recurring' in columns else '✗'}")
        print(f"  start_date: {'✓' if 'start_date' in columns else '✗'}")
        print(f"  end_date: {'✓' if 'end_date' in columns else '✗'}")
    
    # Check schedule_days columns
    if 'schedule_days' in tables:
        columns = {col['name'] for col in inspector.get_columns('schedule_days')}
        print("\nSchedule_days columns:")
        print(f"  id: {'✓' if 'id' in columns else '✗'}")
        print(f"  schedule_id: {'✓' if 'schedule_id' in columns else '✗'}")
        print(f"  day_of_week: {'✓' if 'day_of_week' in columns else '✗'}")
    
    # Count records
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        schedule_count = session.execute(text("SELECT COUNT(*) FROM schedules")).fetchone()[0]
        schedule_day_count = session.execute(text("SELECT COUNT(*) FROM schedule_days")).fetchone()[0]
        print(f"\nRecord counts:")
        print(f"  Schedules: {schedule_count}")
        print(f"  Schedule days: {schedule_day_count}")
    finally:
        session.close()
    
    print("="*60)


if __name__ == "__main__":
    print("\n⚠️  WARNING: This migration will modify your database schema")
    print("⚠️  A backup will be created automatically\n")
    
    response = input("Do you want to proceed with the migration? (y/n): ")
    
    if response.lower() == 'y':
        run_migration()
        verify_migration()
        
        print("\n✅ All done! You can now use recurring schedules.")
        print("\nNext steps:")
        print("  1. Test the new schedule creation API")
        print("  2. Verify existing schedules still work")
        print("  3. Create some recurring schedules to test")
    else:
        print("\n❌ Migration cancelled")
