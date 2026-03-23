"""
Orchestrator — adapted from main_framework.py.
Returns a structured dict instead of printing to console.
"""
import sys
import os
import time
from typing import List, Dict
from dotenv import load_dotenv

# Ensure the POC root is on the path
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_POC_ROOT    = os.path.dirname(_BACKEND_DIR)
sys.path.insert(0, _POC_ROOT)
load_dotenv(os.path.join(_POC_ROOT, ".env"))

from openai import OpenAI
from SQL.sql_retrieval import text_to_sql_pipeline, execute_sql, update_sql_response
from Vector_DB.chat import query_vector_db
from Logs import logs

client = OpenAI(
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/"),
    api_key=os.getenv("OLLAMA_API_KEY",   "ollama"),
)
MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b-cloud")

# ── Server-side session memory ────────────────────────────────────────────────
_session_sql_memory: Dict[str, str] = {}

# ── Static system prompts (KV-cached by Ollama after first call) ──────────────

_FOLLOWUP_SYSTEM = """You are a conversation classifier. Decide whether the user's NEW message is a follow-up to the previous assistant response, or a completely new, standalone question.

A follow-up:
- References "your previous response", "that table", "the result above", "add X to it", etc.
- Cannot be understood without the previous assistant response.
- Asks to modify, extend, reformat, or clarify the previous answer.

A new question:
- Is self-contained and makes sense on its own.
- Asks about a different topic or different data.

Respond with ONLY one word: FOLLOWUP or NEW"""

_ROUTER_SYSTEM = """You are an Intent Router. Classify the user query into ONE category.

1. SQL: Questions about NUMBERS, HOURS, DATES, RATES, or TIMESHEETS.
2. VECTOR: Questions about REVIEWS, FEEDBACK, OPINIONS, PRAISES, or TEXT SUMMARIES.
3. BOTH: Questions asking for BOTH numbers AND qualitative feedback.

Output ONLY the category name: SQL, VECTOR, or BOTH."""

_DECOMPOSE_SYSTEM = """You are a Query Decomposer. The user has asked a complex question that requires data from TWO sources:
1. SQL Database (Employee hours, rates, project stats)
2. Vector Database (Performance reviews, qualitative feedback, praises)

Break the question into two separate, standalone questions.
- The SQL question should ask ONLY for the specific numbers/stats mentioned.
- The Vector question should ask ONLY for the qualitative review/feedback mentioned.

Output Format:
SQL: [Insert SQL-focused question]
VECTOR: [Insert Vector-focused question]"""

_SYNTH_SYSTEM = """You are an HR Insight Assistant. Answer the user's question using data retrieved from SQL and/or Vector databases.

Instructions:
- Use SQL data for numeric insights (hours, rates, project stats).
- Use Vector data for qualitative insights (reviews, feedback, praises).
- If the user asked for a comparison, explicitly compare numbers with text insights.
- Always provide a clear, concise answer that directly addresses the question.
- Avoid repeating the data; synthesize it into actionable insights.
- Provide a final recommendation if the data suggests one.
- Use markdown formatting (bold, lists, tables) for clarity.
- Be concise and professional."""

_FOLLOWUP_SYNTH_SYSTEM = """You are an HR Insight Assistant. Answer the user's follow-up question using the SQL data provided.

Instructions:
- Use ONLY the data provided — do NOT invent numbers.
- Add a brief 1–2 sentence insight below your answer.
- Use markdown formatting."""


# ── Follow-up Classifier ──────────────────────────────────────────────────────
def is_followup(question: str, history: List[Dict]) -> bool:
    print("\n" + "─" * 55)
    print("FOLLOW-UP CLASSIFIER")
    print(f"Query : {question[:80]}{'...' if len(question) > 80 else ''}")

    if not history:
        print("Decision : SKIPPED - no conversation history yet")
        print("─" * 55)
        return False

    last_assistant = next(
        (m["content"] for m in reversed(history) if m["role"] == "assistant"), ""
    )
    if not last_assistant:
        print("Decision : SKIPPED - no prior assistant message found")
        print("─" * 55)
        return False

    user_msg = (
        f'Previous assistant response (last 500 chars):\n"""\n{last_assistant[-500:]}\n"""\n\n'
        f'New user message: "{question}"'
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _FOLLOWUP_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.0
    )
    decision = response.choices[0].message.content.strip().upper()
    verdict = "FOLLOWUP - skipping router" if "FOLLOWUP" in decision else "NEW - sending to intent router"

    print(f"History turns  : {len(history)}")
    print(f"Last AI snippet: ...{last_assistant[-100:].strip()!r}")
    print(f"Decision       : {verdict}")
    print("─" * 55)

    return "FOLLOWUP" in decision


