# System Design — Nền tảng thiết kế hệ thống

## Quy trình tiếp cận bài toán
1. Làm rõ yêu cầu: functional (chức năng gì) và non-functional (scale, latency, availability).
2. Ước lượng (back-of-envelope): QPS, storage, bandwidth. Ví dụ 100M DAU, mỗi user 10 request/ngày → ~11.5k QPS trung bình, peak ~2-3 lần.
3. Định nghĩa API và data model.
4. Thiết kế high-level: các component, luồng dữ liệu.
5. Đi sâu component quan trọng, bàn trade-off.
6. Xử lý bottleneck, single point of failure, scale.

## Scaling
- Vertical scaling: nâng cấu hình một máy — đơn giản nhưng có trần và là SPOF.
- Horizontal scaling: thêm nhiều máy — khó hơn (cần stateless, load balancer) nhưng scale vô hạn.
- Load balancer: phân phối request (round-robin, least-connection, consistent hashing). Health check loại máy chết.
- Stateless service: không lưu state cục bộ, lưu session ở Redis/DB → scale ngang dễ.

## Database
- SQL (quan hệ): ACID, join mạnh, schema chặt. Dùng khi cần transaction, tính toàn vẹn (ngân hàng, đơn hàng).
- NoSQL: key-value (Redis, DynamoDB), document (MongoDB), column (Cassandra), graph (Neo4j). Scale ngang tốt, schema linh hoạt, dùng cho big data, high write.
- Replication: master-slave (read replica giảm tải đọc), master-master. Trade-off replication lag.
- Sharding: chia dữ liệu theo key (range, hash, geo) ra nhiều node. Thách thức: resharding, cross-shard query, hotspot.
- Indexing: tăng tốc đọc, chậm ghi. B-tree index cho range query.

## Caching
Cache giảm tải DB và latency. Chiến lược: cache-aside (app đọc cache, miss thì đọc DB rồi set cache — phổ biến nhất), write-through (ghi cache và DB đồng thời), write-back (ghi cache trước, DB sau — nhanh nhưng rủi ro mất dữ liệu). Eviction: LRU, LFU, TTL. Vấn đề: cache stampede (nhiều request cùng miss), giải quyết bằng lock hoặc stale-while-revalidate. CDN cache nội dung tĩnh gần user.

## CAP Theorem
Trong hệ phân tán, khi có network Partition, phải chọn giữa Consistency (mọi node thấy dữ liệu mới nhất) và Availability (luôn phản hồi). CP: ưu tiên nhất quán (ngân hàng). AP: ưu tiên sẵn sàng (mạng xã hội, chấp nhận eventual consistency). PACELC mở rộng: khi không partition, chọn giữa Latency và Consistency.

## Message Queue & Async
Kafka, RabbitMQ decouple producer-consumer, hấp thụ burst traffic, cho phép xử lý bất đồng bộ. Lợi ích: resilience (consumer chết không mất message), scale độc lập. Đảm bảo: at-least-once (có thể trùng → cần idempotent consumer), at-most-once, exactly-once (khó). Kafka giữ thứ tự trong partition, scale qua nhiều partition.

## Reliability Patterns
- Rate limiting: token bucket (cho phép burst), sliding window, fixed window. Bảo vệ hệ thống khỏi quá tải.
- Circuit breaker: khi downstream lỗi liên tục, mở circuit để fail fast, tránh cascade failure. Trạng thái: closed → open → half-open.
- Retry với exponential backoff + jitter: tránh thundering herd.
- Bulkhead: cô lập tài nguyên để lỗi một phần không kéo sập toàn bộ.
- Idempotency: thao tác lặp lại cho cùng kết quả, dùng idempotency key.

## Ví dụ: URL Shortener
Yêu cầu: tạo short URL, redirect, scale cao đọc nhiều. Sinh key: base62 encode từ counter/ID, hoặc hash URL lấy 7 ký tự. Lưu mapping trong DB + cache (đọc nhiều). Redirect dùng HTTP 301/302. Thêm analytics async qua queue. Dùng CDN và read replica để scale đọc.

## Ví dụ: Rate Limiter phân tán
Dùng Redis lưu counter theo user/IP. Token bucket: mỗi key có số token, nạp lại theo thời gian, mỗi request trừ một token. Dùng Lua script để atomic. Trả header X-RateLimit-Remaining. Sliding window log chính xác hơn nhưng tốn bộ nhớ.
