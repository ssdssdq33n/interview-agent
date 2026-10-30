"""Entry point — chay: python run.py"""
import sys
import os

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Đảm bảo chạy đúng thư mục dự án
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import uvicorn
from backend.config import CONFIG

if __name__ == "__main__":
    srv = CONFIG.get("server", {})
    host = srv.get("host", "127.0.0.1")
    port = srv.get("port", 8080)

    print(f"""
╔══════════════════════════════════════════════╗
║         INTERVIEW AGENT — đang khởi động     ║
║                                              ║
║  Não: {CONFIG['agent']['provider'].upper():<38}║
║  Model: {CONFIG['ollama']['brain_model']:<36}║
║  Server: http://{host}:{port:<24}║
╚══════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
