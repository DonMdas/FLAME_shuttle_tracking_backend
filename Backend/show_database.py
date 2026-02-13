"""
Display all database tables and their contents in a formatted way
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import inspect, text, create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

def print_table_header(table_name, count):
    """Print a nice header for each table"""
    print("\n" + "=" * 80)
    print(f"TABLE: {table_name.upper()}")
    print(f"Records: {count}")
    print("=" * 80)

def format_value(value, max_len=50):
    """Format a value for display, truncating if too long"""
    if value is None:
        return "NULL"
    
    str_val = str(value)
    if len(str_val) > max_len:
        return str_val[:max_len-3] + "..."
    return str_val

def print_table_data(table_name, limit=None):
    """Print table schema and data"""
    inspector = inspect(engine)
    
    # Get columns
    columns = inspector.get_columns(table_name)
    col_names = [col['name'] for col in columns]
    col_types = {col['name']: str(col['type']) for col in columns}
    
    # Print schema
    print("\nSchema:")
    print("-" * 80)
    for col in columns:
        nullable = "NULL" if col['nullable'] else "NOT NULL"
        default = f" DEFAULT {col['default']}" if col['default'] else ""
        print(f"  {col['name']:<30} {str(col['type']):<20} {nullable}{default}")
    
    # Get data
    with engine.connect() as conn:
        count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        count = count_result.scalar()
        
        print_table_header(table_name, count)
        
        if count == 0:
            print("\n  (No data)")
            return
        
        # Limit records if specified
        limit_clause = f" LIMIT {limit}" if limit else ""
        result = conn.execute(text(f"SELECT * FROM {table_name}{limit_clause}"))
        rows = result.fetchall()
        
        if not rows:
            print("\n  (No data)")
            return
        
        # Calculate column widths
        col_widths = {}
        for col_name in col_names:
            col_widths[col_name] = len(col_name)
        
        for row in rows:
            for i, col_name in enumerate(col_names):
                val_len = len(format_value(row[i], max_len=40))
                col_widths[col_name] = max(col_widths[col_name], val_len)
        
        # Cap max width at 40
        for col_name in col_names:
            col_widths[col_name] = min(col_widths[col_name], 40)
        
        # Print header
        print("\nData:")
        print("-" * 80)
        header = " | ".join([col_name.ljust(col_widths[col_name]) for col_name in col_names])
        print(header)
        print("-" * len(header))
        
        # Print rows
        for row in rows:
            row_values = [format_value(row[i], max_len=40).ljust(col_widths[col_names[i]]) 
                         for i in range(len(col_names))]
            print(" | ".join(row_values))
        
        if limit and count > limit:
            print(f"\n... and {count - limit} more rows")

def main():
    """Main function to display all tables"""
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    
    print("\n" + "=" * 80)
    print("DATABASE CONTENTS")
    print("=" * 80)
    print(f"\nDatabase: {settings.DATABASE_URL}")
    print(f"Total Tables: {len(tables)}")
    print(f"Tables: {', '.join(tables)}")
    
    # Ask for limit
    print("\n" + "=" * 80)
    print("Displaying table contents...")
    print("=" * 80)
    
    # Define custom limits for tables with lots of data
    table_limits = {
        "users": 20,
        "vehicles": 20,
        "schedules": 20,
        "route_stops": 30,
        "stations": None,  # Show all
        "routes": None,    # Show all
        "admins": None     # Show all
    }
    
    for table_name in tables:
        try:
            limit = table_limits.get(table_name, 10)  # Default limit of 10
            print_table_data(table_name, limit=limit)
        except Exception as e:
            print(f"\n✗ Error reading table '{table_name}': {e}")
    
    print("\n" + "=" * 80)
    print("END OF DATABASE CONTENTS")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
