"""Agent loop chính của Interview Agent.

Vòng lặp:
  1. Nhận tin nhắn từ user
  2. Retrieve RAG context liên quan
  3. Emit state=thinking
  4. Gọi provider.run_step() → stream tokens về client
  5. Nếu có tool call → execute_tool() → nạp kết quả → gọi lại provider
  6. Lưu messages vào SQLite
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from .config import CONFIG
from .memory import Memory
from .prompt import build_system_prompt
from .providers import ProviderError, make_provider
from .rag import RagStore
from .store import Store
from .tools import execute_tool

EmitFn = Callable[[dict], Awaitable[None]]

_MAX_TOOL_ROUNDS = 5
_RAG_CONTEXT_CHARS = 1200  # cắt RAG context để không vượt context window


class Brain:
    def __init__(self, session_id: str, mode: str = "interviewer", language: str = "vi"):
        self.session_id = session_id
        self.mode = mode
        self.language = language
        self.phase = "introduction"

        cfg = CONFIG
        self.store = Store(cfg["storage"]["db_path"])
        self.memory = Memory(
            cfg["memory"]["vault_dir"],
            cfg["memory"].get("max_journal_priming", 8),
            store=self.store,
        )
        self.rag = RagStore(self.store)
        self.provider = make_provider(cfg["agent"]["provider"])

        # Tạo session trong DB nếu chưa có
        self.store.create_session(session_id, mode=mode, language=language)

        # Build system prompt
        user_profile = self.memory.prime() if mode == "trainer" else ""
        system_content = build_system_prompt(
            mode=mode, phase=self.phase, language=language,
            user_profile=user_profile, weak_areas=self._weak_areas_text(),
        )

        self.messages: list[dict] = [{"role": "system", "content": system_content}]
        history = self.store.get_session_messages(
            session_id, limit=cfg["memory"].get("history_turns", 30),
        )
        self.messages.extend(history)

    def _weak_areas_text(self) -> str:
        """Tom tat diem yeu (chi dung cho trainer mode) -> text cho prompt."""
        if self.mode != "trainer":
            return ""
        try:
            areas = self.store.get_weak_areas(limit=5)
            weak = [a for a in areas if (a.get("avg_score") or 10) < 7]
            if not weak:
                return ""
            return "\n".join(f"- {a['topic']}: {a['avg_score']:.1f}/10 "
                              f"({a.get('total_attempts', 0)} lần)" for a in weak)
        except Exception:
            return ""

    def _rebuild_system(self):
        user_profile = self.memory.prime() if self.mode == "trainer" else ""
        new_system = build_system_prompt(
            mode=self.mode, phase=self.phase, language=self.language,
            user_profile=user_profile, weak_areas=self._weak_areas_text(),
        )
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = new_system
        else:
            self.messages.insert(0, {"role": "system", "content": new_system})

    async def _get_rag_context(self, query: str) -> str:
        if not query or len(query) < 10:
            return ""
        try:
            chunks = await self.rag.retrieve(query, top_k=3)
            if not chunks:
                return ""
            parts = []
            total = 0
            for c in chunks:
                text = c.get("text", "")
                if total + len(text) > _RAG_CONTEXT_CHARS:
                    break
                parts.append(f"[{c.get('topic','?')}] {text}")
                total += len(text)
            return "\n---\n".join(parts)
        except Exception:
            return ""

    async def _on_phase_change(self, phase: str):
        self.phase = phase
        self._rebuild_system()
        self.store.update_session_phase(self.session_id, phase)

    async def _on_session_end(self, score: float, summary: str):
        self.store.end_session(self.session_id, overall_score=score)
        self.memory.write_journal(self.session_id, summary)

    async def chat(self, user_text: str, emit: EmitFn) -> str:
        self.store.save_message(self.session_id, "user", user_text)
        self.messages.append({"role": "user", "content": user_text})

        await emit({"type": "state", "value": "thinking"})

        # RAG: retrieve relevant knowledge chunks
        rag_ctx = await self._get_rag_context(user_text)
        if rag_ctx:
            # Inject RAG context as a temporary system note
            ctx_msg = {
                "role": "system",
                "content": f"[Kiến thức liên quan từ knowledge base]\n{rag_ctx}",
            }
            # Insert right before the last user message
            self.messages.insert(-1, ctx_msg)

        final_content = ""
        for _round in range(_MAX_TOOL_ROUNDS):
            try:
                result = await self.provider.run_step(self.messages, emit)
            except ProviderError as e:
                await emit({"type": "error", "message": str(e)})
                return str(e)

            self.messages.append(result["assistant_msg"])
            final_content = result["content"]

            if not result["tool_calls"]:
                break

            for tc in result["tool_calls"]:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})

                await emit({"type": "tool", "name": tool_name, "status": "running"})

                try:
                    tool_result = await execute_tool(
                        name=tool_name, args=tool_args,
                        store=self.store, memory=self.memory,
                        session_id=self.session_id,
                        on_phase_change=self._on_phase_change,
                        on_session_end=self._on_session_end,
                    )
                except Exception as e:
                    tool_result = f"Lỗi tool: {e}"

                await emit({"type": "tool", "name": tool_name, "status": "done",
                            "result": str(tool_result)[:200]})

                self.messages.append({
                    "role": "tool", "tool_name": tool_name, "content": str(tool_result),
                })

        # Remove temporary RAG context message to avoid context bloat
        if rag_ctx:
            self.messages = [m for m in self.messages
                             if not (m.get("role") == "system" and
                                     m.get("content", "").startswith("[Kiến thức liên quan"))]

        if final_content:
            self.store.save_message(self.session_id, "assistant", final_content)

        await emit({"type": "done", "content": final_content})
        return final_content

    async def switch_mode(self, mode: str):
        self.mode = mode
        self._rebuild_system()
        self.store.update_session_phase(self.session_id, self.phase)

    async def set_language(self, language: str):
        self.language = language
        self._rebuild_system()

    async def health(self) -> dict:
        ok, msg = await self.provider.health_check()
        return {
            "provider": self.provider.name,
            "ok": ok, "message": msg,
            "rag_chunks": self.rag.chunk_count(),
            "mode": self.mode,
            "phase": self.phase,
        }
