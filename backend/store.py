"""SQLite store cho Interview Agent.

Bảng:
  messages          : lịch sử hội thoại theo session
  interview_sessions: metadata mỗi phiên phỏng vấn
  session_questions : câu hỏi + câu trả lời + điểm trong mỗi phiên
  weak_areas        : theo dõi điểm yếu + spaced repetition
  chunks            : RAG embeddings (Phase 2)
  memories          : long-term memory facts
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, session_id TEXT, role TEXT, content TEXT
);
CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);

CREATE TABLE IF NOT EXISTS interview_sessions(
  id TEXT PRIMARY KEY,
  created TEXT,
  updated TEXT,
  mode TEXT DEFAULT 'interview',
  level TEXT DEFAULT 'mid',
  language TEXT DEFAULT 'vi',
  phase TEXT DEFAULT 'introduction',
  status TEXT DEFAULT 'active',
  overall_score REAL DEFAULT 0,
  notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS session_questions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  session_id TEXT,
  phase TEXT,
  topic TEXT,
  question TEXT,
  answer TEXT DEFAULT '',
  score REAL DEFAULT 0,
  feedback TEXT DEFAULT '',
  model_answer TEXT DEFAULT '',
  difficulty TEXT DEFAULT 'mid',
  FOREIGN KEY(session_id) REFERENCES interview_sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_sq_session ON session_questions(session_id);
CREATE INDEX IF NOT EXISTS idx_sq_topic ON session_questions(topic);

CREATE TABLE IF NOT EXISTS weak_areas(
  topic TEXT PRIMARY KEY,
  avg_score REAL DEFAULT 0,
  total_attempts INTEGER DEFAULT 0,
  last_practiced TEXT,
  review_due TEXT,
  notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT, topic TEXT, text TEXT, embedding TEXT
);

CREATE TABLE IF NOT EXISTS memories(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, text TEXT, importance REAL DEFAULT 0.5,
  confidence REAL DEFAULT 0.85, uses INTEGER DEFAULT 0,
  last_used TEXT, source TEXT DEFAULT 'fact', expires TEXT DEFAULT '',
  embedding TEXT DEFAULT ''
);
"""


