import os
import time
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# --- CONFIGURATION ---
# Use absolute path so this works whether run directly or imported from backend/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_POC_ROOT = os.path.dirname(_THIS_DIR)
load_dotenv(os.path.join(_POC_ROOT, ".env"))

OLLAMA_URL     = os.getenv("OLLAMA_BASE_URL",  "http://localhost:11434/v1/")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",     "gpt-oss:20b-cloud")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY",   "ollama")
EMBED_MODEL    = os.getenv("EMBEDDING_MODEL",  "all-MiniLM-L6-v2")

_chroma_env = os.getenv("CHROMA_DB_PATH", "").strip()
DB_PATH = _chroma_env if _chroma_env else os.path.join(_POC_ROOT, "chroma_db_local")


# --- INITIALIZATION (Runs once when imported) ---
print(f"(Vector Module) ChromaDB path resolved to: {DB_PATH}")
print(f"(Vector Module) DB exists: {os.path.exists(DB_PATH)}")
print("(Vector Module) Loading embedding model...")
embedding_function = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

if not os.path.exists(DB_PATH):
    print(f"WARNING: ChromaDB folder not found at '{DB_PATH}'")
    vectorstore = None
else:
    vectorstore = Chroma(
        persist_directory=DB_PATH, 
        embedding_function=embedding_function
    )

print(f"(Vector Module) Connecting to LLM at {OLLAMA_URL}...")
llm = ChatOpenAI(
    base_url=OLLAMA_URL,
    model=OLLAMA_MODEL,
    api_key=OLLAMA_API_KEY,
    temperature=0.0
)

# --- REUSABLE FUNCTION (Called by Orchestrator) ---
def query_vector_db(query):
    """
    Input: User query (string)
    Output: Structured dict: { "context": str, "sources": list[str] }
    """
    if not vectorstore:
        return {"context": "Error: Vector Database not found.", "sources": []}

    print(f"(Vector Tool) Thinking about: '{query}'...")
    
    # 1. Search Vector DB
    results = vectorstore.similarity_search(query, k=5)

    context_parts = []
    unique_sources = []
    
    for i, doc in enumerate(results):
        context_parts.append(doc.page_content)
        # Debug: print all metadata for the first result so we can see what keys exist
        if i == 0:
            print(f"(Vector Tool) Document metadata keys: {list(doc.metadata.keys())}")
            print(f"(Vector Tool) Full metadata: {doc.metadata}")
        source = doc.metadata.get('source', None)
        if source is None:
            # Fallback: try common alternative metadata key names
            source = (
                doc.metadata.get('file_path') or
                doc.metadata.get('filename') or
                doc.metadata.get('file') or
                doc.metadata.get('name') or
                'Unknown'
            )
        if source not in unique_sources:
            unique_sources.append(source)
    
    print(f"(Vector Tool) Sources found: {unique_sources}")
    context_text = "\n---\n".join(context_parts)

    return {
        "context": context_text,   # raw chunks — shown in EvidenceDrawer
        "sources": unique_sources,  # list of source file names
    }

# --- TERMINAL LOOP (Runs ONLY if you run this file directly) ---
if __name__ == "__main__":
    print("Type 'exit' to quit.")
    
    while True:
        user_query = input("\nUser: ")
        if user_query.lower() in ["exit", "quit", "q"]:
            break
        
        start_time = time.time()
        result = query_vector_db(user_query)
        
        print(f"\nSources: {result['sources']}")
        print(f"\nContext:\n{result['context']}")
        print(f"(Time: {round(time.time() - start_time, 2)}s)")
