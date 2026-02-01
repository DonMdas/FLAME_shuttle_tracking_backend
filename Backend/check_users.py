import sqlite3

conn = sqlite3.connect('shuttle_tracker.db')
cursor = conn.cursor()

# Check schema
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()

print("\n📋 Users table schema:")
for col in columns:
    col_id, name, type_, notnull, default, pk = col
    nullable = "NULL" if notnull == 0 else "NOT NULL"
    print(f"  {name:20} {type_:15} {nullable}")

# Check existing users
cursor.execute('SELECT id, email, role, auth_provider, is_email_verified FROM users')
users = cursor.fetchall()

print("\n👥 Existing users:")
if users:
    for user in users:
        role_display = user[2] if user[2] else "None (onboarding)"
        verified = "✓ Verified" if user[4] else "✗ Not verified"
        print(f"  ID {user[0]}: {user[1]}")
        print(f"         Role: {role_display} | Provider: {user[3]} | {verified}")
else:
    print("  No users found")

conn.close()
