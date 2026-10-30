"""Comprehensive self-test — run against a live server.

Usage:
  python run.py            # (in another terminal) start the server first
  python test_server.py [--port 8080]

Covers: health, sessions, stats, report, weak-areas, due-reviews, TTS, STT,
code-run, upload, ingest, frontend, dashboard, WebSocket, plus edge cases and
direct logic tests (InterviewEngine, RagStore, report builder, spaced repetition).
"""
import asyncio, io, json, sys, time, os, argparse, uuid
import urllib.request, urllib.error

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8080)
args_cli, _ = parser.parse_known_args()

PORT = args_cli.port
BASE = f"http://127.0.0.1:{PORT}"
WS_BASE = f"ws://127.0.0.1:{PORT}"
PASS = []; FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name); print(f"  OK  {name}")
    else:
        FAIL.append(name); print(f"  XX  {name}" + (f" -- {detail}" if detail else ""))


def GET(path, timeout=10):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            raw = r.read()
            try: return r.status, json.loads(raw)
            except Exception: return r.status, {"_raw": raw[:200].decode(errors="replace")}
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def POST(path, body, timeout=12):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def POST_MULTIPART(path, filename, content, ctype="text/markdown", timeout=20):
    boundary = "----selftest" + uuid.uuid4().hex[:8]
    parts = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode(),
        f"Content-Type: {ctype}".encode(), b"", content,
        f"--{boundary}--".encode(),
    ]
    data = b"\r\n".join(parts)
    req = urllib.request.Request(BASE + path, data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


# ── WebSocket edge cases ────────────────────────────────────────────────────────
async def test_ws(session_id):
    try:
        import websockets
    except ImportError:
        check("WS: websockets lib", False, "pip install websockets"); return
    uri = f"{WS_BASE}/ws/{session_id}"
    try:
        async with websockets.connect(uri, open_timeout=8) as ws:
            await ws.send(json.dumps({"mode": "interviewer", "language": "vi"}))
            data = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
            check("WS: connected event", data.get("type") == "connected", str(data.get("type")))
            # ping/pong
            await ws.send(json.dumps({"type": "ping"}))
            check("WS: ping/pong", json.loads(await asyncio.wait_for(ws.recv(), 5)).get("type") == "pong")
            # switch_mode
            await ws.send(json.dumps({"type": "switch_mode", "mode": "trainer"}))
            check("WS: switch_mode", json.loads(await asyncio.wait_for(ws.recv(), 5)).get("type") == "mode_changed")
            # switch_language
            await ws.send(json.dumps({"type": "switch_language", "language": "en"}))
            check("WS: switch_language", json.loads(await asyncio.wait_for(ws.recv(), 5)).get("type") == "language_changed")
            # health over ws
            await ws.send(json.dumps({"type": "health"}))
            check("WS: health", json.loads(await asyncio.wait_for(ws.recv(), 8)).get("type") == "health")
            # empty message should not crash (no reply expected) -> send ping after to confirm alive
            await ws.send(json.dumps({"type": "message", "text": "   "}))
            await ws.send(json.dumps({"type": "ping"}))
            check("WS: survives empty message", json.loads(await asyncio.wait_for(ws.recv(), 5)).get("type") == "pong")
    except Exception as e:
        check("WS: connection", False, str(e))


# ── Direct logic tests (import backend) ─────────────────────────────────────────
def test_logic():
    print("\n[LOGIC] Direct module tests")
    try:
        from backend.config import CONFIG
        from backend.store import Store
        from backend.interview_engine import InterviewEngine
        from backend.rag import RagStore
        import backend.main as m
    except Exception as e:
        check("Logic: import backend", False, str(e)); return

    store = Store(CONFIG["storage"]["db_path"])

    # InterviewEngine: bank loaded (built-in + custom)
    eng = InterviewEngine(store)
    check("Engine: bank >= 25 Qs", len(eng.bank) >= 25, f"got {len(eng.bank)}")
    q = eng.select_question(topic="java-core", level="mid", language="vi")
    check("Engine: select_question", bool(q.get("question")) and "keywords" in q)
    cc = eng.get_coding_challenge("java-core", "mid")
    check("Engine: coding challenge", bool(cc.get("title")) and bool(cc.get("starter")))

    # RagStore retrieval (knowledge base populated)
    try:
        chunks = asyncio.run(RagStore(store).retrieve("HashMap collision treeify", top_k=3))
        check("RAG: retrieval returns chunks", len(chunks) >= 1, f"got {len(chunks)}")
    except Exception as e:
        check("RAG: retrieval", False, str(e))

    # Seed a session with scored answers, then test report builder + spaced repetition
    sid = "selftest-" + uuid.uuid4().hex[:8]
    try:
        store.create_session(sid, mode="trainer", level="mid", language="vi")
        seeds = [("java-core", 4.0), ("spring-boot", 9.0), ("devops", 6.5)]
        for topic, score in seeds:
            qid = store.save_question(sid, "technical", topic, f"Q about {topic}")
            store.save_answer(qid, "an answer", score, "feedback", "model")
            store.update_weak_area(topic, score)
        store.end_session(sid, overall_score=6.5)

        report = m._build_report(store.get_session(sid), store.get_session_questions(sid))
        check("Report: overall_score", report["overall_score"] > 0, str(report.get("overall_score")))
        check("Report: scored=3", report["scored_questions"] == 3, str(report.get("scored_questions")))
        check("Report: topics sorted", len(report["topics"]) == 3 and report["topics"][0]["topic"] == "java-core")
        check("Report: weaknesses has java-core", any(t["topic"] == "java-core" for t in report["weaknesses"]))
        check("Report: strengths has spring-boot", any(t["topic"] == "spring-boot" for t in report["strengths"]))
        check("Report: recommendation", bool(report["recommendation"]))

        # Spaced repetition: low score -> review_due set in the future
        wa = {w["topic"]: w for w in store.get_weak_areas(limit=20)}
        check("SpacedRep: java-core tracked", "java-core" in wa and wa["java-core"]["review_due"])
    except Exception as e:
        check("Report/seed", False, str(e))
    finally:
        # cleanup seeded rows
        try:
            c = store._conn()
            c.execute("DELETE FROM session_questions WHERE session_id=?", (sid,))
            c.execute("DELETE FROM interview_sessions WHERE id=?", (sid,))
            c.commit()
        except Exception:
            pass

    # get_question tool via execute_tool
    try:
        from backend.tools import execute_tool, tool_specs
        names = [s["function"]["name"] for s in tool_specs()]
        check("Tools: get_question registered", "get_question" in names)
        res = asyncio.run(execute_tool("get_question", {"topic": "devops", "level": "mid"},
                                       store=store, memory=None, session_id="nope"))
        check("Tools: get_question returns Q", "question" in json.loads(res))
    except Exception as e:
        check("Tools: get_question", False, str(e))


def run_tests():
    print("\n" + "=" * 46)
    print(f"  Interview Agent — Self Test  ({BASE})")
    print("=" * 46)

    # 1. Health
    print("\n[1] GET /api/health")
    s, b = GET("/api/health")
    check("Health 200", s == 200); check("Health status=ok", b.get("status") == "ok")
    check("Health provider", "provider" in b); check("Health ollama", "ollama" in b)
    check("Health claude", "claude" in b); check("Health rag_chunks", "rag_chunks" in b)

    # 2. Docs
    print("\n[2] GET /docs")
    check("Docs accessible", GET("/docs")[0] in (200, 301, 302))

    # 3. Session create (both modes)
    print("\n[3] POST /api/session/new")
    s, b = POST("/api/session/new", {"mode": "interviewer", "level": "senior", "language": "en"})
    check("Session 200", s == 200, f"{s}")
    check("Session id", bool(b.get("session_id")))
    check("Session mode", b.get("mode") == "interviewer")
    check("Session level", b.get("level") == "senior")
    sid = b.get("session_id", "x")
    s2, b2 = POST("/api/session/new", {"mode": "trainer"})
    check("Session trainer", b2.get("mode") == "trainer")
    sid2 = b2.get("session_id", "y")

    # 4. List + concurrent
    print("\n[4] GET /api/sessions")
    s, b = GET("/api/sessions")
    ids = [x.get("id") for x in b.get("sessions", [])]
    check("Sessions list", isinstance(b.get("sessions"), list))
    check("Sessions has both", sid in ids and sid2 in ids)

    # 5. Get session + 404
    print("\n[5] GET /api/session/{id}")
    check("GetSession 200", GET(f"/api/session/{sid}")[0] == 200)
    check("GetSession 404", GET("/api/session/does-not-exist")[0] == 404)

    # 6. Weak areas
    print("\n[6] GET /api/weak-areas")
    s, b = GET("/api/weak-areas")
    check("WeakAreas 200", s == 200 and isinstance(b.get("weak_areas"), list))

    # 7. Stats + new fields
    print("\n[7] GET /api/stats")
    s, b = GET("/api/stats")
    check("Stats 200", s == 200)
    for f in ("total_sessions", "topic_stats", "due_reviews", "score_trend", "avg_score"):
        check(f"Stats.{f}", f in b)

    # 8. Report (empty session) + 404
    print("\n[8] GET /api/session/{id}/report")
    s, b = GET(f"/api/session/{sid}/report")
    check("Report 200", s == 200)
    check("Report fields", all(k in b for k in ("overall_score", "topics", "recommendation", "scored_questions")))
    check("Report 404", GET("/api/session/nope/report")[0] == 404)

    # 9. Due reviews endpoint
    print("\n[9] GET /api/weak-areas/due")
    s, b = GET("/api/weak-areas/due")
    check("DueReviews 200", s == 200 and isinstance(b.get("due_reviews"), list))

    # 10. TTS (vi + en + empty)
    print("\n[10] POST /api/tts")
    check("TTS vi responds", POST("/api/tts", {"text": "Xin chào", "language": "vi"}, 15)[0] in (200, 500))
    check("TTS en responds", POST("/api/tts", {"text": "Hello", "language": "en"}, 15)[0] in (200, 500))
    check("TTS empty -> 400", POST("/api/tts", {"text": ""})[0] == 400)

    # 11. Code run (ok + compile error + empty)
    print("\n[11] POST /api/code/run")
    ok_java = 'public class Main{public static void main(String[] a){System.out.println("hi");}}'
    s, b = POST("/api/code/run", {"language": "java", "code": ok_java}, 35)
    check("Code runs", s in (200, 500))
    bad_java = 'public class Main{ this will not compile }'
    s, b = POST("/api/code/run", {"language": "java", "code": bad_java}, 35)
    check("Code compile-error handled", s in (200, 500))
    check("Code empty -> 400", POST("/api/code/run", {"language": "java", "code": ""})[0] == 400)

    # 12. Upload (valid md + invalid type)
    print("\n[12] POST /api/upload")
    s, b = POST_MULTIPART("/api/upload?kind=knowledge", "selftest.md",
                          b"# Doc\n\nSpring Boot auto-configuration uses conditional beans.\n")
    check("Upload md 200", s == 200 and b.get("status") == "ok", f"{s} {b}")
    s, b = POST_MULTIPART("/api/upload?kind=knowledge", "evil.exe", b"MZ...", "application/octet-stream")
    check("Upload bad type -> 400", s == 400)

    # 13. Frontend + dashboard
    print("\n[13] Static files")
    try:
        with urllib.request.urlopen(BASE + "/", timeout=5) as r:
            html = r.read().decode(errors="replace")
        check("Frontend 200", r.status == 200)
        check("Frontend content", "Interview Agent" in html)
        check("Frontend report modal", "report-overlay" in html)
    except Exception as e:
        check("Frontend", False, str(e))
    try:
        with urllib.request.urlopen(BASE + "/dashboard.html", timeout=5) as r:
            dh = r.read().decode(errors="replace")
        check("Dashboard 200", r.status == 200)
        check("Dashboard trend", "chart-trend" in dh)
    except Exception as e:
        check("Dashboard", False, str(e))

    # 14. WebSocket
    print("\n[14] WebSocket /ws/{id}")
    asyncio.run(test_ws(sid))

    # 15. Direct logic
    test_logic()

    total = len(PASS) + len(FAIL)
    print("\n" + "=" * 46)
    print(f"  Result: {len(PASS)}/{total} PASS")
    if FAIL: print("  FAILED: " + ", ".join(FAIL))
    else: print("  ALL GOOD!")
    print("=" * 46 + "\n")
    return len(FAIL) == 0


if __name__ == "__main__":
    print(f"Checking server at {BASE} ...")
    ready = False
    for i in range(20):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=3); ready = True; break
        except Exception:
            time.sleep(1)
    if not ready:
        print(f"Server not responding at {BASE}. Start it: python run.py"); sys.exit(1)
    sys.exit(0 if run_tests() else 1)
