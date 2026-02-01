"""
Migration script to add schedule_type column to schedules table.

This script:
1. Adds the schedule_type column to the schedules table
2. Sets default value to "regular" for all existing schedules
3. Creates an index on schedule_type for efficient filtering

Run this script once after deploying the schedule_type feature.
"""

import sqlite3
import os
from pathlib import Path

# Get database path from environment or use default
DATABASE_PATH = os.getenv("DATABASE_URL", "sqlite:///./shuttle_tracker.db").replace("sqlite:///", "")

def migrate_database():
    """Add schedule_type column to schedules table"""
    
    # Check if database file exists
    if not Path(DATABASE_PATH).exists():
        print(f"❌ Database not found at: {DATABASE_PATH}")
        print("Please make sure the database file exists before running migration.")
        return False
    
    print(f"🔍 Found database at: {DATABASE_PATH}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(schedules)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'schedule_type' in columns:
            print("✅ Column 'schedule_type' already exists. No migration needed.")
            conn.close()
            return True
        
        print("📝 Adding 'schedule_type' column to schedules table...")
        
        # Add the new column with default value
        cursor.execute("""
            ALTER TABLE schedules 
            ADD COLUMN schedule_type VARCHAR(50) NOT NULL DEFAULT 'regular'
        """)
        
        # Update all existing schedules to 'regular' (redundant but explicit)
        cursor.execute("""
            UPDATE schedules 
            SET schedule_type = 'regular' 
            WHERE schedule_type IS NULL OR schedule_type = ''
        """)
        
        # Check how many schedules were updated
        cursor.execute("SELECT COUNT(*) FROM schedules")
        total_schedules = cursor.fetchone()[0]
        
        # Create index for efficient filtering
        print("📊 Creating index on schedule_type column...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_schedule_type 
            ON schedules(schedule_type)
        """)
        
        # Commit changes
        conn.commit()
        
        print(f"✅ Migration completed successfully!")
        print(f"   - Added 'schedule_type' column")
        print(f"   - Updated {total_schedules} existing schedule(s) to 'regular' type")
        print(f"   - Created index on schedule_type")
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(schedules)")
        columns = cursor.fetchall()
        print("\n📋 Current schedules table structure:")
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if 'conn' in locals():
            conn.close()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  Schedule Type Migration Script")
    print("=" * 60)
    print()
    
    success = migrate_database()
    
    print()
    if success:
        print("✅ Migration completed successfully!")
        print()
        print("Next steps:")
        print("  1. Restart your application")
        print("  2. Test creating schedules with schedule_type='staff'")
        print("  3. Test filtering: GET /api/admin/schedules?schedule_type=staff")
    else:
        print("❌ Migration failed. Please check the errors above.")
    
    print("=" * 60)
