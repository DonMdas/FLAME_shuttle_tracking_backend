import sqlite3

conn = sqlite3.connect("shuttle_tracker.db")
cursor = conn.cursor()

cursor.execute("""
    DELETE FROM vehicles
    WHERE vehicle_id BETWEEN 1 AND 10
""")

conn.commit()
conn.close()

print("Deleted vehicles with IDs 1–10.")