class Store:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._local = threading.local()
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        if not getattr(self._local, "conn", None):
            self._local.conn = sqlite3.connect(self._path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_schema(self):
        c = self._conn()
        c.executescript(SCHEMA)
        c.commit()

    # ── Messages ────────────────────────────────────────────────────
    def save_message(self, session_id: str, role: str, content: str):
        ts = datetime.now().isoformat()
        self._conn().execute(
            "INSERT INTO messages(ts, session_id, role, content) VALUES(?,?,?,?)",
            (ts, session_id, role, content),
        )
        self._conn().commit()

    def get_session_messages(self, session_id: str, limit: int = 40) -> list[dict]:
        rows = self._conn().execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ── Interview Sessions ───────────────────────────────────────────
    def create_session(self, session_id: str, mode: str = "interview",
                       level: str = "mid", language: str = "vi") -> str:
        ts = datetime.now().isoformat()
        self._conn().execute(
            "INSERT OR IGNORE INTO interview_sessions(id,created,updated,mode,level,language) VALUES(?,?,?,?,?,?)",
            (session_id, ts, ts, mode, level, language),
        )
        self._conn().commit()
        return session_id

    def update_session_phase(self, session_id: str, phase: str):
        ts = datetime.now().isoformat()
        self._conn().execute(
            "UPDATE interview_sessions SET phase=?, updated=? WHERE id=?",
            (phase, ts, session_id),
        )
        self._conn().commit()

    def end_session(self, session_id: str, overall_score: float = 0):
        ts = datetime.now().isoformat()
        self._conn().execute(
            "UPDATE interview_sessions SET status='completed', overall_score=?, updated=? WHERE id=?",
            (overall_score, ts, session_id),
        )
        self._conn().commit()

    def get_session(self, session_id: str) -> dict | None:
        row = self._conn().execute(
            "SELECT * FROM interview_sessions WHERE id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 20) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM interview_sessions ORDER BY created DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Questions ────────────────────────────────────────────────────
    def save_question(self, session_id: str, phase: str, topic: str,
                      question: str, difficulty: str = "mid") -> int:
        ts = datetime.now().isoformat()
        cur = self._conn().execute(
            "INSERT INTO session_questions(ts,session_id,phase,topic,question,difficulty) VALUES(?,?,?,?,?,?)",
            (ts, session_id, phase, topic, question, difficulty),
        )
        self._conn().commit()
        return cur.lastrowid

    def save_answer(self, question_id: int, answer: str, score: float,
                    feedback: str, model_answer: str = ""):
        self._conn().execute(
            "UPDATE session_questions SET answer=?,score=?,feedback=?,model_answer=? WHERE id=?",
            (answer, score, feedback, model_answer, question_id),
        )
        self._conn().commit()

    def get_session_questions(self, session_id: str) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM session_questions WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Weak Areas ───────────────────────────────────────────────────
    def update_weak_area(self, topic: str, score: float):
        import datetime as dt
        ts = datetime.now().isoformat()
        # Spaced repetition: diem cang thap -> on lai cang som
        days = 1 if score < 6 else (3 if score < 8 else 7)
        due = (dt.datetime.now() + dt.timedelta(days=days)).isoformat()
        existing = self._conn().execute(
            "SELECT avg_score, total_attempts FROM weak_areas WHERE topic=?", (topic,)
        ).fetchone()
        if existing:
            attempts = existing["total_attempts"] + 1
            avg = (existing["avg_score"] * existing["total_attempts"] + score) / attempts
            self._conn().execute(
                "UPDATE weak_areas SET avg_score=?,total_attempts=?,last_practiced=?,review_due=? WHERE topic=?",
                (avg, attempts, ts, due, topic),
            )
        else:
            self._conn().execute(
                "INSERT INTO weak_areas(topic,avg_score,total_attempts,last_practiced,review_due) VALUES(?,?,1,?,?)",
                (topic, score, ts, due),
            )
        self._conn().commit()

    def get_weak_areas(self, limit: int = 10) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM weak_areas ORDER BY avg_score ASC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_due_reviews(self, limit: int = 20) -> list[dict]:
        """Cac topic den han on tap (spaced repetition): review_due <= now."""
        now = datetime.now().isoformat()
        rows = self._conn().execute(
            "SELECT * FROM weak_areas "
            "WHERE review_due IS NOT NULL AND review_due != '' AND review_due <= ? "
            "ORDER BY review_due ASC LIMIT ?",
            (now, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Chunks (RAG) ─────────────────────────────────────────────────
    def chunk_count(self) -> int:
        row = self._conn().execute("SELECT COUNT(*) as n FROM chunks").fetchone()
        return row["n"] if row else 0

    def source_exists(self, source: str) -> bool:
        row = self._conn().execute(
            "SELECT 1 FROM chunks WHERE source=? LIMIT 1", (source,)
        ).fetchone()
        return row is not None

    def save_chunk(self, source: str, topic: str, text: str, embedding: list | None = None):
        emb_str = json.dumps(embedding) if embedding else ""
        self._conn().execute(
            "INSERT INTO chunks(source,topic,text,embedding) VALUES(?,?,?,?)",
            (source, topic, text, emb_str),
        )
        self._conn().commit()

    # ── Memories ─────────────────────────────────────────────────────
    def save_memory(self, text: str, importance: float = 0.5, source: str = "fact"):
        ts = datetime.now().isoformat()
        self._conn().execute(
            "INSERT INTO memories(ts,text,importance,source) VALUES(?,?,?,?)",
            (ts, text, importance, source),
        )
        self._conn().commit()

    def get_memories(self, limit: int = 20) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM memories ORDER BY importance DESC, ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
