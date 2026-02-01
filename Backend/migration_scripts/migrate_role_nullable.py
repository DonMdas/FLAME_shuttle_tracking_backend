"""
Migration script to make users.role column nullable
This allows onboarding flow where users set their role after signup
"""

import sqlite3
import os
from pathlib import Path

# Get the database path
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "shuttle_tracker.db"

def migrate():
    """Make role column nullable in users table"""
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return
    
    print(f"📁 Database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("\n🔍 Checking current schema...")
        
        # Get current table info
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        
        print("\nCurrent users table columns:")
        for col in columns:
            col_id, name, type_, notnull, default, pk = col
            nullable = "NULL" if notnull == 0 else "NOT NULL"
            print(f"  - {name}: {type_} {nullable}")
        
        # Check if role is already nullable
        role_col = [col for col in columns if col[1] == 'role']
        if role_col and role_col[0][3] == 0:  # notnull == 0 means nullable
            print("\n✅ Role column is already nullable. No migration needed.")
            return
        
        print("\n🔄 Starting migration to make role nullable...")
        
        # SQLite doesn't support ALTER COLUMN, so we need to:
        # 1. Create new table with nullable role
        # 2. Copy data
        # 3. Drop old table
        # 4. Rename new table
        
        # Step 1: Create new table with updated schema
        cursor.execute("""
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(100) NOT NULL UNIQUE,
                hashed_password VARCHAR(255),
                role VARCHAR(20),
                auth_provider VARCHAR(20) NOT NULL,
                is_email_verified BOOLEAN NOT NULL DEFAULT 0,
                otp VARCHAR(6),
                otp_created_at DATETIME,
                google_id VARCHAR(100) UNIQUE,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        print("✓ Created new table with nullable role")
        
        # Step 2: Copy data from old table
        cursor.execute("""
            INSERT INTO users_new 
            SELECT id, email, hashed_password, role, auth_provider, 
                   is_email_verified, otp, otp_created_at, google_id, 
                   is_active, created_at, updated_at
            FROM users
        """)
        row_count = cursor.rowcount
        print(f"✓ Copied {row_count} existing users")
        
        # Step 3: Drop old table
        cursor.execute("DROP TABLE users")
        print("✓ Dropped old table")
        
        # Step 4: Rename new table
        cursor.execute("ALTER TABLE users_new RENAME TO users")
        print("✓ Renamed new table to users")
        
        # Step 5: Recreate indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_role ON users(role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_auth_provider ON users(auth_provider)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_google_id ON users(google_id)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_id ON users(id)")
        print("✓ Recreated indexes")
        
        # Commit changes
        conn.commit()
        
        print("\n✅ Migration completed successfully!")
        print("   Role column is now nullable to support onboarding flow")
        
        # Verify the change
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        role_col = [col for col in columns if col[1] == 'role']
        if role_col:
            nullable = "NULL" if role_col[0][3] == 0 else "NOT NULL"
            print(f"\n✓ Verified: role column is now {nullable}")
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("  MIGRATION: Make users.role column nullable")
    print("=" * 60)
    migrate()
    print("\n" + "=" * 60)
    print("  Migration complete! You can now run signup without role.")
    print("=" * 60)
