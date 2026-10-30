"""Knowledge base ingestion pipeline — Phase 2.

Dùng: python -m backend.ingest [--source <path>] [--cv <pdf_path>]

Hỗ trợ: PDF (pdfplumber), Markdown (.md), Text (.txt)
Chunk → Embed (bge-m3) → lưu vào RAG store
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

# Thêm project root vào path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from .config import CONFIG
from .rag import RagStore
from .store import Store

CHUNK_SIZE    = CONFIG.get("rag", {}).get("chunk_size", 500)
CHUNK_OVERLAP = CONFIG.get("rag", {}).get("chunk_overlap", 50)

# Ánh xạ thư mục/từ khoá → topic tag
TOPIC_HINTS = {
    "java": "java-core",
    "spring": "spring-boot",
    "microservice": "microservices",
    "docker": "devops",
    "kubernetes": "devops",
    "k8s": "devops",
    "ci": "devops",
    "system-design": "system-design",
    "design": "system-design",
    "behavioral": "behavioral",
    "soft": "behavioral",
    "algorithm": "algorithms",
    "data-structure": "algorithms",
    "sql": "database",
    "database": "database",
    "cv": "cv",
    "resume": "cv",
}


def _detect_topic(path: Path) -> str:
    name = str(path).lower()
    for kw, topic in TOPIC_HINTS.items():
        if kw in name:
            return topic
    return "general"


def _chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        # Cắt tại ranh giới câu
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", " "]:
                idx = text.rfind(sep, start + size // 2, end)
                if idx != -1:
                    end = idx + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if len(c) > 30]


def _read_pdf(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n\n".join(
                p.extract_text() or "" for p in pdf.pages
            )
    except Exception:
        pass
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        return "\n\n".join(page.get_text() for page in doc)
    except Exception as e:
        print(f"  [!] Cannot read PDF {path}: {e}", flush=True)
        return ""


def _read_file(path: Path) -> str:
    suf = path.suffix.lower()
    if suf == ".pdf":
        return _read_pdf(path)
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


async def ingest_file(path: Path, rag: RagStore, force: bool = False) -> int:
    text = _read_file(path)
    if not text or len(text) < 50:
        return 0
    topic = _detect_topic(path)
    try:
        source = str(path.relative_to(ROOT))
    except ValueError:
        source = str(path)

    # Skip neu source nay da ingest roi (tranh trung lap)
    if not force and rag.source_exists(source):
        return 0

    chunks = _chunk(text)
    count = 0
    for chunk in chunks:
        await rag.add_chunk(source=source, topic=topic, text=chunk)
        count += 1
    return count


async def ingest_directory(dir_path: Path, rag: RagStore, extensions: tuple = (".pdf", ".md", ".txt")) -> int:
    total = 0
    files = [f for f in dir_path.rglob("*")
             if f.suffix.lower() in extensions and f.is_file()
             and not f.name.startswith("_")]  # bo qua file huong dan _*.md
    print(f"  Found {len(files)} files in {dir_path}", flush=True)
    for f in files:
        n = await ingest_file(f, rag)
        if n:
            print(f"  [OK] {f.name} -> {n} chunks [{_detect_topic(f)}]", flush=True)
        total += n
    return total


async def run_ingest(source: str | None = None, cv: str | None = None, force: bool = False):
    store = Store(CONFIG["storage"]["db_path"])
    rag = RagStore(store)

    # Reset chunks neu force (tranh trung lap khi ingest lai)
    if force:
        try:
            store._conn().execute("DELETE FROM chunks")
            store._conn().commit()
            print("[RESET] Cleared existing chunks (force mode)", flush=True)
        except Exception as e:
            print(f"[RESET] Cannot clear chunks: {e}", flush=True)

    print("=" * 40, flush=True)
    print("  Knowledge Base Ingest Pipeline", flush=True)
    print("=" * 40, flush=True)

    total = 0

    # Ingest knowledge directory
    src = Path(source) if source else ROOT / "data" / "knowledge"
    if src.exists():
        print(f"[1/3] Ingest knowledge base from {src}...", flush=True)
        total += await ingest_directory(src, rag)
    else:
        print(f"[1/3] Skip (no directory {src})", flush=True)

    # Ingest CV
    cv_dir = Path(cv) if cv else ROOT / "data" / "cv"
    if cv_dir.exists():
        print(f"[2/3] Ingest CV from {cv_dir}...", flush=True)
        cv_files = list(cv_dir.rglob("*.pdf")) + list(cv_dir.rglob("*.md"))
        for f in cv_files:
            n = await ingest_file(f, rag)
            if n:
                print(f"  [OK] CV: {f.name} -> {n} chunks", flush=True)
            total += n
    else:
        print(f"[2/3] No CV in {cv_dir} (put file into data/cv/)", flush=True)

    # Ingest custom questions
    q_dir = ROOT / "data" / "questions"
    if q_dir.exists():
        print(f"[3/3] Ingest custom questions from {q_dir}...", flush=True)
        total += await ingest_directory(q_dir, rag, extensions=(".md", ".yaml", ".yml", ".txt"))

    print("=" * 40, flush=True)
    print(f"[DONE] {total} chunks ingested into knowledge base.", flush=True)
    print(f"       RAG store now has {rag.chunk_count()} chunks.", flush=True)
    print("=" * 40, flush=True)
    return total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Nạp knowledge base cho Interview Agent")
    parser.add_argument("--source", help="Thư mục chứa tài liệu kỹ thuật")
    parser.add_argument("--cv", help="Thư mục/file CV PDF")
    parser.add_argument("--force", action="store_true", help="Nạp lại kể cả đã có")
    args = parser.parse_args()
    asyncio.run(run_ingest(source=args.source, cv=args.cv, force=args.force))
