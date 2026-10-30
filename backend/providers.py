"""Dual-brain providers — kế thừa từ Ultron, adapt cho Interview Agent.

OllamaProvider  : tool calling gốc Ollama, stream mượt.
ClaudeProvider  : gọi `claude -p`, giao thức JSON cho tool.

Cả hai trả về cùng cấu trúc:
  { "content": str, "tool_calls": [{"name","args"}], "assistant_msg": {...} }
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
from typing import Awaitable, Callable

from .config import CONFIG
from . import tools as toolkit

EmitFn = Callable[[dict], Awaitable[None]]


class ProviderError(Exception):
    pass


# ── Lọc <think>...</think> của Qwen3 ────────────────────────────────────────
class ThinkFilter:
    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.inside = False
        self.pending = ""

    @staticmethod
    def _tail_overlap(s: str, tag: str) -> int:
        for k in range(min(len(s), len(tag) - 1), 0, -1):
            if s.endswith(tag[:k]):
                return k
        return 0

    def feed(self, text: str) -> str:
        if not self.enabled:
            return text
        self.pending += text
        out: list[str] = []
        while True:
            if not self.inside:
                i = self.pending.find(self.OPEN)
                if i == -1:
                    keep = self._tail_overlap(self.pending, self.OPEN)
                    cut = len(self.pending) - keep
                    out.append(self.pending[:cut])
                    self.pending = self.pending[cut:]
                    break
                out.append(self.pending[:i])
                self.pending = self.pending[i + len(self.OPEN):]
                self.inside = True
            else:
                j = self.pending.find(self.CLOSE)
                if j == -1:
                    keep = self._tail_overlap(self.pending, self.CLOSE)
                    self.pending = self.pending[len(self.pending) - keep:]
                    break
                self.pending = self.pending[j + len(self.CLOSE):]
                self.inside = False
        return "".join(out)

    def flush(self) -> str:
        rem = "" if self.inside else self.pending
        self.pending = ""
        return rem


# ── Base ─────────────────────────────────────────────────────────────────────
class BaseProvider:
    name = "base"

    def set_model(self, model: str): pass

    async def health_check(self) -> tuple[bool, str]:
        raise NotImplementedError

    async def run_step(self, messages: list[dict], emit: EmitFn) -> dict:
        raise NotImplementedError


# ── Ollama ───────────────────────────────────────────────────────────────────
class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self):
        import ollama
        self._ollama = ollama
        oc = CONFIG["ollama"]
        self.host = oc["host"]
        self.model = (oc.get("models", {}) or {}).get("default") or oc["brain_model"]
        self.client = ollama.AsyncClient(host=self.host)
        self.options = {"num_ctx": oc["num_ctx"], "temperature": oc["temperature"]}
        self.think = oc.get("think", False)
        self.strip = CONFIG["agent"].get("strip_thinking", True)
        self.keep_alive = oc.get("keep_alive", "30m")

    def set_model(self, model: str):
        if model:
            self.model = model

    async def warmup(self):
        try:
            await self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                options={"num_predict": 1},
                keep_alive=self.keep_alive,
                stream=False,
            )
        except Exception:
            pass

    async def health_check(self) -> tuple[bool, str]:
        try:
            data = await self.client.list()
            names = [m.get("model", m.get("name", "")) for m in data.get("models", [])]
            if not any(self.model in n for n in names):
                return False, (f"Ollama chạy nhưng chưa có model '{self.model}'. "
                               f"Chạy: ollama pull {self.model}")
            return True, f"Ollama OK ({self.model})"
        except Exception as e:
            return False, f"Không kết nối Ollama tại {self.host}. Ollama đã bật chưa? ({e})"

    async def _chat(self, messages):
        kwargs = dict(
            model=self.model,
            messages=messages,
            tools=toolkit.tool_specs(),
            options=self.options,
            stream=True,
            keep_alive=self.keep_alive,
        )
        try:
            return await self.client.chat(think=self.think, **kwargs)
        except (self._ollama.ResponseError, TypeError):
            return await self.client.chat(**kwargs)

    async def run_step(self, messages, emit):
        try:
            stream = await self._chat(messages)
        except Exception as e:
            raise ProviderError(f"Ollama lỗi: {e}") from e

        tf = ThinkFilter(self.strip)
        content, visible, speaking = "", "", False
        raw_tool_calls: list = []

        async for chunk in stream:
            msg = chunk.message
            if getattr(msg, "content", None):
                content += msg.content
                clean = tf.feed(msg.content)
                if clean:
                    if not speaking:
                        await emit({"type": "state", "value": "speaking"})
                        speaking = True
                    visible += clean
                    await emit({"type": "token", "text": clean})
            if getattr(msg, "tool_calls", None):
                raw_tool_calls.extend(msg.tool_calls)

        tail = tf.flush()
        if tail:
            visible += tail
            await emit({"type": "token", "text": tail})

        tool_calls = [
            {"name": tc.function.name, "args": dict(tc.function.arguments or {})}
            for tc in raw_tool_calls
        ]
        assistant_msg = {"role": "assistant", "content": content}
        if raw_tool_calls:
            assistant_msg["tool_calls"] = [
                {"function": {"name": tc.function.name, "arguments": dict(tc.function.arguments or {})}}
                for tc in raw_tool_calls
            ]
        return {"content": visible.strip(), "tool_calls": tool_calls, "assistant_msg": assistant_msg}


# ── Claude (-p) ──────────────────────────────────────────────────────────────
class ClaudeProvider(BaseProvider):
    name = "claude"
    STREAM_TIMEOUT = 180

    def __init__(self):
        cc = CONFIG.get("claude", {})
        self.cli = cc.get("cli", "claude")
        self.model = cc.get("model", "") or ""
        self.use_subscription = cc.get("use_subscription", True)
        self.permission_mode = (cc.get("permission_mode", "") or "").strip()
        self.allowed_tools = cc.get("allowed_tools", []) or []
        self.disallowed_tools = cc.get("disallowed_tools", []) or []
        self.effort = (cc.get("effort", "") or "").strip()
        self.idle_timeout = float(cc.get("idle_timeout", 180) or 180)
        self.stream_timeout = float(cc.get("stream_timeout", self.STREAM_TIMEOUT) or self.STREAM_TIMEOUT)
        self.path = shutil.which(self.cli)

    def _perm_flags(self) -> list[str]:
        flags: list[str] = []
        if self.effort:
            flags += ["--effort", self.effort]
        if self.permission_mode:
            flags += ["--permission-mode", self.permission_mode]
        if self.disallowed_tools:
            flags += ["--disallowedTools", *[str(t) for t in self.disallowed_tools]]
        if self.allowed_tools:
            flags += ["--allowedTools", *[str(t) for t in self.allowed_tools]]
        return flags

    def _env(self):
        import os
        env = dict(os.environ)
        if self.use_subscription:
            env.pop("ANTHROPIC_API_KEY", None)
            env.pop("ANTHROPIC_AUTH_TOKEN", None)
        return env

    async def health_check(self) -> tuple[bool, str]:
        if not self.path:
            return False, f"Không tìm thấy '{self.cli}'. Cài Claude Code và đăng nhập."
        try:
            proc = await asyncio.create_subprocess_exec(
                self.path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            if proc.returncode == 0:
                return True, f"Claude OK ({out.decode(errors='ignore').strip()})"
            return False, "Claude CLI lỗi."
        except Exception as e:
            return False, f"Không chạy được Claude CLI: {e}"

    def _build_prompt(self, messages: list[dict]) -> str:
        parts: list[str] = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                parts.append(content)
                parts.append("\n" + toolkit.tools_prompt())
            elif role == "user":
                parts.append(f"\n[NGƯỜI DÙNG]: {content}")
            elif role == "assistant":
                if content:
                    parts.append(f"\n[BẠN]: {content}")
                for tc in m.get("tool_calls", []):
                    fn = tc.get("function", {})
                    parts.append(
                        f'\n[BẠN gọi tool]: {fn.get("name")} '
                        f'{json.dumps(fn.get("arguments", {}), ensure_ascii=False)}'
                    )
            elif role == "tool":
                parts.append(f"\n[KẾT QUẢ TOOL {m.get('tool_name','')}]: {content}")
        parts.append(
            "\n\nHãy trả lời tiếp cho [NGƯỜI DÙNG]. "
            "Nếu cần dùng tool, chỉ xuất DUY NHẤT một dòng JSON như hướng dẫn."
        )
        return "\n".join(parts)

    async def run_step(self, messages, emit):
        if not self.path:
            raise ProviderError("Claude CLI chưa sẵn sàng.")
        prompt = self._build_prompt(messages)
        cmd = [
            self.path, "-p",
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
        ]
        if self.model:
            cmd += ["--model", self.model]
        cmd += self._perm_flags()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._env(),
                limit=10 * 1024 * 1024,
            )
        except Exception as e:
            raise ProviderError(f"Không gọi được Claude: {e}") from e

        proc.stdin.write(prompt.encode("utf-8"))
        try:
            await proc.stdin.drain()
        except Exception:
            pass
        proc.stdin.close()

        full, visible, mode = "", "", None
        in_text, speaking = False, False
        result_text, is_error, err_msg = None, False, ""

        try:
            while True:
                try:
                    raw = await asyncio.wait_for(proc.stdout.readline(), timeout=self.idle_timeout)
                except asyncio.TimeoutError as e:
                    raise ProviderError(f"Claude im lặng quá {self.idle_timeout:g}s.") from e
                if not raw:
                    if result_text is not None or is_error:
                        break
                    raise ProviderError("Claude kết thúc bất thường.")
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                et = ev.get("type")
                if et == "stream_event":
                    e = ev.get("event", {})
                    st = e.get("type")
                    if st == "content_block_start":
                        in_text = e.get("content_block", {}).get("type") == "text"
                    elif st == "content_block_stop":
                        in_text = False
                    elif st == "content_block_delta":
                        delta = e.get("delta", {})
                        if in_text and delta.get("type") == "text_delta":
                            chunk = delta.get("text", "")
                            full += chunk
                            if mode is None and full.strip():
                                s = full.lstrip()
                                mode = "tool" if (s[0] == "{" or s.startswith("```")) else "text"
                            if mode == "text" and chunk:
                                if not speaking:
                                    await emit({"type": "state", "value": "speaking"})
                                    speaking = True
                                visible += chunk
                                await emit({"type": "token", "text": chunk})
                elif et == "result":
                    if ev.get("is_error"):
                        is_error, err_msg = True, ev.get("result", "")
                    else:
                        result_text = ev.get("result", full)
                    break
        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:
                pass

        if is_error:
            raise ProviderError(f"Claude lỗi: {err_msg}")

        text = (result_text if result_text is not None else full).strip()
        tool_call = _parse_tool_json(text)
        if tool_call:
            return {
                "content": "",
                "tool_calls": [tool_call],
                "assistant_msg": {"role": "assistant", "content": text},
            }
        if mode != "text" and text:
            visible = text
            await emit({"type": "state", "value": "speaking"})
            await emit({"type": "token", "text": text})

        return {
            "content": (visible or text).strip(),
            "tool_calls": [],
            "assistant_msg": {"role": "assistant", "content": text},
        }


def _parse_tool_json(text: str) -> dict | None:
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[4:] if s.lower().startswith("json") else s
        s = s.strip()
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start : i + 1])
                except json.JSONDecodeError:
                    return None
                if isinstance(obj, dict) and obj.get("action") == "tool" and obj.get("tool"):
                    return {"name": obj["tool"], "args": obj.get("args", {}) or {}}
                return None
    return None


def make_provider(name: str) -> BaseProvider:
    key = (name or "").lower()
    if key == "ollama":
        return OllamaProvider()
    if key == "claude":
        return ClaudeProvider()
    raise ProviderError(f"Không có provider '{name}'. Chọn: ollama | claude")
