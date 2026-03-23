# Hybrid RAG HR Analytics System

A full-stack HR analytics platform that routes natural language queries to **PostgreSQL** (structured data) or **ChromaDB** (unstructured documents), or both, and synthesizes responses using an LLM via Ollama.

Ask questions like *"How many hours did Alex work last month?"* (SQL) or *"What does David's performance review say?"* (Vector) — the system automatically picks the right data source.

---

## Architecture

```
Browser → POST /api/chat → FastAPI (backend/main.py)
                               ↓
                        orchestrator.process_query()
                               ↓
              ┌── decide_route() → SQL | VECTOR | BOTH
              │
              ├── SQL path:    text_to_sql_pipeline() → PostgreSQL
              ├── VECTOR path: query_vector_db()      → ChromaDB
              └── BOTH:        decompose → run both   → merge
                               ↓
                        synthesize_answer() via Ollama LLM
                               ↓
                        log_interaction() → techies_audit_logs table
                               ↓
                        ChatResponse { text, intent, evidence }
```

### How It Works

1. **Intent Router** — An LLM classifies each query as `SQL`, `VECTOR`, or `BOTH`.
2. **SQL Path** — Converts natural language to PostgreSQL via LLM, executes the query, and returns structured rows/columns.
3. **Vector Path** — Performs semantic similarity search against ChromaDB using HuggingFace embeddings (`all-MiniLM-L6-v2`).
4. **BOTH Path** — Decomposes the query into an SQL sub-question and a Vector sub-question, runs both, then merges the results.
5. **Follow-up Detection** — Classifies whether a new message is a follow-up to the previous response. If so, it rewrites the prior SQL query instead of re-routing.
6. **Synthesis** — An LLM combines all retrieved data into a clear, markdown-formatted answer.
7. **Audit Logging** — Every interaction is logged to the `techies_audit_logs` PostgreSQL table with query, intent, response, and latency.

---

## Project Structure

```
POC/
├── backend/
│   ├── main.py                  # FastAPI app, /api/chat endpoint, CORS
│   ├── orchestrator.py          # Query routing, follow-up detection, synthesis, session memory
│   └── requirements_backend.txt # Backend-specific Python dependencies
│
├── SQL/
│   ├── sql_retrieval.py         # NL → SQL conversion via LLM, query execution against PostgreSQL
│   └── create_tables.py         # Database table creation scripts
│
├── Vector_DB/
│   ├── chat.py                  # Semantic similarity search via ChromaDB
│   ├── store_documents.py       # Embeds performance_reviews/ docs into chroma_db_local/
│   ├── store_techies.py         # Embeds Techies/ data into chroma_db_techies/
│   └── unzip.py                 # Utility to extract zipped document archives
│
├── Logs/
│   └── logs.py                  # Writes all queries/responses to techies_audit_logs table
│
├── frontend/
│   ├── app/                     # Next.js app router (layout, page, globals)
│   ├── components/
│   │   ├── ChatInterface.tsx    # Main chat UI component
│   │   ├── EvidenceDrawer.tsx   # Side drawer showing SQL queries and vector sources
│   │   └── InsightCard.tsx      # Card component for displaying insights
│   └── lib/
│       ├── types.ts             # TypeScript type definitions
│       └── theme-context.tsx    # Theme provider
│
├── performance_reviews/         # Source .docx files (employee performance reviews)
│   ├── Alex_Rivera_2025-01_Oct.docx
│   ├── David_Chen_2025-02_Nov.docx
│   ├── Maya_Johnson_2025-03_Dec.docx
│   └── ... (25 review documents across 5 employees, Oct 2025 – Feb 2026)
│
├── chroma_db_local/             # ChromaDB persistent storage (auto-generated from performance_reviews/)
│
├── create_audit.py              # Creates the techies_audit_logs table in PostgreSQL
├── main_framework.py            # Standalone CLI version of the orchestrator
├── requirements.txt             # Core Python dependencies
└── .env                         # Environment variables (not committed)
```

### Data Sources

