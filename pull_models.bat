@echo off
chcp 65001 >nul
title Pull Ollama Models

echo.
echo ╔══════════════════════════════════════════════╗
echo ║     Pull Models cho Interview Agent          ║
echo ╚══════════════════════════════════════════════╝
echo.
echo Sẽ pull các model cần thiết. Mất thời gian tùy mạng.
echo.

ollama --version >nul 2>&1
if errorlevel 1 (
    echo [LỖI] Ollama chưa cài. Tải tại ollama.com
    pause & exit /b 1
)

echo [1/3] Pull LLM chính: qwen3:14b ~9GB
echo       (Dùng qwen3:8b nếu VRAM dưới 12GB - sửa config.yaml)
ollama pull qwen3:14b
if errorlevel 1 (
    echo [LỖI] Pull qwen3:14b thất bại. Thử qwen3:8b:
    ollama pull qwen3:8b
)

echo.
echo [2/3] Pull Embedding model: bge-m3 ~560MB
ollama pull bge-m3

echo.
echo [3/3] Pull Vision model (tuỳ chọn): qwen2.5vl:7b
echo       Bỏ qua nếu không cần nhìn ảnh/CV scan
set /p PULL_VISION="Pull vision model? (y/N): "
if /i "%PULL_VISION%"=="y" (
    ollama pull qwen2.5vl:7b
)

echo.
echo ══════════════════════════════════════════════
echo Models đã pull:
ollama list
echo.
echo Xong! Chạy start.bat để khởi động Interview Agent.
pause
