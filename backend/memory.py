"""Long-term memory — Markdown vault (kế thừa từ Ultron).

3 tầng:
  core.md      : sự thật về bạn (CV summary, điểm mạnh/yếu, tiến độ) — luôn được nạp
  journal/*.md : nhật ký mỗi phiên — N bản gần nhất được priming
  history.jsonl: log thô mọi lượt
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


class Memory:
    def __init__(self, vault_dir: str, max_journal_priming: int = 8, store=None):
        self.vault = Path(vault_dir)
        self.journal_dir = self.vault / "journal"
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.core_path = self.vault / "core.md"
        self.max_journal_priming = max_journal_priming
        self.store = store
        self.embed_fn = None

        if not self.core_path.exists():
            self.core_path.write_text(
                "# Hồ sơ người dùng\n\n"
                "> Điền thông tin về bạn để Interview Agent hiểu và hỗ trợ tốt hơn.\n\n"
                "## Thông tin cơ bản\n"
                "- Tên: (chưa điền)\n"
                "- Level hiện tại: mid\n"
                "- Công nghệ chính: Java, Spring Boot\n\n"
                "## Điểm mạnh\n"
                "(chưa có dữ liệu)\n\n"
                "## Điểm yếu cần cải thiện\n"
                "(chưa có dữ liệu)\n\n"
                "## Tiến độ gần đây\n"
                "(chưa có phiên nào)\n",
                encoding="utf-8",
            )

    def prime(self) -> str:
        """Trả về khối văn bản nạp vào system prompt."""
        parts = ["## HỒ SƠ NGƯỜI DÙNG\n" + self.core_path.read_text(encoding="utf-8").strip()]
        journals = sorted(self.journal_dir.glob("*.md"), reverse=True)[: self.max_journal_priming]
        if journals:
            block = ["\n## NHẬT KÝ PHIÊN GẦN ĐÂY"]
            for p in journals:
                block.append(f"\n### {p.stem}\n{p.read_text(encoding='utf-8').strip()}")
            parts.append("\n".join(block))
        return "\n\n".join(parts).strip()

    def remember(self, fact: str, source: str = "session") -> str:
        """Thêm sự thật vào core.md."""
        fact = fact.strip()
        if not fact:
            return "Không có gì để nhớ."
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        existing = self.core_path.read_text(encoding="utf-8")
        if fact.lower() in existing.lower():
            return "Đã nhớ rồi."
        with open(self.core_path, "a", encoding="utf-8") as f:
            f.write(f"\n- ({ts}) [{source}] {fact}")
        return f"Đã nhớ: {fact[:80]}"

    def recall(self, query: str, limit: int = 5) -> str:
        """Tìm kiếm từ khoá trong vault."""
        query_lower = query.lower()
        hits: list[tuple[int, str]] = []
        for path in [self.core_path, *sorted(self.journal_dir.glob("*.md"), reverse=True)[:10]]:
            for line in path.read_text(encoding="utf-8").splitlines():
                score = sum(w in line.lower() for w in query_lower.split())
                if score:
                    hits.append((score, line.strip()))
        hits.sort(key=lambda x: -x[0])
        result = [h[1] for h in hits[:limit]]
        return "\n".join(result) if result else "(Không tìm thấy trong trí nhớ)"

    def write_journal(self, session_id: str, content: str):
        """Ghi nhật ký sau phiên phỏng vấn."""
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        path = self.journal_dir / f"{date_str}_{session_id[:8]}.md"
        path.write_text(
            f"# Phiên {session_id[:8]} — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{content}\n",
            encoding="utf-8",
        )

    def update_core(self, section: str, content: str):
        """Cập nhật một section trong core.md."""
        text = self.core_path.read_text(encoding="utf-8")
        pattern = re.compile(rf"(## {re.escape(section)}\n)(.*?)(\n## |\Z)", re.DOTALL)
        replacement = f"## {section}\n{content}\n\n## "
        new_text, n = pattern.subn(replacement, text)
        if n:
            self.core_path.write_text(new_text.rstrip() + "\n", encoding="utf-8")
        else:
            with open(self.core_path, "a", encoding="utf-8") as f:
                f.write(f"\n## {section}\n{content}\n")
