import os
import psycopg2
from psycopg2 import sql
import random
from datetime import date, timedelta
from dotenv import load_dotenv

_POC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_POC_ROOT, ".env"))

# ==========================================
# 1. DATABASE CONFIGURATION
# ==========================================
DB_CONFIG = {
    "dbname":   os.getenv("POSTGRES_DB",       "poc"),
    "user":     os.getenv("POSTGRES_USER",     "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "host":     os.getenv("POSTGRES_HOST",     "localhost"),
    "port":     os.getenv("POSTGRES_PORT",     "5432"),
}

# ==========================================
# 2. DATA GENERATION (The 5 Employees)
# ==========================================
employees_data = [
    {
        "name": "Alex Rivera", 
        "role": "Senior Backend Engineer", 
        "dept": "Engineering", 
        "manager": "Jordan Smith", 
        "joined": "2023-05-15", 
        "email": "alex.rivera@company.com",
        "annual_salary": 145000
    },
    {
        "name": "Sarah Jenkins", 
        "role": "Junior Marketing Associate", 
        "dept": "Marketing", 
        "manager": "Elena Rodriguez", 
        "joined": "2025-09-01", 
        "email": "sarah.jenkins@company.com",
        "annual_salary": 62000
    },
    {
        "name": "David Chen", 
        "role": "HR Manager", 
        "dept": "Human Resources", 
        "manager": "Marcus Thorne", 
        "joined": "2021-11-20", 
        "email": "david.chen@company.com",
        "annual_salary": 98000
    },
    {
        "name": "Priyesh Patel", 
        "role": "Junior DevOps Engineer", 
        "dept": "Engineering", 
        "manager": "Samira Khan", 
        "joined": "2025-08-10", 
        "email": "priyesh.patel@company.com",
        "annual_salary": 78000
    },
    {
        "name": "Maya Johnson", 
        "role": "IT Support Specialist", 
        "dept": "IT", 
        "manager": "David Ross", 
        "joined": "2024-03-01", 
        "email": "maya.johnson@company.com",
        "annual_salary": 58000
    }
]

# Generate Weekly Dates (Fridays) from Oct 2025 to Feb 2026
week_ending_dates = []
current_date = date(2025, 10, 3) # First Friday of Oct 2025
end_date = date(2026, 2, 28)

while current_date <= end_date:
    week_ending_dates.append(current_date)
    current_date += timedelta(days=7)

# Generate Monthly Pay Dates (End of Month)
pay_dates = [
    date(2025, 10, 31),
    date(2025, 11, 30),
    date(2025, 12, 31),
    date(2026, 1, 31),
    date(2026, 2, 28)
]

# ==========================================
# 3. SQL COMMANDS
# ==========================================
DDL_COMMANDS = [
    # Drop tables if they exist (Clean Slate)
    "DROP TABLE IF EXISTS timesheets CASCADE;",
    "DROP TABLE IF EXISTS billing_finances CASCADE;",
    "DROP TABLE IF EXISTS employees CASCADE;",

    # 1. Employees Table
    """
    CREATE TABLE employees (
        emp_id SERIAL PRIMARY KEY,
        full_name VARCHAR(100) NOT NULL UNIQUE, -- Unique constraint matches Vector DB logic
        role VARCHAR(100),
        department VARCHAR(100),
        manager_name VARCHAR(100),
        date_joined DATE,
        email VARCHAR(150),
        annual_salary NUMERIC(10, 2),
        is_active BOOLEAN DEFAULT TRUE
    );
    """,

    # 2. Timesheets Table (Weekly)
    """
    CREATE TABLE timesheets (
        timesheet_id SERIAL PRIMARY KEY,
        emp_id INTEGER REFERENCES employees(emp_id),
        week_ending_date DATE NOT NULL,
        hours_worked NUMERIC(5, 2),
        overtime_hours NUMERIC(5, 2) DEFAULT 0,
        projects_worked TEXT,
        status VARCHAR(20) DEFAULT 'Approved'
    );
    """,

    # 3. Billing/Finances Table (Monthly)
    """
    CREATE TABLE billing_finances (
        record_id SERIAL PRIMARY KEY,
        emp_id INTEGER REFERENCES employees(emp_id),
        pay_period_end DATE NOT NULL,
        gross_pay NUMERIC(10, 2),
        tax_deductions NUMERIC(10, 2),
        benefits_deduction NUMERIC(10, 2),
        net_pay NUMERIC(10, 2),
        currency VARCHAR(3) DEFAULT 'USD'
    );
    """
]

# ==========================================
# 4. EXECUTION FUNCTION
# ==========================================
def create_database():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("Connected to Database")

        # --- A. CREATE TABLES ---
        for command in DDL_COMMANDS:
            cur.execute(command)
        print("Tables Created (employees, timesheets, billing_finances)")

        # --- B. INSERT EMPLOYEES ---
        emp_name_to_id = {} # Map name to DB ID for foreign keys
        
        for emp in employees_data:
            cur.execute("""
                INSERT INTO employees (full_name, role, department, manager_name, date_joined, email, annual_salary)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING emp_id;
            """, (emp['name'], emp['role'], emp['dept'], emp['manager'], emp['joined'], emp['email'], emp['annual_salary']))
            
            new_id = cur.fetchone()[0]
            emp_name_to_id[emp['name']] = new_id
            print(f"   -> Inserted Employee: {emp['name']} (ID: {new_id})")

        # --- C. INSERT TIMESHEETS (22 Weeks per Employee) ---
        print("   -> Inserting Timesheets...")
        for name, emp_id in emp_name_to_id.items():
            for week_date in week_ending_dates:
                # Randomize hours slightly for realism
                if name == "Alex Rivera": # Works hard (burnout risk mentioned in reports)
                    hours = random.choice([40, 45, 50, 60]) 
                elif name == "Maya Johnson": # Crisis month in Dec
                    hours = 55 if week_date.month == 12 else 40
                else:
                    hours = 40

                cur.execute("""
                    INSERT INTO timesheets (emp_id, week_ending_date, hours_worked, projects_worked)
                    VALUES (%s, %s, %s, %s);
                """, (emp_id, week_date, hours, "Standard Duties"))

        # --- D. INSERT FINANCES (5 Months per Employee) ---
        print("   -> Inserting Financial Records...")
        for name, emp_id in emp_name_to_id.items():
            salary = next(e['annual_salary'] for e in employees_data if e['name'] == name)
            monthly_gross = round(salary / 12, 2)
            
            for pay_date in pay_dates:
                # Basic tax calc (30% approx)
                tax = round(monthly_gross * 0.25, 2)
                benefits = 200.00
                net = monthly_gross - tax - benefits

                cur.execute("""
                    INSERT INTO billing_finances (emp_id, pay_period_end, gross_pay, tax_deductions, benefits_deduction, net_pay)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (emp_id, pay_date, monthly_gross, tax, benefits, net))

        # Commit all changes
        conn.commit()
        cur.close()
        conn.close()
        print("\nSUCCESS: Database populated with 5 months of synthetic data!")

    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    create_database()