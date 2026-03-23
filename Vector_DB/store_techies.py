"""
Ingest Techies HR Excel files into a new ChromaDB vector store.

Files:
  - Techies/Employee Feedbacks Report.xlsx
  - Techies/Employees Praises Report.xlsx

Output: chroma_db_techies/ (at POC root)
"""

import os
import pandas as pd
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_POC_ROOT = os.path.dirname(_THIS_DIR)
load_dotenv(os.path.join(_POC_ROOT, ".env"))

FEEDBACKS_FILE = os.path.join(_POC_ROOT, "Techies", "Employee Feedbacks Report.xlsx")
PRAISES_FILE   = os.path.join(_POC_ROOT, "Techies", "Employees Praises Report.xlsx")
DB_PATH        = os.path.join(_POC_ROOT, "chroma_db_techies")
EMBED_MODEL    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


def _read_sheet(path, sheet_index=0):
    """Read an Excel file whose real header is on row index 1 (row 2 in Excel)."""
    df = pd.read_excel(path, sheet_name=sheet_index, header=1)
    # Drop completely empty rows
    df.dropna(how="all", inplace=True)
    # Skip the title row that Excel merged across columns (it contains the report name)
    df = df[df.iloc[:, 0].notna()]
    return df


def _clean(val):
    """Return a clean string, or empty string for NaN/None."""
    if pd.isna(val) or val is None:
        return ""
    return str(val).strip()


# ── 1. Load Feedbacks ─────────────────────────────────────────────────────────
print("--- Loading Employee Feedbacks Report ---")
fb_df = _read_sheet(FEEDBACKS_FILE)
fb_df.columns = [
    "employee_number", "employee_name", "job_title",
    "department", "sub_department", "location",
    "feedback", "projects", "core_values", "given_by", "date"
]

feedback_docs = []
for _, row in fb_df.iterrows():
    emp_num  = _clean(row["employee_number"])
    name     = _clean(row["employee_name"])
    title    = _clean(row["job_title"])
    dept     = _clean(row["department"])
    feedback = _clean(row["feedback"])
    projects = _clean(row["projects"])
    values   = _clean(row["core_values"])
    given_by = _clean(row["given_by"])
    date     = _clean(row["date"])
    location = _clean(row["location"])

    if not feedback:
        continue

    content = (
        f"Employee: {name} ({emp_num})\n"
        f"Job Title: {title}\n"
        f"Department: {dept}\n"
        f"Location: {location}\n"
        f"Feedback: {feedback}\n"
        f"Projects: {projects}\n"
        f"Core Values: {values}\n"
        f"Given By: {given_by}\n"
        f"Date: {date}"
    )

    feedback_docs.append(Document(
        page_content=content,
        metadata={
            "source": "Employee Feedbacks Report.xlsx",
            "type": "feedback",
            "employee_number": emp_num,
            "employee_name": name,
            "job_title": title,
            "department": dept,
            "given_by": given_by,
            "date": date,
        }
    ))

print(f"  Loaded {len(feedback_docs)} feedback records.")


# ── 2. Load Praises ───────────────────────────────────────────────────────────
print("--- Loading Employees Praises Report ---")
pr_df = _read_sheet(PRAISES_FILE)
pr_df.columns = [
    "employee_number", "employee_name", "job_title",
    "department", "sub_department", "location",
    "badge", "praise", "projects", "given_by", "date"
]

praise_docs = []
for _, row in pr_df.iterrows():
    emp_num  = _clean(row["employee_number"])
    name     = _clean(row["employee_name"])
    title    = _clean(row["job_title"])
    dept     = _clean(row["department"])
    badge    = _clean(row["badge"])
    praise   = _clean(row["praise"])
    projects = _clean(row["projects"])
    given_by = _clean(row["given_by"])
    date     = _clean(row["date"])
    location = _clean(row["location"])

    if not praise:
        continue

    content = (
        f"Employee: {name} ({emp_num})\n"
        f"Job Title: {title}\n"
        f"Department: {dept}\n"
        f"Location: {location}\n"
        f"Badge: {badge}\n"
        f"Praise: {praise}\n"
        f"Projects: {projects}\n"
        f"Given By: {given_by}\n"
        f"Date: {date}"
    )

    praise_docs.append(Document(
        page_content=content,
        metadata={
            "source": "Employees Praises Report.xlsx",
            "type": "praise",
            "employee_number": emp_num,
            "employee_name": name,
            "job_title": title,
            "department": dept,
            "badge": badge,
            "given_by": given_by,
            "date": date,
        }
    ))

print(f"  Loaded {len(praise_docs)} praise records.")


# ── 3. Chunk ──────────────────────────────────────────────────────────────────
all_docs = feedback_docs + praise_docs
print(f"\n--- Chunking {len(all_docs)} documents ---")

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=80)
splits = splitter.split_documents(all_docs)
print(f"  Split into {len(splits)} chunks.")


# ── 4. Embed & Store ──────────────────────────────────────────────────────────
print(f"\n--- Embedding with '{EMBED_MODEL}' ---")
embedding_fn = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

print(f"--- Creating ChromaDB at '{DB_PATH}' ---")
vectorstore = Chroma.from_documents(
    documents=splits,
    embedding=embedding_fn,
    persist_directory=DB_PATH,
)

print(f"\nSUCCESS! New vector DB created at: {DB_PATH}")
print(f"  Total chunks stored: {vectorstore._collection.count()}")
