import psycopg2

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "poc",
    "user": "postgres",
    "password": "",  # <--- REPLACE THIS
    "host": "localhost",
    "port": "5432"
}

def create_audit_table():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("Creating 'techies_audit_logs' table...")
        
        # We store: Timestamp, User Query, Detected Intent, Tool Output, and Final Answer
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS techies_audit_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_query TEXT,
            detected_intent TEXT,
            tool_used TEXT,
            raw_context TEXT,
            final_response TEXT,
            latency_seconds NUMERIC(5, 2)
        );
        ''')
        
        conn.commit()
        print("✅ Success! Table 'techies_audit_logs' is ready.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    create_audit_table()