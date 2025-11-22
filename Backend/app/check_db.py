import sqlite3
import os

db_path = "shuttle_tracker.db"

print(f"Checking database: {db_path}")
print(f"File exists: {os.path.exists(db_path)}")
print(f"File size: {os.path.getsize(db_path) if os.path.exists(db_path) else 0} bytes")
print()

if not os.path.exists(db_path):
    print("❌ Database file not found!")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Fetch table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]

if not tables:
    print("❌ No tables found - database not initialized!")
    conn.close()
    exit()

print(f"✅ Found {len(tables)} table(s):")
for table in tables:
    print(f"  - {table}")
print()

# Display structure of each table
for table in tables:
    print(f"📌 Table: {table}")
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    
    if not columns:
        print("  ❗ No column info found (possible internal table).\n")
        continue

    for col in columns:
        cid, name, dtype, notnull, default, pk = col
        print(f"  {name:20} {dtype:15} {'NOT NULL' if notnull else ''}")
    print()

conn.close()
