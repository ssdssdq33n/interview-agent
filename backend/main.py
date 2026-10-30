"""FastAPI server — Interview Agent.

REST:
  GET  /api/health
  POST /api/session/new
  GET  /api/sessions
  GET  /api/session/{id}
  GET  /api/weak-areas
  POST /api/tts            → edge-tts audio stream
  POST /api/stt            → whisper transcription
  POST /api/code/run       → Docker/subprocess code execution
  GET  /api/stats          → dashboard stats
  POST /api/ingest         → trigger knowledge ingest

WS:
  /ws/{session_id}
"""
from __future__ import annotations

import asyncio
import io
import json
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .brain import Brain
from .config import CONFIG, FRONTEND_DIR
from .store import Store

app = FastAPI(title="Interview Agent", docs_url="/docs")

# Static files
_assets = FRONTEND_DIR / "assets"
if _assets.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets), html=False), name="assets")

_BRAINS: dict[str, Brain] = {}

# Singleton Store + RagStore dung chung (tranh tao lai + connect pgvector moi lan)
_STORE: Store | None = None
_RAG = None


def _store() -> Store:
    global _STORE
    if _STORE is None:
        _STORE = Store(CONFIG["storage"]["db_path"])
    return _STORE


def _rag():
    global _RAG
    if _RAG is None:
        from .rag import RagStore
        _RAG = RagStore(_store())
    return _RAG


def _get_brain(session_id: str, mode: str = "interviewer", language: str = "vi") -> Brain:
    if session_id not in _BRAINS:
        _BRAINS[session_id] = Brain(session_id, mode=mode, language=language)
    return _BRAINS[session_id]


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    from .providers import OllamaProvider, ClaudeProvider
    ollama_ok, ollama_msg = False, "unknown"
    try:
        prov = OllamaProvider()
        ollama_ok, ollama_msg = await prov.health_check()
    except Exception as e:
        ollama_msg = str(e)

    claude_ok, claude_msg = False, "unknown"
    try:
        cprov = ClaudeProvider()
        claude_ok, claude_msg = await cprov.health_check()
    except Exception as e:
        claude_msg = str(e)

    store = _store()

    rag_chunks = 0
    try:
        rag_chunks = _rag().chunk_count()
    except Exception:
        pass

    return {
        "status": "ok",
        "provider": CONFIG["agent"]["provider"],
        "model": CONFIG["ollama"]["brain_model"],
        "ollama": {"ok": ollama_ok, "message": ollama_msg},
        "claude": {"ok": claude_ok, "message": claude_msg},
        "sessions_count": len(store.list_sessions()),
        "rag_chunks": rag_chunks,
    }


# ── Sessions ──────────────────────────────────────────────────────────────────

