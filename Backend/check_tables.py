"""Quick script to check if route tables are created"""
import sys
import os

# Add Backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import inspect, text
from app.db.session import engine

def check_tables():
    """Check if stations, routes, and route_stops tables exist"""
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print("=" * 60)
    print("DATABASE TABLE CHECK")
    print("=" * 60)
    
    required_tables = ['stations', 'routes', 'route_stops']
    
    print("\nAll tables in database:")
    for table in sorted(tables):
        print(f"  ✓ {table}")
    
    print(f"\nTotal tables: {len(tables)}")
    
    print("\n" + "-" * 60)
    print("Required Route Tables:")
    print("-" * 60)
    
    all_exist = True
    for table in required_tables:
        if table in tables:
            print(f"  ✓ {table} - EXISTS")
        else:
            print(f"  ✗ {table} - MISSING")
            all_exist = False
    
    if all_exist:
        print("\n" + "=" * 60)
        print("✓ All route tables exist!")
        print("=" * 60)
        
        # Check data counts
        print("\nData counts:")
        with engine.connect() as conn:
            stations_count = conn.execute(text("SELECT COUNT(*) FROM stations")).scalar()
            routes_count = conn.execute(text("SELECT COUNT(*) FROM routes")).scalar()
            route_stops_count = conn.execute(text("SELECT COUNT(*) FROM route_stops")).scalar()
            
            print(f"  - Stations: {stations_count}")
            print(f"  - Routes: {routes_count}")
            print(f"  - Route Stops: {route_stops_count}")
            
        print("\n" + "=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ Some tables are missing! Run migration script.")
        print("=" * 60)
        return False
    
    return True

if __name__ == "__main__":
    try:
        success = check_tables()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Error checking tables: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
