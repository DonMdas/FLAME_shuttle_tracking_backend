"""
Migration script to add feedbacks table.
This table stores user feedback about rides, routes, and services.

Run this script to create the feedbacks table in the database.
Run from Backend directory: python migration_scripts/add_feedbacks_table.py
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
    """Create feedbacks table"""
    db = SessionLocal()
    
    try:
        print("Starting migration: Create feedbacks table")
        
        # Check if table already exists
        check_table_query = text("""
            SELECT COUNT(*) 
            FROM sqlite_master 
            WHERE type='table' AND name='feedbacks'
        """)
        
        result = db.execute(check_table_query)
        table_exists = result.scalar() > 0
        
        if table_exists:
            print("✓ Table 'feedbacks' already exists")
            return
        
        # Create feedbacks table
        print("\nCreating feedbacks table...")
        create_table_query = text("""
            CREATE TABLE feedbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                is_anonymous BOOLEAN NOT NULL DEFAULT 0,
                
                feedback_type VARCHAR(50) NOT NULL,
                category VARCHAR(50),
                
                vehicle_id INTEGER,
                route_id VARCHAR(100),
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
                
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE SET NULL,
                FOREIGN KEY (route_id) REFERENCES routes(route_id) ON DELETE SET NULL,
                FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE SET NULL,
                FOREIGN KEY (resolved_by) REFERENCES admins(id) ON DELETE SET NULL
            )
        """)
        
        db.execute(create_table_query)
        db.commit()
        print("✓ Created feedbacks table")
        
        # Create indexes for better query performance
        print("\nCreating indexes...")
        
        indexes = [
            ("idx_feedbacks_user_id", "user_id"),
            ("idx_feedbacks_feedback_type", "feedback_type"),
            ("idx_feedbacks_category", "category"),
            ("idx_feedbacks_status", "status"),
            ("idx_feedbacks_vehicle_id", "vehicle_id"),
            ("idx_feedbacks_route_id", "route_id"),
            ("idx_feedbacks_created_at", "created_at")
        ]
        
        for idx_name, column in indexes:
            create_index_query = text(f"""
                CREATE INDEX {idx_name} ON feedbacks({column})
            """)
            db.execute(create_index_query)
            print(f"  ✓ Created index: {idx_name}")
        
        db.commit()
        
        print("\n" + "="*50)
        print("Migration Summary:")
        print("="*50)
        print("✓ feedbacks table created")
        print("✓ 7 indexes created")
        print("✓ Foreign key constraints set up")
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
    print("Database Migration: Create feedbacks table")
    print("="*50 + "\n")
    
    try:
        run_migration()
    except Exception as e:
        sys.exit(1)