@app.post("/api/session/new")
async def new_session(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    session_id = str(uuid.uuid4())
    mode     = body.get("mode", "interviewer")
    level    = body.get("level", CONFIG["interview"].get("default_level", "mid"))
    language = body.get("language", CONFIG["agent"].get("language", "vi"))

    brain = _get_brain(session_id, mode=mode, language=language)
    brain.store.create_session(session_id, mode=mode, level=level, language=language)

    return {"session_id": session_id, "mode": mode, "level": level, "language": language}


@app.get("/api/sessions")
async def list_sessions():
    store = _store()
    return {"sessions": store.list_sessions()}


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    store = _store()
    session = store.get_session(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return {
        "session": session,
        "questions": store.get_session_questions(session_id),
        "weak_areas": store.get_weak_areas(),
    }


@app.get("/api/session/{session_id}/report")
async def session_report(session_id: str):
    store = _store()
    session = store.get_session(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    questions = store.get_session_questions(session_id)
    return _build_report(session, questions)


def _build_report(session: dict, questions: list[dict]) -> dict:
    import datetime as dt
    lang = session.get("language", "vi")
    scored = [q for q in questions if q.get("score")]
    topic_map: dict[str, list[float]] = {}
    for q in scored:
        topic_map.setdefault(q.get("topic", "general"), []).append(float(q.get("score", 0)))

    topics = [
        {"topic": tp, "avg_score": round(sum(v) / len(v), 2), "count": len(v)}
        for tp, v in sorted(topic_map.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
    ]
    avg = round(sum(q["score"] for q in scored) / len(scored), 2) if scored else 0.0
    overall = round(float(session.get("overall_score") or avg), 2)
    strengths = [t for t in topics if t["avg_score"] >= 8]
    weaknesses = [t for t in topics if t["avg_score"] < 6]

    # Duration
    duration_min = 0
    try:
        c = dt.datetime.fromisoformat(session["created"])
        u = dt.datetime.fromisoformat(session["updated"])
        duration_min = max(0, round((u - c).total_seconds() / 60, 1))
    except Exception:
        pass

    # Recommendation text (bilingual, deterministic)
    if lang == "vi":
        if not scored:
            rec = "Chưa có câu hỏi nào được chấm điểm trong phiên này."
        elif weaknesses:
            rec = "Nên ôn lại: " + ", ".join(t["topic"] for t in weaknesses[:3]) + \
                  ". Tập trung giải thích sâu cơ chế và đánh đổi (trade-off)."
        elif overall >= 8:
            rec = "Rất tốt! Nền tảng vững. Thử nâng độ khó lên senior/system design."
        else:
            rec = "Khá ổn. Luyện thêm để câu trả lời sâu và có ví dụ cụ thể hơn."
    else:
        if not scored:
            rec = "No scored questions in this session yet."
        elif weaknesses:
            rec = "Review: " + ", ".join(t["topic"] for t in weaknesses[:3]) + \
                  ". Focus on explaining mechanisms and trade-offs in depth."
        elif overall >= 8:
            rec = "Excellent! Solid foundation. Try harder senior / system-design questions."
        else:
            rec = "Good. Practice deeper answers with concrete examples."

    return {
        "session_id": session["id"],
        "mode": session.get("mode"),
        "level": session.get("level"),
        "language": lang,
        "phase": session.get("phase"),
        "status": session.get("status"),
        "overall_score": overall,
        "total_questions": len(questions),
        "scored_questions": len(scored),
        "duration_min": duration_min,
        "topics": topics,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendation": rec,
        "questions": [
            {"topic": q.get("topic"), "question": q.get("question"),
             "score": q.get("score"), "feedback": q.get("feedback")}
            for q in scored
        ],
    }


@app.get("/api/weak-areas")
async def get_weak_areas():
    store = _store()
    return {"weak_areas": store.get_weak_areas()}


@app.get("/api/stats")
async def get_stats():
    store = _store()
    sessions = store.list_sessions(limit=100)
    weak_areas = store.get_weak_areas(limit=20)
    due_reviews = store.get_due_reviews(limit=20)
    questions = []
    for s in sessions[:10]:
        questions.extend(store.get_session_questions(s["id"]))
    total_q = len(questions)
    scored = [q for q in questions if q.get("score")]
    avg_score = (sum(q.get("score", 0) for q in scored) / len(scored)) if scored else 0
    # Score trend: avg score per completed session (oldest -> newest, last 10)
    trend = []
    for s in reversed(sessions):
        qs = [q for q in store.get_session_questions(s["id"]) if q.get("score")]
        if qs:
            trend.append({
                "session": s["id"][:8],
                "avg_score": round(sum(q["score"] for q in qs) / len(qs), 2),
                "date": s.get("created", "")[:10],
            })
    trend = trend[-10:]

    return {
        "total_sessions": len(sessions),
        "total_questions": total_q,
        "avg_score": round(avg_score, 2),
        "weak_areas": weak_areas,
        "due_reviews": due_reviews,
        "recent_sessions": sessions[:5],
        "topic_stats": _compute_topic_stats(questions),
        "score_trend": trend,
    }


@app.get("/api/weak-areas/due")
async def get_due_reviews():
    store = _store()
    return {"due_reviews": store.get_due_reviews()}


def _compute_topic_stats(questions: list[dict]) -> list[dict]:
    topics: dict[str, list[float]] = {}
    for q in questions:
        t = q.get("topic", "general")
        s = float(q.get("score", 0) or 0)
        topics.setdefault(t, []).append(s)
    return [
        {"topic": t, "avg_score": round(sum(v)/len(v), 2), "attempts": len(v)}
        for t, v in sorted(topics.items())
    ]


# ── TTS ───────────────────────────────────────────────────────────────────────

@app.post("/api/tts")
async def text_to_speech(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    text = body.get("text", "").strip()
    language = body.get("language", CONFIG["agent"].get("language", "vi"))
    if not text:
        return JSONResponse({"error": "No text"}, status_code=400)

    tts_cfg = CONFIG.get("tts", {})
    engine = tts_cfg.get("engine", "edge")

    if engine == "edge":
        voice = tts_cfg.get("vi_voice", "vi-VN-NamMinhNeural") if language == "vi" \
            else tts_cfg.get("en_voice", "en-US-GuyNeural")
        rate = tts_cfg.get("rate", "+0%")
        pitch = tts_cfg.get("pitch", "+0Hz")

        try:
            import edge_tts
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            audio_buffer.seek(0)
            return StreamingResponse(audio_buffer, media_type="audio/mpeg",
                                     headers={"Content-Disposition": "inline"})
        except Exception as e:
            return JSONResponse({"error": f"edge-tts lỗi: {e}"}, status_code=500)

    return JSONResponse({"error": "TTS engine không hỗ trợ"}, status_code=400)


# ── STT ───────────────────────────────────────────────────────────────────────

@app.post("/api/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    stt_cfg = CONFIG.get("stt", {})
    engine = stt_cfg.get("engine", "browser")
    language = CONFIG["agent"].get("language", "vi")

    if engine != "whisper":
        return JSONResponse({"error": "STT engine is browser, dùng Web Speech API"}, status_code=400)

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return JSONResponse({"error": "faster-whisper chưa được cài. pip install faster-whisper"}, status_code=500)

    content = await audio.read()
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(content)
        tmp_path = f.name

    try:
        model_name = stt_cfg.get("whisper_model", "large-v3-turbo")
        device = stt_cfg.get("whisper_device", "auto")
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        model = WhisperModel(model_name, device=device, compute_type="int8")
        segments, info = model.transcribe(
            tmp_path,
            language=language if language != "mixed" else None,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(s.text.strip() for s in segments)
        return {"text": text, "language": info.language, "probability": info.language_probability}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ── Code execution ─────────────────────────────────────────────────────────────

@app.post("/api/code/run")
async def run_code(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    language = body.get("language", "java")
    code = body.get("code", "").strip()
    if not code:
        return JSONResponse({"error": "No code provided"}, status_code=400)

    from .code_runner import run_code as _run
    result = await _run(language, code)
    return result


# ── File upload (CV / knowledge docs) ───────────────────────────────────────────

_ALLOWED_UPLOAD = {".pdf", ".md", ".txt"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), kind: str = "cv"):
    """Upload CV hoac tai lieu kien thuc, luu vao data/cv hoac data/knowledge."""
    from .config import DATA_DIR

    name = Path(file.filename or "upload").name
    ext = Path(name).suffix.lower()
    if ext not in _ALLOWED_UPLOAD:
        return JSONResponse(
            {"error": f"Chi ho tro {', '.join(sorted(_ALLOWED_UPLOAD))}"},
            status_code=400,
        )

    if kind == "cv":
        target_dir = DATA_DIR / "cv"
    else:
        target_dir = DATA_DIR / "knowledge" / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / name

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        return JSONResponse({"error": "File qua lon (toi da 20MB)"}, status_code=400)
    dest.write_bytes(content)

    # Ingest ngay file vua upload
    ingested = 0
    try:
        from .ingest import ingest_file
        ingested = await ingest_file(dest, _rag(), force=True)
    except Exception as e:
        return JSONResponse(
            {"status": "saved", "filename": name, "chunks": 0, "warning": str(e)},
            status_code=200,
        )

    return {"status": "ok", "filename": name, "kind": kind, "chunks": ingested}


# ── Knowledge ingest ──────────────────────────────────────────────────────────

@app.post("/api/ingest")
async def trigger_ingest(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    source = body.get("source")
    cv = body.get("cv")
    wait = body.get("wait", False)
    force = body.get("force", False)

    from .ingest import run_ingest

    if wait:
        # Chay dong bo va tra ket qua (dung cho self-test)
        total = await run_ingest(source=source, cv=cv, force=force)
        return {"status": "done", "ingested": total, "total_chunks": _rag().chunk_count()}

    asyncio.create_task(run_ingest(source=source, cv=cv, force=force))
    return {"status": "started", "message": "Ingest dang chay o background"}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()

    try:
        init_data = await asyncio.wait_for(ws.receive_json(), timeout=5)
    except Exception:
        init_data = {}

    mode     = init_data.get("mode", "interviewer")
    language = init_data.get("language", CONFIG["agent"].get("language", "vi"))
    brain    = _get_brain(session_id, mode=mode, language=language)

    await ws.send_json({
        "type": "connected",
        "session_id": session_id,
        "mode": mode,
        "language": language,
        "provider": CONFIG["agent"]["provider"],
        "model": CONFIG["ollama"]["brain_model"],
    })

    async def emit(event: dict):
        try:
            await ws.send_json(event)
        except Exception:
            pass

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                text = data.get("text", "").strip()
                if not text:
                    continue
                await brain.chat(text, emit)

            elif msg_type == "switch_mode":
                new_mode = data.get("mode", "interviewer")
                await brain.switch_mode(new_mode)
                await ws.send_json({"type": "mode_changed", "mode": new_mode})

            elif msg_type == "switch_provider":
                new_provider = data.get("provider", "ollama")
                CONFIG["agent"]["provider"] = new_provider
                _BRAINS.pop(session_id, None)
                brain = _get_brain(session_id, mode=mode, language=language)
                await ws.send_json({"type": "provider_changed", "provider": new_provider})

            elif msg_type == "switch_language":
                new_lang = data.get("language", "vi")
                language = new_lang
                await brain.set_language(new_lang)
                await ws.send_json({"type": "language_changed", "language": new_lang})

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

            elif msg_type == "health":
                result = await brain.health()
                await ws.send_json({"type": "health", **result})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    html = FRONTEND_DIR / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return JSONResponse({"error": "Frontend not found."}, status_code=503)


@app.get("/{path:path}")
async def catch_all(path: str):
    for candidate in [FRONTEND_DIR / path, FRONTEND_DIR / f"{path}.html"]:
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
    html = FRONTEND_DIR / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return JSONResponse({"error": "Not found"}, status_code=404)