# ── Follow-up Handler (dispatcher) ───────────────────────────────────────────
def handle_followup(query: str, history: List[Dict]) -> dict:
    """
    Routes a classified follow-up:
    - If the server memory has a prior SQL query  → update_sql_response (real DB data)
    - Otherwise (VECTOR / general follow-up)       → LLM-only path
    """
    prior_sql = _session_sql_memory.get("last_sql")

    if prior_sql:
        print(f"\n(Follow-up Handler) Found prior SQL in memory — calling update_sql_response")
        print(f"Prior SQL: {prior_sql[:120]}{'...' if len(prior_sql) > 120 else ''}")

        sql_data = update_sql_response(query, prior_sql)

        if sql_data.get("sql_query"):
            _session_sql_memory["last_sql"] = sql_data["sql_query"]

        if sql_data.get("error"):
            return {
                "response_text": f"SQL update failed: {sql_data['error']}",
                "intent": "FOLLOWUP",
                "evidence": {
                    "sql_query": sql_data.get("sql_query"),
                    "sql_columns": None,
                    "sql_table": None,
                    "vector_context": None,
                    "vector_sources": None,
                    "latency": 0.0,
                }
            }

        columns = sql_data.get("columns") or []
        rows    = sql_data.get("rows") or []

        rows_preview = "\n".join(str(r) for r in rows[:30])
        table_note = (
            f"The result has {len(rows)} rows. DO NOT reproduce the full table. "
            "Give a brief summary and tell the user: 'The full data is available in the Evidence Drawer below.'"
        ) if len(rows) > 10 else "Present as a clean markdown table."

        user_msg = (
            f'Follow-up request: "{query}"\n\n'
            f"SQL executed:\n{sql_data['sql_query']}\n\n"
            f"Columns: {columns}\n"
            f"Data ({len(rows)} rows):\n{rows_preview}\n\n"
            f"Table instruction: {table_note}"
        )

        synth = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _FOLLOWUP_SYNTH_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.3
        )
        response_text = synth.choices[0].message.content.strip()

        return {
            "response_text": response_text,
            "intent": "FOLLOWUP",
            "evidence": {
                "sql_query": sql_data["sql_query"],
                "sql_columns": list(columns),
                "sql_table": rows,
                "vector_context": None,
                "vector_sources": None,
                "latency": 0.0,
            }
        }

    # Fallback: no prior SQL — use conversation context
    print("(Follow-up Handler) No prior SQL in memory — using LLM-only path")
    messages = [
        {
            "role": "system",
            "content": (
                "You are an HR Insight Assistant. The user is asking a follow-up question "
                "based on your previous response. Use the conversation history to answer accurately. "
                "Preserve and extend any tables or structured data from your previous response. "
                "Use markdown formatting for clarity."
            )
        }
    ]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": query})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7
    )
    response_text = response.choices[0].message.content.strip()

    return {
        "response_text": response_text,
        "intent": "FOLLOWUP",
        "evidence": {
            "sql_query": None,
            "sql_columns": None,
            "sql_table": None,
            "vector_context": None,
            "vector_sources": None,
            "latency": 0.0,
        }
    }


# ── Router ─────────────────────────────────────────────────────────────────────
def decide_route(question: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _ROUTER_SYSTEM},
            {"role": "user",   "content": question},
        ],
        temperature=0.1
    )
    choice = response.choices[0].message.content.strip().upper()
    print(f"(Router) Raw LLM output: '{choice}'")

    words = [w.strip(".,") for w in choice.split()]
    if "BOTH" in words:
        return "BOTH"
    if "VECTOR" in words:
        return "VECTOR"
    if "SQL" in words:
        return "SQL"

    print("(Router) Could not parse response cleanly — defaulting to VECTOR")
    return "VECTOR"


# ── Decomposer ─────────────────────────────────────────────────────────────────
def decompose_query(complex_question: str):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _DECOMPOSE_SYSTEM},
            {"role": "user",   "content": complex_question},
        ],
        temperature=0.1
    )
    result = response.choices[0].message.content.strip()

    sql_q, vector_q = "", ""
    for line in result.split('\n'):
        if line.startswith("SQL:"):
            sql_q = line.replace("SQL:", "").strip()
        elif line.startswith("VECTOR:"):
            vector_q = line.replace("VECTOR:", "").strip()

    return sql_q or complex_question, vector_q or complex_question


