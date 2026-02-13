"""
Migration script to add stations, routes, and route_stops tables.
Populates tables with data from route_config.py.

Run with: uv run migration_scripts/add_routes_and_stations.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.db.session import engine, SessionLocal
from app.db.models import Base, Station, Route, RouteStop
from app.core.route_config import STATIONS, ROUTE_DEFINITIONS


def table_exists(inspector, table_name: str) -> bool:
    """Check if a table exists in the database"""
    return table_name in inspector.get_table_names()


def get_database_type() -> str:
    """Detect database type (sqlite or mysql)"""
    dialect_name = engine.dialect.name.lower()
    if 'sqlite' in dialect_name:
        return 'sqlite'
    elif 'mysql' in dialect_name or 'mariadb' in dialect_name:
        return 'mysql'
    return 'unknown'


def create_tables():
    """Create new tables for stations, routes, and route_stops"""
    print("🔨 Creating new tables...")
    
    # Create only the new tables
    Station.__table__.create(engine, checkfirst=True)
    Route.__table__.create(engine, checkfirst=True)
    RouteStop.__table__.create(engine, checkfirst=True)
    
    print("✅ Tables created successfully!")


def populate_stations(db: SessionLocal):
    """Populate stations table from route_config.py"""
    print("\n📍 Populating stations...")
    
    # Check if stations already exist
    existing_count = db.query(Station).count()
    if existing_count > 0:
        print(f"ℹ️  Found {existing_count} existing stations. Skipping population.")
        return
    
    stations_added = 0
    for station_id, station_data in STATIONS.items():
        db_station = Station(
            id=station_data.id,
            name=station_data.name,
            latitude=station_data.lat,
            longitude=station_data.lon,
            is_active=True
        )
        db.add(db_station)
        stations_added += 1
    
    db.commit()
    print(f"✅ Added {stations_added} stations")


def populate_routes(db: SessionLocal):
    """Populate routes and route_stops tables from route_config.py"""
    print("\n🛣️  Populating routes and stops...")
    
    # Check if routes already exist
    existing_count = db.query(Route).count()
    if existing_count > 0:
        print(f"ℹ️  Found {existing_count} existing routes. Skipping population.")
        return
    
    routes_added = 0
    stops_added = 0
    
    for route_id, route_def in ROUTE_DEFINITIONS.items():
        # Create route
        db_route = Route(
            route_id=route_def["route_id"],
            name=route_def["name"],
            from_location=route_def["from_location"],
            to_location=route_def["to_location"],
            is_active=True
        )
        db.add(db_route)
        db.flush()  # Flush to get the route ID
        routes_added += 1
        
        # Create route stops
        for order, station_id in enumerate(route_def["stops"]):
            # Verify station exists
            station = db.query(Station).filter(Station.id == station_id).first()
            if not station:
                print(f"⚠️  Warning: Station '{station_id}' not found for route '{route_id}'. Skipping.")
                continue
            
            db_route_stop = RouteStop(
                route_id=route_def["route_id"],
                station_id=station_id,
                stop_order=order
            )
            db.add(db_route_stop)
            stops_added += 1
    
    db.commit()
    print(f"✅ Added {routes_added} routes with {stops_added} stops")


def update_existing_schedules(db: SessionLocal):
    """Update existing schedules to ensure route_id references are valid"""
    print("\n🔄 Validating existing schedules...")
    
    from app.db.models import Schedule
    
    schedules = db.query(Schedule).all()
    if not schedules:
        print("ℹ️  No existing schedules to validate.")
        return
    
    invalid_count = 0
    for schedule in schedules:
        route = db.query(Route).filter(Route.route_id == schedule.route_id).first()
        if not route:
            print(f"⚠️  Schedule {schedule.id} references non-existent route '{schedule.route_id}'")
            invalid_count += 1
    
    if invalid_count > 0:
        print(f"⚠️  Found {invalid_count} schedules with invalid route references.")
        print("   Please update or delete these schedules manually.")
    else:
        print("✅ All existing schedules have valid route references")


def main():
    """Main migration function"""
    print("="*60)
    print("MIGRATION: Add Routes and Stations Tables")
    print("="*60)
    
    # Detect database type
    db_type = get_database_type()
    print(f"\n📊 Database Type: {db_type.upper()}")
    
    # Create inspector
    inspector = inspect(engine)
    
    # Check if tables already exist
    stations_exists = table_exists(inspector, "stations")
    routes_exists = table_exists(inspector, "routes")
    route_stops_exists = table_exists(inspector, "route_stops")
    
    if stations_exists and routes_exists and route_stops_exists:
        print("\n✅ All tables already exist!")
        
        # Check if we need to populate
        db = SessionLocal()
        try:
            station_count = db.query(Station).count()
            route_count = db.query(Route).count()
            
            if station_count == 0 or route_count == 0:
                print("\n📥 Tables exist but are empty. Populating with data...")
                populate_stations(db)
                populate_routes(db)
                update_existing_schedules(db)
            else:
                print(f"\nℹ️  Found {station_count} stations and {route_count} routes.")
                print("   Database already populated.")
        finally:
            db.close()
    else:
        # Create tables
        create_tables()
        
        # Populate with data
        db = SessionLocal()
        try:
            populate_stations(db)
            populate_routes(db)
            update_existing_schedules(db)
        finally:
            db.close()
    
    print("\n" + "="*60)
    print("✅ Migration completed successfully!")
    print("="*60)
    
    # Display summary
    db = SessionLocal()
    try:
        station_count = db.query(Station).count()
        route_count = db.query(Route).count()
        route_stop_count = db.query(RouteStop).count()
        
        print(f"\n📊 Database Summary:")
        print(f"   • Stations: {station_count}")
        print(f"   • Routes: {route_count}")
        print(f"   • Route Stops: {route_stop_count}")
        
        # Show sample routes
        print(f"\n📋 Sample Routes:")
        routes = db.query(Route).limit(5).all()
        for route in routes:
            stops_count = len(route.route_stops)
            print(f"   • {route.name} ({stops_count} stops)")
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
