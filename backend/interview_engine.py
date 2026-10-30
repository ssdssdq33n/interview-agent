"""Interview Engine — sinh câu hỏi, chấm điểm, chọn topic.

Tích hợp với Brain qua RAG + LLM scoring.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Optional

from .config import CONFIG, DATA_DIR
from .store import Store

# ── Built-in question bank (fallback khi RAG chưa có dữ liệu) ─────────────
_QUESTION_BANK: list[dict] = [
    # Java Core
    {"topic": "java-core", "level": "junior", "lang": "vi",
     "q": "Sự khác nhau giữa abstract class và interface trong Java là gì?",
     "keywords": ["abstract", "interface", "implements", "extends", "default method"]},
    {"topic": "java-core", "level": "mid", "lang": "vi",
     "q": "Giải thích cơ chế hoạt động của HashMap. Khi nào xảy ra collision và Java xử lý thế nào?",
     "keywords": ["hash", "bucket", "linked list", "treeify", "load factor", "capacity"]},
    {"topic": "java-core", "level": "mid", "lang": "vi",
     "q": "Phân biệt Checked Exception và Unchecked Exception. Khi nào dùng RuntimeException?",
     "keywords": ["checked", "unchecked", "RuntimeException", "try-catch", "throws"]},
    {"topic": "java-core", "level": "senior", "lang": "vi",
     "q": "Giải thích Java Memory Model (JMM) và happens-before relationship. Khi nào cần volatile?",
     "keywords": ["happens-before", "volatile", "synchronized", "visibility", "ordering", "JMM"]},
    {"topic": "java-core", "level": "mid", "lang": "en",
     "q": "Explain the difference between synchronized methods and synchronized blocks. Which is preferred?",
     "keywords": ["monitor", "lock", "method", "block", "this", "class", "granularity"]},

    # Spring Boot
    {"topic": "spring-boot", "level": "junior", "lang": "vi",
     "q": "Spring Boot autoconfiguration hoạt động như thế nào? Giải thích @SpringBootApplication.",
     "keywords": ["@SpringBootApplication", "@EnableAutoConfiguration", "@ComponentScan", "spring.factories"]},
    {"topic": "spring-boot", "level": "mid", "lang": "vi",
     "q": "Phân biệt @Component, @Service, @Repository, @Controller. Ý nghĩa thực sự là gì?",
     "keywords": ["stereotype", "AOP", "exception translation", "component scan", "@Repository"]},
    {"topic": "spring-boot", "level": "mid", "lang": "vi",
     "q": "Giải thích Bean Lifecycle trong Spring. ApplicationContext vs BeanFactory?",
     "keywords": ["BeanFactory", "ApplicationContext", "InitializingBean", "@PostConstruct", "destroy"]},
    {"topic": "spring-boot", "level": "senior", "lang": "vi",
     "q": "Giải thích Spring AOP: proxy pattern, JDK dynamic proxy vs CGLIB. Limitations là gì?",
     "keywords": ["AOP", "proxy", "JDK proxy", "CGLIB", "self-invocation", "pointcut", "advice"]},

    # Microservices
    {"topic": "microservices", "level": "mid", "lang": "vi",
     "q": "Giải thích các pattern để xử lý distributed transaction: Saga, 2PC. Khi nào dùng mỗi cái?",
     "keywords": ["Saga", "2PC", "choreography", "orchestration", "eventual consistency", "rollback"]},
    {"topic": "microservices", "level": "senior", "lang": "vi",
     "q": "Circuit Breaker pattern hoạt động thế nào? Giải thích 3 trạng thái và cách implement với Resilience4j.",
     "keywords": ["closed", "open", "half-open", "threshold", "Resilience4j", "fallback"]},
    {"topic": "microservices", "level": "mid", "lang": "en",
     "q": "What are the trade-offs between synchronous REST and asynchronous messaging (Kafka/RabbitMQ) in microservices?",
     "keywords": ["coupling", "latency", "reliability", "eventual consistency", "message queue"]},

    # DevOps
    {"topic": "devops", "level": "junior", "lang": "vi",
     "q": "Giải thích sự khác nhau giữa Docker image và container. Dockerfile ENTRYPOINT vs CMD?",
     "keywords": ["image", "container", "layer", "ENTRYPOINT", "CMD", "override"]},
    {"topic": "devops", "level": "mid", "lang": "vi",
     "q": "Kubernetes: Pod, Deployment, Service, Ingress — giải thích và mối quan hệ giữa chúng.",
     "keywords": ["Pod", "Deployment", "ReplicaSet", "Service", "Ingress", "ClusterIP", "LoadBalancer"]},
    {"topic": "devops", "level": "mid", "lang": "vi",
     "q": "Giải thích CI/CD pipeline. Các stage điển hình và cách tối ưu build time?",
     "keywords": ["CI", "CD", "pipeline", "stages", "cache", "artifact", "deploy"]},

    # System Design
    {"topic": "system-design", "level": "senior", "lang": "vi",
     "q": "Thiết kế một hệ thống URL shortener (giống bit.ly). Yêu cầu: 1B URLs, 100M DAU.",
     "keywords": ["hash", "Base62", "database", "cache", "CDN", "redirect", "analytics"]},
    {"topic": "system-design", "level": "senior", "lang": "vi",
     "q": "Thiết kế rate limiting service. Các thuật toán nào có thể dùng? Trade-off?",
     "keywords": ["token bucket", "sliding window", "fixed window", "Redis", "distributed", "header"]},

    # Behavioral
    {"topic": "behavioral", "level": "mid", "lang": "vi",
     "q": "Kể về một tình huống bạn phải xử lý conflict với đồng nghiệp. Bạn đã làm thế nào?",
     "keywords": ["STAR", "situation", "task", "action", "result", "communication"]},
    {"topic": "behavioral", "level": "mid", "lang": "vi",
     "q": "Mô tả một dự án khó nhất bạn từng làm. Khó khăn lớn nhất là gì và bạn giải quyết thế nào?",
     "keywords": ["challenge", "approach", "team", "solution", "result", "learned"]},
    {"topic": "behavioral", "level": "senior", "lang": "vi",
     "q": "Làm thế nào bạn balance giữa technical debt và tính năng mới? Bạn đã thuyết phục stakeholder thế nào?",
     "keywords": ["trade-off", "refactor", "business", "stakeholder", "technical debt", "prioritize"]},
]

# Coding challenges
_CODING_CHALLENGES: list[dict] = [
    {"topic": "java-core", "level": "junior",
     "title": "FizzBuzz nâng cao",
     "description": "Viết hàm trả về list string từ 1 đến n:\n- Bội số 3: 'Fizz'\n- Bội số 5: 'Buzz'\n- Bội số 15: 'FizzBuzz'\n- Ngược lại: số đó",
     "starter": "import java.util.*;\npublic class Main {\n    public static List<String> fizzBuzz(int n) {\n        // TODO\n        return new ArrayList<>();\n    }\n    public static void main(String[] args) {\n        System.out.println(fizzBuzz(15));\n    }\n}",
     "expected": "[1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz]"},

    {"topic": "java-core", "level": "mid",
     "title": "Two Sum",
     "description": "Cho mảng int[] nums và int target, trả về index của 2 phần tử có tổng bằng target. Yêu cầu O(n).",
     "starter": "import java.util.*;\npublic class Main {\n    public static int[] twoSum(int[] nums, int target) {\n        // TODO: O(n) solution\n        return new int[]{};\n    }\n    public static void main(String[] args) {\n        System.out.println(Arrays.toString(twoSum(new int[]{2,7,11,15}, 9)));\n    }\n}",
     "expected": "[0, 1]"},

    {"topic": "java-core", "level": "mid",
     "title": "Reverse Linked List",
     "description": "Reverse một linked list. Implement cả iterative và recursive solution.",
     "starter": "public class Main {\n    static class ListNode {\n        int val;\n        ListNode next;\n        ListNode(int val) { this.val = val; }\n    }\n    public static ListNode reverseList(ListNode head) {\n        // TODO\n        return null;\n    }\n    public static void main(String[] args) {\n        // Test: 1->2->3->4->5 -> 5->4->3->2->1\n        ListNode head = new ListNode(1);\n        head.next = new ListNode(2);\n        head.next.next = new ListNode(3);\n        ListNode r = reverseList(head);\n        while(r!=null){System.out.print(r.val+\" \");r=r.next;}\n    }\n}",
     "expected": "5 4 3 2 1"},

    {"topic": "spring-boot", "level": "senior",
     "title": "Custom Spring Annotation",
     "description": "Tạo annotation @RateLimit(maxCalls=5, window=60) để giới hạn số lần gọi một method trong 60 giây.\nDùng Spring AOP để implement.",
     "starter": "// Implement:\n// 1. @interface RateLimit\n// 2. RateLimitAspect với @Around\n// 3. In-memory tracking với ConcurrentHashMap\npublic class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Spring AOP Rate Limiter\");\n        System.out.println(\"See implementation files\");\n    }\n}",
     "expected": "Spring AOP Rate Limiter"},
]


def _load_custom_questions() -> list[dict]:
    """Nap cau hoi custom tu data/questions/*.yaml (neu co)."""
    q_dir = DATA_DIR / "questions"
    loaded: list[dict] = []
    if not q_dir.exists():
        return loaded
    try:
        import yaml
    except Exception:
        return loaded
    for path in list(q_dir.glob("*.yaml")) + list(q_dir.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[ENGINE] Cannot parse {path.name}: {e}", flush=True)
            continue
        items = data.get("questions", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict) or not it.get("question"):
                continue
            loaded.append({
                "topic": it.get("topic", "general"),
                "level": it.get("level", "mid"),
                "lang": it.get("language", it.get("lang", "vi")),
                "q": it["question"],
                "keywords": it.get("expected_keywords", it.get("keywords", [])),
                "model_answer": it.get("model_answer", ""),
            })
    if loaded:
        print(f"[ENGINE] Loaded {len(loaded)} custom questions", flush=True)
    return loaded


class InterviewEngine:
    def __init__(self, store: Store):
        self.store = store
        # Built-in bank + custom questions tu YAML
        self.bank = list(_QUESTION_BANK) + _load_custom_questions()

    def select_question(
        self, topic: str = "java-core", level: str = "mid",
        language: str = "vi", phase: str = "technical",
        exclude_ids: list[int] | None = None,
    ) -> dict:
        bank = self.bank
        if phase == "behavioral":
            candidates = [q for q in bank if q["topic"] == "behavioral"]
        else:
            # Uu tien dung ngon ngu + topic + level
            candidates = [q for q in bank
                          if q["topic"] == topic and q["level"] == level
                          and q.get("lang", "vi") == language]
            if not candidates:
                candidates = [q for q in bank
                              if q["topic"] == topic and q["level"] == level]
            if not candidates:
                candidates = [q for q in bank if q["topic"] == topic]
            if not candidates:
                candidates = bank

        if not candidates:
            return {"topic": topic, "question": f"Hãy kể về kinh nghiệm với {topic}", "keywords": []}

        q = random.choice(candidates)
        return {
            "topic": q["topic"], "question": q["q"],
            "keywords": q.get("keywords", []),
            "model_answer": q.get("model_answer", ""),
        }

    def get_coding_challenge(self, topic: str = "java-core", level: str = "mid") -> dict:
        candidates = [c for c in _CODING_CHALLENGES if c["topic"] == topic and c["level"] == level]
        if not candidates:
            candidates = [c for c in _CODING_CHALLENGES if c["level"] == level]
        if not candidates:
            candidates = _CODING_CHALLENGES
        return random.choice(candidates)

    def get_next_topic(self, weak_areas: list[dict], focus: list[str] | None = None) -> str:
        if not focus:
            focus = CONFIG.get("interview", {}).get("focus_areas", ["java-core", "spring-boot"])
        if weak_areas:
            due = [w for w in weak_areas if w.get("avg_score", 10) < 7]
            if due:
                weak_topic = due[0]["topic"]
                if weak_topic in focus:
                    return weak_topic
        return random.choice(focus)

    def format_score_feedback(self, score: float, feedback: str, model_answer: str,
                               language: str = "vi") -> str:
        stars = "★" * round(score / 2) + "☆" * (5 - round(score / 2))
        if language == "vi":
            s = f"📊 **Điểm: {score:.1f}/10** {stars}\n\n"
            s += f"💬 **Nhận xét:** {feedback}\n\n"
            if model_answer:
                s += f"✅ **Câu trả lời mẫu:**\n{model_answer}"
        else:
            s = f"📊 **Score: {score:.1f}/10** {stars}\n\n"
            s += f"💬 **Feedback:** {feedback}\n\n"
            if model_answer:
                s += f"✅ **Model answer:**\n{model_answer}"
        return s

    async def score_answer_with_llm(
        self, question: str, answer: str, keywords: list[str],
        provider, language: str = "vi"
    ) -> tuple[float, str, str]:
        kw_str = ", ".join(keywords[:8]) if keywords else "N/A"
        prompt_vi = (
            f"Chấm điểm câu trả lời phỏng vấn Java/DevOps sau.\n\n"
            f"**Câu hỏi:** {question}\n"
            f"**Câu trả lời của ứng viên:** {answer}\n"
            f"**Từ khoá kỳ vọng:** {kw_str}\n\n"
            f"Trả lời JSON (không giải thích thêm):\n"
            f'```json\n{{"score": 7.5, "feedback": "...", "model_answer": "..."}}\n```'
        )
        prompt_en = (
            f"Grade this Java/DevOps interview answer.\n\n"
            f"**Question:** {question}\n"
            f"**Candidate answer:** {answer}\n"
            f"**Expected keywords:** {kw_str}\n\n"
            f"Return JSON only:\n"
            f'```json\n{{"score": 7.5, "feedback": "...", "model_answer": "..."}}\n```'
        )
        prompt = prompt_vi if language == "vi" else prompt_en

        try:
            from .providers import OllamaProvider
            prov = OllamaProvider()
            messages = [
                {"role": "system", "content": "Bạn là chuyên gia phỏng vấn kỹ thuật. Chấm điểm chính xác và khách quan. Trả về JSON."},
                {"role": "user", "content": prompt},
            ]
            collected = []

            async def _noop(ev): pass

            result = await prov.run_step(messages, _noop)
            text = result["content"]
        except Exception as e:
            return 5.0, f"Không thể chấm tự động: {e}", ""

        return _parse_score_json(text)


def _parse_score_json(text: str) -> tuple[float, str, str]:
    m = re.search(r'\{.*?"score".*?\}', text, re.DOTALL)
    if not m:
        return 5.0, text[:200], ""
    try:
        obj = json.loads(m.group(0))
        score = float(obj.get("score", 5.0))
        score = max(0.0, min(10.0, score))
        feedback = str(obj.get("feedback", ""))
        model = str(obj.get("model_answer", ""))
        return score, feedback, model
    except Exception:
        return 5.0, text[:200], ""
