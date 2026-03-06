import psycopg2
import time

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "poc",
    "user": "postgres",
    "password": "",
    "host": "localhost",
    "port": "5432"
}

def log_interaction(query, intent, tool, context, response, start_time):
    """
    Saves the interaction details to PostgreSQL.
    """
    try:
        latency = round(time.time() - start_time, 2)
        
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        sql = '''
        INSERT INTO audit_logs (user_query, detected_intent, tool_used, raw_context, final_response, latency_seconds)
        VALUES (%s, %s, %s, %s, %s, %s)
        '''
        
        # Truncate context if it's too huge (optional, keeps DB clean)
        if len(context) > 2000:
            context = context[:2000] + "... [TRUNCATED]"
            
        cursor.execute(sql, (query, intent, tool, context, response, latency))
        
        conn.commit()
        print(f"Log saved. Latency: {latency}s")
        
    except Exception as e:
        print(f"(Audit) Logging failed: {e}")
    finally:
        if conn: conn.close()