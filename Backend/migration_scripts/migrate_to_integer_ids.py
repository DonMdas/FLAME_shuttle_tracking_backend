"""
Migration Script: Convert Route and Station IDs to Integers
=============================================================

This script migrates the database from string-based IDs to integer autoincrement IDs for:
1. Stations table (id: STRING → INTEGER)
2. Routes table (remove route_id STRING, use id INTEGER)
3. Update foreign key references in RouteStop, Schedule, and Feedback tables

**IMPORTANT**: Backup your database before running this migration!

Changes:
- Stations.id: STRING → INTEGER (autoincrement)
- Routes: Remove route_id field, use id as primary identifier
- RouteStop: Update foreign keys to integers
- Schedule: Update route_id foreign key to integer
- Feedback: Update route_id foreign key to integer
"""

import sqlite3
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shuttle_tracker.db")
db_path = DATABASE_URL.replace("sqlite:///", "")

def migrate_to_integer_ids():
    """Migrate stations and routes to use integer IDs"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting migration to integer IDs...")
        
        # Create mapping tables for station and route IDs
        print("\n1. Creating ID mapping tables...")
        
        # Get existing stations
        cursor.execute("SELECT id, name, latitude, longitude, is_active, created_at, updated_at FROM stations ORDER BY created_at")
        old_stations = cursor.fetchall()
        
        # Get existing routes
        cursor.execute("SELECT id, route_id, name, from_location, to_location, route_type, is_active, created_at, updated_at FROM routes ORDER BY id")
        old_routes = cursor.fetchall()
        
        # Create station ID mapping (old_string_id → new_int_id)
        station_id_map = {}
        
        # Create route ID mapping (old_string_route_id → integer_id)
        route_id_map = {}
        for route in old_routes:
            integer_id, string_route_id = route[0], route[1]
            route_id_map[string_route_id] = integer_id
        
        print(f"  - Found {len(old_stations)} stations")
        print(f"  - Found {len(old_routes)} routes")
        
        # ========== STATIONS MIGRATION ==========
        print("\n2. Migrating stations table...")
        
        # Create new stations table with integer ID
        cursor.execute("""
            CREATE TABLE stations_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert stations and build mapping
        for old_station in old_stations:
            old_id, name, lat, lon, is_active, created_at, updated_at = old_station
            cursor.execute("""
                INSERT INTO stations_new (name, latitude, longitude, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, lat, lon, is_active, created_at, updated_at))
            new_id = cursor.lastrowid
            station_id_map[old_id] = new_id
            print(f"  - Station '{old_id}' → {new_id}: {name}")
        
        print(f"✓ Migrated {len(station_id_map)} stations")
        
        # ========== ROUTES MIGRATION ==========
        print("\n3. Migrating routes table...")
        
        # Create new routes table without route_id field
        cursor.execute("""
            CREATE TABLE routes_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                from_location VARCHAR(100) NOT NULL,
                to_location VARCHAR(100) NOT NULL,
                route_type VARCHAR(20) NOT NULL DEFAULT 'staff',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert routes (reuse existing integer IDs)
        for route in old_routes:
            old_int_id, route_id, name, from_loc, to_loc, route_type, is_active, created_at, updated_at = route
            cursor.execute("""
                INSERT INTO routes_new (id, name, from_location, to_location, route_type, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (old_int_id, name, from_loc, to_loc, route_type, is_active, created_at, updated_at))
            print(f"  - Route {old_int_id} (was '{route_id}'): {name}")
        
        print(f"✓ Migrated { len(old_routes)} routes")
        
        # ========== ROUTE_STOPS MIGRATION ==========
        print("\n4. Migrating route_stops table...")
        
        # Get existing route_stops
        cursor.execute("SELECT id, route_id, station_id, stop_order, created_at FROM route_stops")
        old_route_stops = cursor.fetchall()
        
        # Create new route_stops table with integer foreign keys
        cursor.execute("""
            CREATE TABLE route_stops_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id INTEGER NOT NULL,
                station_id INTEGER NOT NULL,
                stop_order INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (route_id) REFERENCES routes_new(id) ON DELETE CASCADE,
                FOREIGN KEY (station_id) REFERENCES stations_new(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_route_stops_new_route_id ON route_stops_new(route_id)")
        cursor.execute("CREATE INDEX idx_route_stops_new_station_id ON route_stops_new(station_id)")
        
        # Insert route_stops with mapped IDs
        migrated_stops = 0
        skipped_stops = 0
        for stop in old_route_stops:
            stop_id, old_route_id, old_station_id, stop_order, created_at = stop
            
            # Map route_id: string → integer
            new_route_id = route_id_map.get(old_route_id)
            if not new_route_id:
                print(f"  ! Skipping stop {stop_id}: route '{old_route_id}' not found")
                skipped_stops += 1
                continue
            
            # Map station_id: string → integer
            new_station_id = station_id_map.get(old_station_id)
            if not new_station_id:
                print(f"  ! Skipping stop {stop_id}: station '{old_station_id}' not found")
                skipped_stops += 1
                continue
            
            cursor.execute("""
                INSERT INTO route_stops_new (route_id, station_id, stop_order, created_at)
                VALUES (?, ?, ?, ?)
            """, (new_route_id, new_station_id, stop_order, created_at))
            migrated_stops += 1
        
        print(f"✓ Migrated {migrated_stops} route stops ({skipped_stops} skipped)")
        
        # ========== SCHEDULES MIGRATION ==========
        print("\n5. Migrating schedules table...")
        
        # Get existing schedules
        cursor.execute("SELECT id, vehicle_id, start_time, route_id, schedule_type, is_active, created_at, updated_at FROM schedules")
        old_schedules = cursor.fetchall()
        
        # Create new schedules table with integer route_id foreign key
        cursor.execute("""
            CREATE TABLE schedules_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                start_time TIMESTAMP NOT NULL,
                route_id INTEGER NOT NULL,
                schedule_type VARCHAR(50) NOT NULL DEFAULT 'regular',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
                FOREIGN KEY (route_id) REFERENCES routes_new(id) ON DELETE RESTRICT
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_schedules_new_vehicle_id ON schedules_new(vehicle_id)")
        cursor.execute("CREATE INDEX idx_schedules_new_route_id ON schedules_new(route_id)")
        cursor.execute("CREATE INDEX idx_schedules_new_schedule_type ON schedules_new(schedule_type)")
        
        # Insert schedules with mapped route IDs
        migrated_schedules = 0
        skipped_schedules = 0
        for schedule in old_schedules:
            sched_id, vehicle_id, start_time, old_route_id, schedule_type, is_active, created_at, updated_at = schedule
            
            new_route_id = route_id_map.get(old_route_id)
            if not new_route_id:
                print(f"  ! Skipping schedule {sched_id}: route '{old_route_id}' not found")
                skipped_schedules += 1
                continue
            
            cursor.execute("""
                INSERT INTO schedules_new (vehicle_id, start_time, route_id, schedule_type, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (vehicle_id, start_time, new_route_id, schedule_type, is_active, created_at, updated_at))
            migrated_schedules += 1
        
        print(f"✓ Migrated {migrated_schedules} schedules ({skipped_schedules} skipped)")
        
        # ========== FEEDBACK MIGRATION ==========
        print("\n6. Migrating feedbacks table...")
        
        # Get existing feedbacks
        cursor.execute("""
            SELECT id, user_id, is_anonymous, feedback_type, category, vehicle_id, route_id, schedule_id,
                   rating, title, description, issues, status, priority, admin_response, admin_notes,
                   resolved_by, resolved_at, created_at, updated_at
            FROM feedbacks
        """)
        old_feedbacks = cursor.fetchall()
        
        # Create new feedbacks table
        cursor.execute("""
            CREATE TABLE feedbacks_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                is_anonymous BOOLEAN NOT NULL DEFAULT 0,
                feedback_type VARCHAR(50) NOT NULL,
                category VARCHAR(50),
                vehicle_id INTEGER,
                route_id INTEGER,
                schedule_id INTEGER,
                rating INTEGER,
                title VARCHAR(255),
                description VARCHAR(2000),
                issues VARCHAR(1000),
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                admin_response VARCHAR(2000),
                admin_notes VARCHAR(2000),
                resolved_by INTEGER,
                resolved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE SET NULL,
                FOREIGN KEY (route_id) REFERENCES routes_new(id) ON DELETE SET NULL,
                FOREIGN KEY (schedule_id) REFERENCES schedules_new(id) ON DELETE SET NULL,
                FOREIGN KEY (resolved_by) REFERENCES admins(id) ON DELETE SET NULL
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_feedbacks_new_user_id ON feedbacks_new(user_id)")
        cursor.execute("CREATE INDEX idx_feedbacks_new_feedback_type ON feedbacks_new(feedback_type)")
        cursor.execute("CREATE INDEX idx_feedbacks_new_category ON feedbacks_new(category)")
        cursor.execute("CREATE INDEX idx_feedbacks_new_vehicle_id ON feedbacks_new(vehicle_id)")
        cursor.execute("CREATE INDEX idx_feedbacks_new_route_id ON feedbacks_new(route_id)")
        cursor.execute("CREATE INDEX idx_feedbacks_new_status ON feedbacks_new(status)")
        
        # Insert feedbacks with mapped route IDs
        migrated_feedbacks = 0
        for feedback in old_feedbacks:
            (fb_id, user_id, is_anon, fb_type, category, vehicle_id, old_route_id, schedule_id,
             rating, title, desc, issues, status, priority, admin_resp, admin_notes,
             resolved_by, resolved_at, created_at, updated_at) = feedback
            
            # Map route_id if present
            new_route_id = None
            if old_route_id:
                new_route_id = route_id_map.get(old_route_id)
                if not new_route_id:
                    print(f"  ! Feedback {fb_id}: route '{old_route_id}' not found, setting to NULL")
            
            cursor.execute("""
                INSERT INTO feedbacks_new (
                    user_id, is_anonymous, feedback_type, category, vehicle_id, route_id, schedule_id,
                    rating, title, description, issues, status, priority, admin_response, admin_notes,
                    resolved_by, resolved_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, is_anon, fb_type, category, vehicle_id, new_route_id, schedule_id,
                  rating, title, desc, issues, status, priority, admin_resp, admin_notes,
                  resolved_by, resolved_at, created_at, updated_at))
            migrated_feedbacks += 1
        
        print(f"✓ Migrated {migrated_feedbacks} feedbacks")
        
        # ========== REPLACE OLD TABLES ==========
        print("\n7. Replacing old tables with new ones...")
        
        cursor.execute("DROP TABLE IF EXISTS feedbacks")
        cursor.execute("DROP TABLE IF EXISTS schedules")
        cursor.execute("DROP TABLE IF EXISTS route_stops")
        cursor.execute("DROP TABLE IF EXISTS routes")
        cursor.execute("DROP TABLE IF EXISTS stations")
        
        cursor.execute("ALTER TABLE stations_new RENAME TO stations")
        cursor.execute("ALTER TABLE routes_new RENAME TO routes")
        cursor.execute("ALTER TABLE route_stops_new RENAME TO route_stops")
        cursor.execute("ALTER TABLE schedules_new RENAME TO schedules")
        cursor.execute("ALTER TABLE feedbacks_new RENAME TO feedbacks")
        
        print("✓ Tables replaced")
        
        # Commit changes
        conn.commit()
        
        print("\n" + "="*60)
        print("✓ MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nSummary:")
        print(f"  - Stations: {len(station_id_map)} migrated to integer IDs")
        print(f"  - Routes: {len(old_routes)} migrated (removed route_id field)")
        print(f"  - Route stops: {migrated_stops} migrated")
        print(f"  - Schedules: {migrated_schedules} migrated")
        print(f"  - Feedbacks: {migrated_feedbacks} migrated")
        print("\nAll IDs are now integers with autoincrement!")
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        print("Rolling back changes...")
        conn.rollback()
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    print("="*60)
    print("Database Migration: String IDs → Integer IDs")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    print("\n⚠️  WARNING: This migration will modify your database structure!")
    print("   Make sure you have a backup before proceeding.")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    input()
    
    migrate_to_integer_ids()