# ── Synthesizer ────────────────────────────────────────────────────────────────
def synthesize_answer(user_input: str, final_context: str, row_count: int = 0) -> str:
    table_instruction = (
        f"The result has {row_count} rows. DO NOT reproduce the full table. "
        "Instead, give a brief summary (totals, max, min, averages as relevant) and tell the user: "
        "'The full data is available in the Evidence Drawer below.'"
        if row_count > 10
        else "If SQL data is present, include it as a clean markdown table in your answer."
    )

    user_msg = (
        f"User Question: {user_input}\n\n"
        f"Data Retrieved:\n{final_context}\n\n"
        f"Table instruction: {table_instruction}"
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYNTH_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


# ── Main Entry Point ───────────────────────────────────────────────────────────
def process_query(query: str, history: List[Dict] = None) -> dict:
    if history is None:
        history = []
    start_time = time.time()

    # ── Follow-up check (bypasses router entirely) ────────────────────────────
    if is_followup(query, history):
        print(f"\n{'='*40}")
        print(f"  ROUTER DECISION: FOLLOWUP (skipped router)")
        print(f"  Query: '{query[:80]}{'...' if len(query) > 80 else ''}'")
        print(f"{'='*40}")
        result = handle_followup(query, history)
        result["evidence"]["latency"] = round(time.time() - start_time, 2)
        return result

    # 1. Route
    intent = decide_route(query)
    print(f"\n{'='*40}")
    print(f"  ROUTER DECISION: {intent}")
    print(f"  Query: '{query[:80]}{'...' if len(query) > 80 else ''}'")
    print(f"{'='*40}")

    sql_query_str = None
    sql_columns   = None
    sql_table     = None
    vector_context = None
    vector_sources = None
    final_context_for_llm = ""

    # 2. Execute
    if intent == "SQL":
        sql_data = text_to_sql_pipeline(query)
        sql_query_str = sql_data.get("sql_query")
        sql_columns   = sql_data.get("columns")
        sql_table     = sql_data.get("rows")
        if sql_query_str:
            _session_sql_memory["last_sql"] = sql_query_str
            print(f"   (Memory) Saved SQL to session memory")
        if sql_columns and sql_table:
            rows_text = "\n".join(str(row) for row in sql_table)
            final_context_for_llm = f"Columns: {sql_columns}\nData:\n{rows_text}"
        else:
            final_context_for_llm = sql_data.get("error", "No data returned.")

    elif intent == "VECTOR":
        vec_data = query_vector_db(query)
        vector_context = vec_data.get("context")
        vector_sources = vec_data.get("sources")
        final_context_for_llm = vector_context or "No context found."
        _session_sql_memory.pop("last_sql", None)

    elif intent == "BOTH":
        sql_sub_q, vector_sub_q = decompose_query(query)

        sql_data = text_to_sql_pipeline(sql_sub_q)
        sql_query_str = sql_data.get("sql_query")
        sql_columns   = sql_data.get("columns")
        sql_table     = sql_data.get("rows")
        if sql_query_str:
            _session_sql_memory["last_sql"] = sql_query_str
            print(f"(Memory) Saved SQL to session memory")

        vec_data = query_vector_db(vector_sub_q)
        vector_context = vec_data.get("context")
        vector_sources = vec_data.get("sources")

        sql_text = (
            f"Columns: {sql_columns}\nData:\n" + "\n".join(str(r) for r in sql_table)
            if sql_columns and sql_table
            else sql_data.get("error", "No SQL data.")
        )
        final_context_for_llm = (
            f"--- NUMERIC DATA (SQL) ---\n{sql_text}\n\n"
            f"--- PERFORMANCE REVIEWS (TEXT) ---\n{vector_context or 'No vector data.'}"
        )

    # 3. Synthesize
    row_count = len(sql_table) if sql_table else 0
    response_text = synthesize_answer(query, final_context_for_llm, row_count=row_count)

    # 4. Log
    logs.log_interaction(
        query=query,
        intent=intent,
        tool="Hybrid" if intent == "BOTH" else intent,
        context=final_context_for_llm,
        response=response_text,
        start_time=start_time
    )

    latency = round(time.time() - start_time, 2)

    return {
        "response_text": response_text,
        "intent": intent,
        "evidence": {
            "sql_query": sql_query_str,
            "sql_columns": sql_columns,
            "sql_table": sql_table,
            "vector_context": vector_context,
            "vector_sources": vector_sources,
            "latency": latency,
        }
    }
