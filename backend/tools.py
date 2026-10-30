"""Tool registry cho Interview Agent.

Tools cho Ollama (JSON schema) và Claude -p (text format).
"""
from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable, Optional

# ── Tool specifications (Ollama native format) ───────────────────────────────
_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Lưu một sự thật quan trọng về user vào long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "Sự thật cần nhớ (ngắn gọn, dưới 200 ký tự)"},
                    "source": {"type": "string", "description": "Nguồn: interview, training, cv", "default": "interview"},
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Tìm kiếm thông tin trong long-term memory về user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Từ khoá cần tìm"},
                    "limit": {"type": "integer", "description": "Số kết quả tối đa", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "next_phase",
            "description": "Chuyển sang giai đoạn tiếp theo của phỏng vấn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "description": "Giai đoạn mới",
                        "enum": ["introduction", "background", "technical", "system_design", "behavioral", "qa"],
                    },
                    "reason": {"type": "string", "description": "Lý do chuyển phase"},
                },
                "required": ["phase"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_session",
            "description": "Kết thúc phiên phỏng vấn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "overall_score": {"type": "number", "description": "Điểm tổng 0-10"},
                    "summary": {"type": "string", "description": "Tóm tắt phiên"},
                },
                "required": ["overall_score", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_answer",
            "description": "Chấm điểm câu trả lời của user và cập nhật weak areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Chủ đề câu hỏi"},
                    "question": {"type": "string", "description": "Câu hỏi đã hỏi"},
                    "answer": {"type": "string", "description": "Câu trả lời của user"},
                    "score": {"type": "number", "description": "Điểm 0-10"},
                    "feedback": {"type": "string", "description": "Nhận xét ngắn gọn"},
                    "model_answer": {"type": "string", "description": "Câu trả lời mẫu"},
                },
                "required": ["topic", "question", "answer", "score", "feedback"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_coding_challenge",
            "description": "Lấy một bài tập coding phù hợp với topic và level hiện tại.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic: java-core, spring-boot, algorithms", "default": "java-core"},
                    "level": {"type": "string", "description": "Độ khó: junior, mid, senior", "default": "mid"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_question",
            "description": "Lấy một câu hỏi phỏng vấn có sẵn từ ngân hàng theo topic/level (kèm từ khoá kỳ vọng để chấm). Dùng khi muốn hỏi câu chuẩn, bám sát level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "java-core, spring-boot, microservices, devops, system-design, behavioral", "default": "java-core"},
                    "level": {"type": "string", "description": "junior, mid, senior", "default": "mid"},
                },
                "required": [],
            },
        },
    },
]

_DESCRIPTIONS = """
Bạn có thể gọi tool bằng cách xuất ĐÚNG JSON (không thêm text trước/sau):
{"action":"tool","tool":"<tên>","args":{<tham số>}}

Tools:
1. remember — lưu sự thật: {"fact":"...","source":"interview"}
2. recall   — tìm memory: {"query":"...","limit":5}
3. next_phase — chuyển phase: {"phase":"technical","reason":"..."}
4. end_session — kết thúc: {"overall_score":7.5,"summary":"..."}
5. score_answer — chấm điểm: {"topic":"java-core","question":"...","answer":"...","score":7.5,"feedback":"...","model_answer":"..."}
6. get_coding_challenge — lấy bài tập: {"topic":"java-core","level":"mid"}
7. get_question — lấy câu hỏi chuẩn từ ngân hàng: {"topic":"java-core","level":"mid"}
"""


def tool_specs() -> list:
    return _SPECS


def tools_prompt() -> str:
    return _DESCRIPTIONS


async def execute_tool(
    name: str,
    args: dict,
    store,
    memory,
    session_id: str,
    on_phase_change: Optional[Callable] = None,
    on_session_end: Optional[Callable] = None,
    emit: Optional[Callable] = None,
) -> str:
    if name == "remember":
        fact = args.get("fact", "").strip()
        source = args.get("source", "interview")
        if not fact:
            return "Không có gì để nhớ."
        return memory.remember(fact, source)

    if name == "recall":
        query = args.get("query", "")
        limit = int(args.get("limit", 5))
        return memory.recall(query, limit)

    if name == "next_phase":
        phase = args.get("phase", "technical")
        valid = ["introduction", "background", "technical", "system_design", "behavioral", "qa"]
        if phase not in valid:
            return f"Phase không hợp lệ: {phase}"
        if on_phase_change:
            await on_phase_change(phase)
        return f"Đã chuyển sang phase: {phase}"

    if name == "end_session":
        score = float(args.get("overall_score", 0))
        summary = args.get("summary", "")
        if on_session_end:
            await on_session_end(score, summary)
        store.end_session(session_id, overall_score=score)
        return f"Phiên kết thúc. Điểm tổng: {score:.1f}/10"

    if name == "score_answer":
        topic = args.get("topic", "general")
        question = args.get("question", "")
        answer = args.get("answer", "")
        score = float(args.get("score", 5))
        feedback = args.get("feedback", "")
        model_answer = args.get("model_answer", "")

        q_id = store.save_question(session_id, "technical", topic, question)
        store.save_answer(q_id, answer, score, feedback, model_answer)
        store.update_weak_area(topic, score)

        result = {"score": score, "feedback": feedback}
        if model_answer:
            result["model_answer"] = model_answer
        return json.dumps(result, ensure_ascii=False)

    if name == "get_coding_challenge":
        from .interview_engine import InterviewEngine
        engine = InterviewEngine(store)
        topic = args.get("topic", "java-core")
        level = args.get("level", "mid")
        challenge = engine.get_coding_challenge(topic, level)
        return json.dumps(challenge, ensure_ascii=False)

    if name == "get_question":
        from .interview_engine import InterviewEngine
        engine = InterviewEngine(store)
        topic = args.get("topic", "java-core")
        level = args.get("level", "mid")
        sess = store.get_session(session_id) or {}
        language = sess.get("language", "vi")
        q = engine.select_question(topic=topic, level=level, language=language, phase="technical")
        return json.dumps(q, ensure_ascii=False)

    return f"Tool '{name}' không được tìm thấy."
