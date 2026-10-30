# Microservices — Kiến trúc dịch vụ nhỏ

## Monolith vs Microservices
Monolith: một codebase, deploy một khối — đơn giản lúc đầu, dễ phát triển nhanh, nhưng khó scale từng phần và khó maintain khi lớn. Microservices: tách thành nhiều service độc lập theo bounded context — scale độc lập, deploy độc lập, team tự chủ, nhưng phức tạp về vận hành, network, data consistency. Nên bắt đầu monolith, tách khi thực sự cần.

## Giao tiếp giữa service
- Synchronous (REST, gRPC): đơn giản, dễ debug, nhưng tạo coupling thời gian (temporal coupling) — caller chờ callee. gRPC nhanh hơn REST nhờ HTTP/2 và protobuf.
- Asynchronous (message queue, event): decoupling, resilience, nhưng khó theo dõi luồng, eventual consistency. Dùng khi không cần phản hồi tức thì.

Trade-off: REST đồng bộ phù hợp query cần kết quả ngay; messaging phù hợp command/event, chịu tải burst, và fire-and-forget.

## Distributed Transaction
Không dùng được 2PC (two-phase commit) trên quy mô lớn vì blocking và SPOF ở coordinator. Thay vào:
- Saga pattern: chuỗi local transaction, mỗi bước có compensating action để rollback. Choreography (các service phản ứng với event, phi tập trung) hoặc Orchestration (một orchestrator điều phối, dễ theo dõi hơn).
- Outbox pattern: ghi event vào bảng outbox cùng transaction với business data, một process/CDC publish ra broker — tránh dual-write mất đồng bộ.
- Eventual consistency: chấp nhận dữ liệu nhất quán sau một khoảng thời gian.

## Resilience
- Circuit breaker (Resilience4j): closed (bình thường) → open (lỗi vượt ngưỡng, fail fast) → half-open (thử lại). Tránh cascade failure.
- Retry + exponential backoff + jitter: tránh làm quá tải service đang hồi phục.
- Timeout: luôn đặt timeout cho call ngoài, tránh treo thread.
- Bulkhead: cô lập thread pool/connection cho từng dependency.
- Fallback: trả giá trị mặc định/cache khi service lỗi.

## Service Discovery & API Gateway
Service discovery (Eureka, Consul, k8s Service): service tự đăng ký, client tìm được địa chỉ động. API Gateway (Spring Cloud Gateway, Kong): điểm vào duy nhất, xử lý routing, authentication, rate limiting, aggregation — ẩn cấu trúc nội bộ khỏi client.

## Data Management
Mỗi service sở hữu database riêng (database per service) — không chia sẻ DB để tránh coupling. Query xuyên service: API composition (gọi nhiều service rồi ghép) hoặc CQRS (tách model đọc/ghi, duy trì read model qua event). Cẩn thận N+1 call giữa service.

## Observability trong microservices
Distributed tracing (OpenTelemetry, Jaeger): trace ID xuyên suốt request qua nhiều service giúp tìm bottleneck. Centralized logging với correlation ID. Metrics per service. Đây là điều kiện bắt buộc để vận hành microservices.

## Idempotency
Do message có thể giao at-least-once, consumer phải idempotent: xử lý cùng message nhiều lần cho cùng kết quả. Dùng idempotency key, kiểm tra đã xử lý chưa trước khi thực hiện side effect.
