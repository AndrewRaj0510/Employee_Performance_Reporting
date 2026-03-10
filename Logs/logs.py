import os
import psycopg2
import time
from dotenv import load_dotenv

# Load .env from the POC root (two levels up from Logs/)
_POC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_POC_ROOT, ".env"))

DB_CONFIG = {
    "dbname":   os.getenv("POSTGRES_DB",       "poc"),
    "user":     os.getenv("POSTGRES_USER",     "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "host":     os.getenv("POSTGRES_HOST",     "localhost"),
    "port":     os.getenv("POSTGRES_PORT",     "5432"),
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