| Source | Type | Tables / Collections | Description |
|--------|------|---------------------|-------------|
| **PostgreSQL** | Structured | `techies_employees`, `techies_timesheets` | Employee records, timesheet hours, project assignments |
| **ChromaDB** | Unstructured | `performance_reviews` collection | Embedded .docx performance reviews for semantic search |
| **PostgreSQL** | Audit | `techies_audit_logs` | Auto-logged query history with intent, response, and latency |

### `performance_reviews/` Folder

Contains `.docx` performance review documents for employees. These are the source documents that get chunked, embedded with HuggingFace `all-MiniLM-L6-v2`, and stored in ChromaDB. File naming convention: `{FirstName}_{LastName}_{Sequence}_{Month}.docx`.

### `chroma_db_local/` Folder

This is the **ChromaDB persistent vector database** directory. It is auto-generated when you run `store_documents.py`, which reads all `.docx` files from `performance_reviews/`, splits them into chunks, generates embeddings, and persists them here. This folder contains:
- SQLite metadata (`chroma.sqlite3`)
- Binary embedding vectors (`data_level0.bin`)
- Index files for fast similarity search

You can regenerate this folder at any time by re-running the embedding script.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15, React 19, TypeScript, Tailwind CSS |
| **Backend** | FastAPI, Python 3.11+, Uvicorn |
| **LLM** | Ollama (local inference) |
| **SQL Database** | PostgreSQL (via Supabase or local) |
| **Vector Database** | ChromaDB (persistent, local) |
| **Embeddings** | HuggingFace `all-MiniLM-L6-v2` via `sentence-transformers` |
| **Orchestration** | LangChain (document loading, text splitting, ChromaDB integration) |

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **PostgreSQL** database (local or hosted, e.g., Supabase)
- **Ollama** running locally on port 11434 with a model pulled (e.g., `gpt-oss:20b-cloud`)

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd POC
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Ollama / LLM
OLLAMA_BASE_URL=http://localhost:11434/v1/
OLLAMA_MODEL=gpt-oss:20b-cloud
OLLAMA_API_KEY=ollama

# PostgreSQL
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# ChromaDB
CHROMA_DB_PATH=chroma_db_local

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### 3. Install Python Dependencies

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
pip install -r backend/requirements_backend.txt
```

### 4. Initialize the Database

```bash
# Create the audit_logs table
python create_audit.py

# Create employees and timesheets tables
python SQL/create_tables.py
```

### 5. Embed Documents into ChromaDB

```bash
# Embeds performance_reviews/*.docx into chroma_db_local/
python Vector_DB/store_documents.py
```

### 6. Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

## Running the Application

### Start the Backend (Port 8000)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Start the Frontend (Port 3000)

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## API Reference

### `GET /`
Health check endpoint.

**Response:**
```json
{ "status": "ok", "message": "HR RAG API is running." }
```

### `POST /api/chat`
Main chat endpoint.

**Request Body:**
```json
{
  "query": "How many hours did Alex work in January?",
  "history": [
    { "role": "user", "content": "previous question" },
    { "role": "assistant", "content": "previous answer" }
  ]
}
```

**Response:**
```json
{
  "response_text": "Alex worked 160 hours in January...",
  "intent": "SQL",
  "evidence": {
    "sql_query": "SELECT ... FROM techies_timesheets ...",
    "sql_columns": ["Employee Name", "Total Hours"],
    "sql_table": [["Alex Rivera", 160]],
    "vector_context": null,
    "vector_sources": null,
    "latency": 3.45
  }
}
```

---

## Testing Individual Modules

```bash
# Test SQL module interactively
python SQL/sql_retrieval.py

# Test Vector module interactively
python Vector_DB/chat.py
```

---

## Session Memory

The orchestrator maintains **server-side SQL session memory** so follow-up questions can reference prior SQL queries. When a user asks a follow-up (e.g., *"Add department to that table"*), the system rewrites the previous SQL query instead of starting from scratch.

---

## License

This project is for internal use and proof-of-concept purposes.
