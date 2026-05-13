import psycopg2
import json
import time
import os
import config

DB_URL = config.DATABASE_URL

def get_conn():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # --- Scrapes Table ---
    c.execute('''CREATE TABLE IF NOT EXISTS scrapes 
                 (user_id BIGINT PRIMARY KEY, url TEXT, title TEXT, created_at REAL, items TEXT)''')
    
    # --- Preferences Table ---
    c.execute('''CREATE TABLE IF NOT EXISTS preferences 
                 (user_id BIGINT PRIMARY KEY, upload_file BOOLEAN, default_category TEXT, expiry_minutes INTEGER, page_size INTEGER DEFAULT 6)''')
    
    conn.commit()
    conn.close()

def save_scrape(user_id, url, title, items):
    conn = get_conn()
    c = conn.cursor()
    items_json = json.dumps(items)
    c.execute("""INSERT INTO scrapes (user_id, url, title, items, created_at) 
                 VALUES (%s, %s, %s, %s, %s)
                 ON CONFLICT (user_id) DO UPDATE SET 
                 url = EXCLUDED.url, title = EXCLUDED.title, items = EXCLUDED.items, created_at = EXCLUDED.created_at""",
              (user_id, url, title, items_json, time.time()))
    conn.commit()
    conn.close()

def get_scrape(user_id):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT url, title, items, created_at FROM scrapes WHERE user_id = %s", (user_id,))
        row = c.fetchone()
    except Exception as e:
        print(f"DB Error get_scrape: {e}")
        row = None
    finally:
        conn.close()
    
    if row:
        return {"url": row[0], "title": row[1], "items": json.loads(row[2]), "created_at": row[3]}
    return None

def get_prefs(user_id):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT upload_file, default_category, expiry_minutes, page_size FROM preferences WHERE user_id = %s", (user_id,))
        row = c.fetchone()
    except Exception as e:
        print(f"DB Error get_prefs: {e}")
        row = None
    finally:
        conn.close()
        
    if row:
        return {
            "upload_file": bool(row[0]),
            "default_category": row[1],
            "expiry_minutes": row[2],
            "page_size": row[3] if row[3] else 6
        }
    return {"upload_file": True, "default_category": "ask", "expiry_minutes": 10, "page_size": 6}

def save_prefs(user_id, prefs):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO preferences (user_id, upload_file, default_category, expiry_minutes, page_size) 
                 VALUES (%s, %s, %s, %s, %s)
                 ON CONFLICT (user_id) DO UPDATE SET 
                 upload_file = EXCLUDED.upload_file, default_category = EXCLUDED.default_category, 
                 expiry_minutes = EXCLUDED.expiry_minutes, page_size = EXCLUDED.page_size""",
              (user_id, bool(prefs.get("upload_file", True)), prefs.get("default_category", "ask"), 
               prefs.get("expiry_minutes", 10), prefs.get("page_size", 6)))
    conn.commit()
    conn.close()

def clear_old_scrapes(expiry_seconds=3600):
    conn = get_conn()
    c = conn.cursor()
    now = time.time()
    c.execute("DELETE FROM scrapes WHERE created_at < %s", (now - expiry_seconds,))
    conn.commit()
    conn.close()

# Initialize DB on import
try:
    init_db()
except Exception as e:
    print(f"Failed to initialize PostgreSQL: {e}")
