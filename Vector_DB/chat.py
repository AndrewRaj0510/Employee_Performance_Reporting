import os
import time
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# --- CONFIGURATION ---
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_POC_ROOT = os.path.dirname(_THIS_DIR)
load_dotenv(os.path.join(_POC_ROOT, ".env"))

EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

_chroma_env = os.getenv("CHROMA_DB_PATH", "").strip()
if not _chroma_env:
    DB_PATH = os.path.join(_POC_ROOT, "chroma_db_local")
elif os.path.isabs(_chroma_env):
    DB_PATH = _chroma_env
else:
    DB_PATH = os.path.join(_POC_ROOT, _chroma_env)


# --- INITIALIZATION (Runs once when imported) ---
print(f"(Vector Module) ChromaDB path resolved to: {DB_PATH}")
print(f"(Vector Module) DB exists: {os.path.exists(DB_PATH)}")
print("(Vector Module) Loading embedding model...")
embedding_function = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"batch_size": 32, "normalize_embeddings": True},
)

if not os.path.exists(DB_PATH):
    print(f"WARNING: ChromaDB folder not found at '{DB_PATH}'")
    vectorstore = None
else:
    vectorstore = Chroma(
        persist_directory=DB_PATH,
        embedding_function=embedding_function
    )

# --- QUERY EMBEDDING CACHE ---
# Avoids re-encoding the same query string on repeated or similar calls.
_embed_cache: dict[str, list[float]] = {}

def _get_embedding(text: str) -> list[float]:
    if text not in _embed_cache:
        _embed_cache[text] = embedding_function.embed_query(text)
    return _embed_cache[text]


# --- REUSABLE FUNCTION (Called by Orchestrator) ---
def query_vector_db(query: str) -> dict:
    """
    Input: User query (string)
    Output: Structured dict: { "context": str, "sources": list[str] }
    """
    if not vectorstore:
        return {"context": "Error: Vector Database not found.", "sources": []}

    print(f"(Vector Tool) Thinking about: '{query}'...")

    # Embed once, reuse cache on repeat queries; use by-vector search to skip
    # ChromaDB's internal re-encoding step.
    query_vector = _get_embedding(query)
    results = vectorstore.similarity_search_by_vector(query_vector, k=3)

    context_parts = []
    unique_sources = []

    for i, doc in enumerate(results):
        context_parts.append(doc.page_content)
        if i == 0:
            print(f"(Vector Tool) Metadata: {doc.metadata}")
        source = (
            doc.metadata.get("source") or
            doc.metadata.get("file_path") or
            doc.metadata.get("filename") or
            "Unknown"
        )
        if source not in unique_sources:
            unique_sources.append(source)

    print(f"(Vector Tool) Sources found: {unique_sources}")
    context_text = "\n---\n".join(context_parts)

    return {
        "context": context_text,
        "sources": unique_sources,
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
