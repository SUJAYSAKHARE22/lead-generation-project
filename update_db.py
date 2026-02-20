import sqlite3

conn = sqlite3.connect("leads.db")
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE companies ADD COLUMN chat_id INTEGER")
    print("✅ chat_id column added successfully.")
except Exception as e:
    print("⚠️ Maybe column already exists:", e)

conn.commit()
conn.close()
