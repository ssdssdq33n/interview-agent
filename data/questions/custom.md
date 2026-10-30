# Custom Q&A — Interview Agent

Thêm câu hỏi tùy chỉnh theo format dưới đây.
Agent sẽ ưu tiên hỏi những câu này dựa trên topic và level.

## Format

```yaml
- topic: "spring-boot"
  level: "mid"
  language: "vi"
  question: "Giải thích sự khác nhau giữa @Component, @Service, @Repository trong Spring?"
  expected_keywords: ["stereotype", "AOP", "exception translation", "component scan"]
  model_answer: |
    @Component là annotation chung để đánh dấu bean.
    @Service và @Repository là specialization của @Component.
    @Repository còn tích hợp PersistenceExceptionTranslationPostProcessor
    để convert database exception thành Spring DataAccessException.
  difficulty: 3  # 1-5
  follow_ups:
    - "Khi nào nên dùng @Repository thay vì @Component?"
```

## Câu hỏi mẫu

- topic: "java-core"
  level: "mid"
  language: "vi"
  question: "Giải thích HashMap hoạt động như thế nào? Khi nào xảy ra collision?"

- topic: "devops"
  level: "mid"  
  language: "vi"
  question: "Sự khác nhau giữa Docker image và container là gì?"

- topic: "spring-boot"
  level: "senior"
  language: "en"
  question: "How does Spring Boot autoconfiguration work under the hood?"
