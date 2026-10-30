@echo off
chcp 65001 >nul
title Interview Agent

echo.
echo ╔══════════════════════════════════════════════╗
echo ║          INTERVIEW AGENT — Start             ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ── Bước 1: Kiểm tra Python ──────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [LỖI] Chưa cài Python. Tải tại python.org rồi chạy lại.
    pause & exit /b 1
)
echo [OK] Python đã sẵn sàng.

:: ── Bước 2: Tạo virtualenv nếu chưa có ──────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Tạo môi trường ảo...
    python -m venv .venv
)

:: ── Bước 3: Cài thư viện nếu cần ────────────────────────────────
call .venv\Scripts\activate.bat
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [INFO] Cài thư viện... ^(lần đầu mất vài phút^)
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [LỖI] Cài thư viện thất bại. Kiểm tra kết nối mạng.
        pause & exit /b 1
    )
)
echo [OK] Thư viện đã sẵn sàng.

:: ── Bước 4: Kiểm tra Ollama ──────────────────────────────────────
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [CẢNH BÁO] Ollama chưa cài hoặc chưa start.
    echo            Tải tại ollama.com, rồi chạy pull_models.bat
) else (
    echo [OK] Ollama đã sẵn sàng.
)

:: ── Bước 5: Kiểm tra model Ollama ────────────────────────────────
ollama list 2>nul | findstr /i "qwen3" >nul
if errorlevel 1 (
    echo [CẢNH BÁO] Chưa có model Qwen3. Chạy pull_models.bat trước.
    echo            Bỏ qua nếu dùng não Claude.
)

:: ── Bước 6: Docker Compose ───────────────────────────────────────
docker --version >nul 2>&1
if not errorlevel 1 (
    docker compose ps --quiet pgvector >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Khởi động Docker services...
        docker compose up -d --quiet-pull
        if errorlevel 1 (
            echo [CẢNH BÁO] Docker không start được. Tiếp tục với SQLite.
        ) else (
            echo [OK] Docker services đã lên.
        )
    ) else (
        echo [OK] Docker services đang chạy.
    )
) else (
    echo [INFO] Docker chưa cài - dùng SQLite thay pgvector.
)

:: ── Bước 7: Tạo thư mục data nếu chưa có ───────────────────────
if not exist "data\memory\core.md" (
    echo [INFO] Khởi tạo thư mục data...
    python -c "from backend.store import Store; Store('data/sessions/interview.db')" 2>nul
)

:: ── Bước 7b: Nạp knowledge base nếu còn trống ──────────────────
for /f %%c in ('python -c "from backend.store import Store; print(Store('data/sessions/interview.db').chunk_count())" 2^>nul') do set CHUNKS=%%c
if "%CHUNKS%"=="0" (
    echo [INFO] Knowledge base trong - dang nap tai lieu lan dau...
    python -m backend.ingest
    echo [OK] Da nap knowledge base.
) else (
    echo [OK] Knowledge base: %CHUNKS% chunks.
)

:: ── Bước 8: Mở browser ───────────────────────────────────────────
echo.
echo [INFO] Mở trình duyệt...
timeout /t 2 /nobreak >nul
start http://localhost:8080

:: ── Bước 9: Khởi động server ─────────────────────────────────────
echo [INFO] Khởi động Interview Agent server...
echo        Bấm Ctrl+C để dừng.
echo.
python run.py

pause
