"""
Initialize RouteType Lookup Table
==================================

This script populates the route_types table with valid route/schedule types.
Run this after creating the database tables for the first time.
"""

import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shuttle_tracker.db")
db_path = DATABASE_URL.replace("sqlite:///", "")

def initialize_route_types():
    """Insert the allowed route types into the route_types table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Initializing route_types table...")
        print("=" * 70)
        
        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS route_types (
                type_name VARCHAR(20) PRIMARY KEY NOT NULL,
                description VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Define the allowed types
        route_types = [
            ('student', 'Routes and schedules for student shuttles (mapped to student user role)'),
            ('staff', 'Routes and schedules for staff/faculty transportation (mapped to staff user role)'),
            ('internal', 'Internal/administrative routes with special access')
        ]
        
        # Check existing types
        cursor.execute("SELECT type_name FROM route_types")
        existing_types = [row[0] for row in cursor.fetchall()]
        
        if existing_types:
            print(f"✅ Found existing types: {', '.join(existing_types)}")
        
        # Insert or update types
        inserted = 0
        updated = 0
        for type_name, description in route_types:
            cursor.execute("SELECT COUNT(*) FROM route_types WHERE type_name = ?", (type_name,))
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                cursor.execute("""
                    UPDATE route_types 
                    SET description = ? 
                    WHERE type_name = ?
                """, (description, type_name))
                print(f"🔄 Updated: {type_name}")
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO route_types (type_name, description)
                    VALUES (?, ?)
                """, (type_name, description))
                print(f"✅ Inserted: {type_name}")
                inserted += 1
        
        conn.commit()
        
        # Display final state
        print("\n" + "=" * 70)
        print("📊 Route Types Table:")
        print("=" * 70)
        cursor.execute("SELECT type_name, description FROM route_types ORDER BY type_name")
        for row in cursor.fetchall():
            print(f"  {row[0]:10} - {row[1]}")
        
        print("\n" + "=" * 70)
        print(f"✅ Initialization complete!")
        print(f"   - Inserted: {inserted} new type(s)")
        print(f"   - Updated: {updated} existing type(s)")
        print("=" * 70)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("INITIALIZE ROUTE_TYPES TABLE")
    print("=" * 70 + "\n")
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file not found at {db_path}")
        print("Please check your DATABASE_URL in .env file")
        exit(1)
    
    try:
        initialize_route_types()
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        exit(1)
