# Hướng dẫn nạp Knowledge Base

## Cách nạp dữ liệu

Thư mục này chứa tài liệu kỹ thuật để Interview Agent học.
Chạy lệnh sau sau khi server đã khởi động (Phase 2):

```bash
python -m backend.ingest --source knowledge/
```

## Cấu trúc thư mục

```
data/
├── knowledge/          # Tài liệu kỹ thuật (Java, DevOps, Spring...)
│   ├── java/           # Java core, collections, concurrency
│   ├── spring/         # Spring Boot, Spring Cloud
│   ├── devops/         # Docker, K8s, CI/CD
│   └── system-design/  # Distributed systems, architecture
├── cv/                 # File CV PDF của bạn (đặt tên cv.pdf)
├── questions/          # Câu hỏi custom
└── memory/             # Bộ nhớ agent (tự động tạo)
```

## Nguồn dữ liệu đề xuất (Phase 2)

- **Java**: Baeldung articles, Java docs, Effective Java
- **Spring**: Spring docs, Petclinic source code
- **DevOps**: Docker docs, K8s docs, GitLab CI examples
- **System Design**: Grokking the System Design, ByteByteGo
- **Behavioral**: STAR method guide

Xem thêm: `backend/ingest.py` (sẽ có ở Phase 2)
