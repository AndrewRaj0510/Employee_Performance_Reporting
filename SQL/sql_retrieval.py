import os
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

# Load .env from the POC root (two levels up from SQL/)
_POC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_POC_ROOT, ".env"))

DB_CONFIG = {
    "dbname":   os.getenv("POSTGRES_DB",       "poc"),
    "user":     os.getenv("POSTGRES_USER",     "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "host":     os.getenv("POSTGRES_HOST",     "localhost"),
    "port":     os.getenv("POSTGRES_PORT",     "5432"),
}

client = OpenAI(
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/"),
    api_key=os.getenv("OLLAMA_API_KEY",   "ollama"),
)
MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b-cloud")


def execute_sql(query):
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query)
        colnames = [desc[0] for desc in cursor.description]
        results = cursor.fetchall()
        return colnames, results
    except Exception as e:
        return None, str(e)
    finally:
        if conn: conn.close()

def text_to_sql_pipeline(user_question):
    """
    Converts natural language to SQL, runs it, and returns a structured dict.
    Returns: { "sql_query": str, "columns": list|None, "rows": list|None, "error": str|None }
    """
    print(f"   (SQL Tool) Thinking about: '{user_question}'...")

    prompt = f"""
    You are a SQL Assistant. Convert the user's question into a PostgreSQL query.
    
    Table: timesheets
  - timesheet_id, emp_id, week_ending_date, hours_worked, overtime_hours, projects_worked, status

    Table: employees
  - emp_id, full_name, role, department, manager_name, date_joined, email, annual_salary, is_active

    Table: billing_finances
  - record_id, emp_id, pay_period_end, gross_pay, tax_deductions, benefits_deduction, net_pay, currency

    emp_id is the primary key in employees and a foreign key in timesheets.

    RULES:
    1. KEEP IT SIMPLE: Write the most basic, straightforward query possible. Rely on simple SELECT, WHERE, GROUP BY, and ORDER BY clauses. 
    2. NO COMPLEX LOGIC: Do NOT use Window Functions (OVER/PARTITION), Common Table Expressions (WITH), or complex nested subqueries.
    3. THE DATE RULE (STRICT): NEVER apply default date, month, or year filters (e.g., never add `WHERE EXTRACT(YEAR FROM date) = 2026`). ONLY filter by date/year if the user EXPLICITLY asks for a specific year in the prompt(Ex:- '2026' or in  'the year 2026' or 'in 2026'). If no timeframe is requested, query all available history.
    4. NO EXPLANATIONS: Return ONLY the raw executable SQL query. Do not include markdown formatting (like ```sql), backticks, or conversational text.
    5. Use join to combine tables if needed.
    6. If questions are asked about departments/roles always group them.
    
    User Question: {user_question}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-oss:20b-cloud",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        sql_query = response.choices[0].message.content.strip()
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
        
        print(f"(SQL Tool) Executing: {sql_query}")
        columns, data = execute_sql(sql_query)
        
        if columns is None:
            # data is the error string when columns is None
            return {"sql_query": sql_query, "columns": None, "rows": None, "error": f"SQL Error: {data}"}
        elif not data:
            return {"sql_query": sql_query, "columns": columns, "rows": [], "error": "Query returned no data."}
        else:
            # Convert tuples to lists so the result is JSON-serialisable
            rows = [list(row) for row in data]
            return {"sql_query": sql_query, "columns": columns, "rows": rows, "error": None}

    except Exception as e:
        return {"sql_query": "", "columns": None, "rows": None, "error": f"Error communicating with Ollama: {e}"}


def update_sql_response(followup_question: str, prior_sql: str):
    """
    Takes an existing SQL query and a follow-up user request.
    Uses an LLM to minimally rewrite the SQL, executes it, and returns
    the same structured dict as text_to_sql_pipeline.

    Returns: { "sql_query": str, "columns": list|None, "rows": list|None, "error": str|None }
    """
    print(f"(SQL Update Tool) Prior SQL  : {prior_sql}")
    print(f"(SQL Update Tool) Follow-up  : '{followup_question}'")

    prompt = f"""
    You are a PostgreSQL expert. Rewrite the SQL query below to satisfy the user's follow-up request.

    === PREVIOUS SQL QUERY ===
    {prior_sql}

    === DATABASE SCHEMA ===
    Table: timesheets
    - timesheet_id, emp_id, week_ending_date, hours_worked, overtime_hours, projects_worked, status

    Table: employees
    - emp_id, full_name, role, department, manager_name, date_joined, email, annual_salary, is_active

    Table: billing_finances
    - record_id, emp_id, pay_period_end, gross_pay, tax_deductions, benefits_deduction, net_pay, currency

    emp_id is the primary key in employees and a foreign key in timesheets and billing_finances.

    === USER FOLLOW-UP REQUEST ===
    "{followup_question}"

    === RULES ===
    1. Keep changes minimal — only add/remove columns, joins, or filters as needed.
    2. NEVER add date/year filters unless the user explicitly requests a specific date/year.
    3. Do NOT use Window Functions (OVER/PARTITION), CTEs (WITH), or complex nested subqueries.
    4. Return ONLY the raw executable SQL. No markdown, no backticks, no explanation.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-oss:20b-cloud",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )

        updated_sql = response.choices[0].message.content.strip()
        updated_sql = updated_sql.replace("```sql", "").replace("```", "").strip()

        print(f"(SQL Update Tool) Updated SQL: {updated_sql}")

        columns, data = execute_sql(updated_sql)

        if columns is None:
            return {"sql_query": updated_sql, "columns": None, "rows": None, "error": f"SQL Error: {data}"}
        elif not data:
            return {"sql_query": updated_sql, "columns": columns, "rows": [], "error": "Query returned no data."}
        else:
            rows = [list(row) for row in data]
            return {"sql_query": updated_sql, "columns": columns, "rows": rows, "error": None}

    except Exception as e:
        return {"sql_query": "", "columns": None, "rows": None, "error": f"Error communicating with Ollama: {e}"}


# --- TEST BLOCK (Only runs if you run this file directly) ---
if __name__ == "__main__":
    print("--- SQL TOOL TEST MODE ---")
    while True:
        q = input("SQL Query: ")
        if q == "exit": break
        result = text_to_sql_pipeline(q)
        if result["error"]:
            print(f"Error: {result['error']}")
        else:
            print(f"SQL: {result['sql_query']}")
            print(f"Columns: {result['columns']}")
            for row in result["rows"]:
                print(row)
