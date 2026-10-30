"""Code execution sandbox — Docker hoặc subprocess fallback.

Hỗ trợ: Java (primary), Python (bonus)
Timeout: 15s, Memory: 128MB
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from .config import CONFIG

SANDBOX_IMAGE = "interview-agent-sandbox"
JAVA_TIMEOUT = 15
PY_TIMEOUT = 10


async def _run_cmd(cmd: list[str], stdin: str = "", timeout: int = 15) -> tuple[str, str, int]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin.encode("utf-8")),
            timeout=timeout,
        )
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return "", f"Timeout sau {timeout}s", -1
    except Exception as e:
        return "", str(e), -1


async def _docker_available() -> bool:
    out, _, rc = await _run_cmd(["docker", "info"], timeout=5)
    return rc == 0


async def _image_exists() -> bool:
    _, _, rc = await _run_cmd(["docker", "inspect", SANDBOX_IMAGE], timeout=5)
    return rc == 0


async def run_java_docker(code: str) -> dict:
    stdout, stderr, rc = await _run_cmd(
        [
            "docker", "run", "--rm", "--network", "none",
            "--memory", "128m", "--memory-swap", "128m",
            "--cpus", "0.5",
            "-i", SANDBOX_IMAGE,
        ],
        stdin=code,
        timeout=JAVA_TIMEOUT + 5,
    )
    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": rc,
        "engine": "docker",
        "success": rc == 0,
    }


async def run_java_subprocess(code: str) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "Main.java"
        src.write_text(code, encoding="utf-8")

        # Compile
        co, ce, crc = await _run_cmd(
            ["javac", "-d", tmpdir, str(src)],
            timeout=10,
        )
        if crc != 0:
            return {"stdout": "", "stderr": ce or "Lỗi compile", "exit_code": crc,
                    "engine": "local", "success": False}

        # Run
        ro, re_, rrc = await _run_cmd(
            ["java", "-cp", tmpdir, "-Xmx128m", "-Xss512k", "Main"],
            timeout=JAVA_TIMEOUT,
        )
        return {"stdout": ro, "stderr": re_, "exit_code": rrc,
                "engine": "local", "success": rrc == 0}


async def run_python_subprocess(code: str) -> dict:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        fpath = f.name
    try:
        out, err, rc = await _run_cmd(
            ["python", "-c", code],
            timeout=PY_TIMEOUT,
        )
        return {"stdout": out, "stderr": err, "exit_code": rc,
                "engine": "local", "success": rc == 0}
    finally:
        try:
            os.unlink(fpath)
        except Exception:
            pass


async def run_code(language: str, code: str) -> dict:
    lang = language.lower()
    if lang in ("java", "java21"):
        if await _docker_available() and await _image_exists():
            return await run_java_docker(code)
        return await run_java_subprocess(code)
    if lang == "python":
        return await run_python_subprocess(code)
    return {
        "stdout": "",
        "stderr": f"Ngôn ngữ '{language}' chưa được hỗ trợ. Dùng: java, python",
        "exit_code": -1,
        "engine": "none",
        "success": False,
    }
