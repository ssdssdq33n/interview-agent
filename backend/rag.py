"""RAG store — pgvector nếu có, fallback keyword SQLite.

Dùng bge-m3 (768 dim) từ Ollama để embed. Nếu Ollama chưa sẵn sàng
thì skip embed và dùng BM25-style keyword search.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from .config import CONFIG
from .store import Store


class RagStore:
    _pg_unavailable = False  # class-level: da xac dinh pgvector khong kha dung -> skip

    def __init__(self, store: Store):
        self.store = store
        self._pg_conn = None
        self._pg_ready = False
        self._embed_model = CONFIG["ollama"].get("embed_model", "bge-m3")
        self._top_k = CONFIG.get("rag", {}).get("top_k", 5)
        if CONFIG.get("postgres", {}).get("enabled") and not RagStore._pg_unavailable:
            self._init_pg()

    def _init_pg(self):
        try:
            import psycopg2
            dsn = CONFIG["postgres"]["dsn"]
            self._pg_conn = psycopg2.connect(dsn, connect_timeout=3)
            cur = self._pg_conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            dim = CONFIG["postgres"].get("dim", 768)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS doc_chunks (
                    id SERIAL PRIMARY KEY,
                    source TEXT,
                    topic TEXT,
                    text TEXT,
                    embedding vector({dim})
                );
                CREATE INDEX IF NOT EXISTS doc_chunks_emb_idx
                ON doc_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
            """)
            self._pg_conn.commit()
            self._pg_ready = True
        except Exception as e:
            print(f"[RAG] pgvector not available, using SQLite: {e}", flush=True)
            self._pg_conn = None
            RagStore._pg_unavailable = True  # cac RagStore sau khoi thu connect lai

    _embed_down_until = 0.0  # class-level: skip embed cho den thoi diem nay (monotonic)

    async def embed(self, text: str) -> Optional[list[float]]:
        import time
        if time.monotonic() < RagStore._embed_down_until:
            return None  # dang trong cooldown vi Ollama down -> keyword fallback
        try:
            import ollama
            client = ollama.AsyncClient(host=CONFIG["ollama"]["host"])
            resp = await client.embeddings(model=self._embed_model, prompt=text[:2000])
            RagStore._embed_down_until = 0.0  # thanh cong -> reset
            return resp.get("embedding") or resp.get("embeddings", [[]])[0]
        except Exception:
            # Ollama down -> skip embed trong 60s toi (tranh retry cham moi chunk)
            RagStore._embed_down_until = time.monotonic() + 60
            print("[RAG] Ollama embed unavailable, keyword search for 60s", flush=True)
            return None

    async def add_chunk(self, source: str, topic: str, text: str):
        emb = await self.embed(text)
        if self._pg_ready and emb:
            try:
                cur = self._pg_conn.cursor()
                cur.execute(
                    "INSERT INTO doc_chunks(source,topic,text,embedding) VALUES(%s,%s,%s,%s)",
                    (source, topic, text, json.dumps(emb)),
                )
                self._pg_conn.commit()
                return
            except Exception:
                pass
        # Fallback: SQLite
        self.store.save_chunk(source, topic, text, emb)

    async def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        k = top_k or self._top_k
        emb = await self.embed(query)

        if self._pg_ready and emb:
            try:
                cur = self._pg_conn.cursor()
                cur.execute(
                    """SELECT source, topic, text,
                       1 - (embedding <=> %s::vector) AS score
                       FROM doc_chunks
                       ORDER BY embedding <=> %s::vector
                       LIMIT %s""",
                    (json.dumps(emb), json.dumps(emb), k),
                )
                rows = cur.fetchall()
                return [{"source": r[0], "topic": r[1], "text": r[2], "score": r[3]}
                        for r in rows]
            except Exception:
                pass

        return self._keyword_search(query, k)

    def _keyword_search(self, query: str, k: int) -> list[dict]:
        words = re.findall(r"\w+", query.lower())
        if not words:
            return []
        conn = self.store._conn()
        rows = conn.execute("SELECT source, topic, text FROM chunks LIMIT 500").fetchall()
        scored = []
        for r in rows:
            t = (r["text"] or "").lower()
            score = sum(t.count(w) for w in words)
            if score:
                scored.append({"source": r["source"], "topic": r["topic"],
                               "text": r["text"], "score": score})
        scored.sort(key=lambda x: -x["score"])
        return scored[:k]

    def chunk_count(self) -> int:
        if self._pg_ready:
            try:
                cur = self._pg_conn.cursor()
                cur.execute("SELECT COUNT(*) FROM doc_chunks")
                return cur.fetchone()[0]
            except Exception:
                pass
        return self.store.chunk_count()

    def source_exists(self, source: str) -> bool:
        if self._pg_ready:
            try:
                cur = self._pg_conn.cursor()
                cur.execute("SELECT 1 FROM doc_chunks WHERE source=%s LIMIT 1", (source,))
                return cur.fetchone() is not None
            except Exception:
                pass
        return self.store.source_exists(source)
