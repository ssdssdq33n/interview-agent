# Java Concurrency — Lập trình đa luồng

## Thread và lifecycle
Một Thread có các trạng thái: NEW, RUNNABLE, BLOCKED, WAITING, TIMED_WAITING, TERMINATED. Tạo thread bằng cách extends Thread hoặc implement Runnable (ưu tiên Runnable để tách logic khỏi cơ chế thread).

## synchronized
synchronized đảm bảo mutual exclusion và visibility. synchronized method khóa trên object (this) hoặc class (với static). synchronized block khóa trên object chỉ định, cho phép khóa fine-grained hơn — giảm vùng tranh chấp. Mỗi object có một monitor lock; chỉ một thread giữ monitor tại một thời điểm.

Nên dùng synchronized block thay vì method khi chỉ cần bảo vệ một phần nhỏ code, giúp tăng throughput.

## volatile
volatile đảm bảo visibility: mọi thread đọc giá trị mới nhất từ main memory, không cache cục bộ. Nó KHÔNG đảm bảo atomicity cho thao tác kép (như i++). Dùng volatile cho cờ trạng thái (boolean running) hoặc double-checked locking.

## Java Memory Model (JMM) và happens-before
JMM định nghĩa khi nào một thread thấy được thay đổi của thread khác. Quan hệ happens-before: nếu A happens-before B thì kết quả của A hiển thị với B. Các quy tắc: unlock happens-before lock sau đó; ghi volatile happens-before đọc volatile sau đó; Thread.start() happens-before mọi hành động trong thread; mọi hành động trong thread happens-before Thread.join() trả về.

## atomic và CAS
Các lớp java.util.concurrent.atomic (AtomicInteger, AtomicLong, AtomicReference) dùng CAS (Compare-And-Swap) — thao tác nguyên tử ở mức CPU, lock-free. CAS: so sánh giá trị hiện tại với giá trị kỳ vọng, nếu khớp thì cập nhật. Vấn đề ABA giải quyết bằng AtomicStampedReference.

## Lock nâng cao
ReentrantLock: linh hoạt hơn synchronized — hỗ trợ tryLock (timeout), lock interruptibly, fairness. Phải unlock trong finally. ReadWriteLock: cho phép nhiều reader đồng thời, chỉ một writer — tốt khi đọc nhiều ghi ít. StampedLock (Java 8): optimistic read nhanh hơn.

## ExecutorService và Thread Pool
Không nên tạo thread thủ công cho tác vụ ngắn. ExecutorService quản lý thread pool, tái sử dụng thread. Executors.newFixedThreadPool, newCachedThreadPool, newSingleThreadExecutor. Nên tự cấu hình ThreadPoolExecutor (corePoolSize, maxPoolSize, queue, rejection policy) để kiểm soát. submit() trả về Future để lấy kết quả.

## CompletableFuture
CompletableFuture hỗ trợ lập trình bất đồng bộ kiểu chaining: thenApply, thenCompose, thenCombine, exceptionally. Kết hợp nhiều tác vụ async mà không block thread.

## Vấn đề thường gặp
- Deadlock: hai thread chờ lock của nhau. Tránh bằng cách luôn acquire lock theo cùng thứ tự, dùng tryLock với timeout.
- Race condition: kết quả phụ thuộc thứ tự thực thi không xác định. Giải quyết bằng synchronization.
- Livelock: thread liên tục phản ứng với nhau mà không tiến triển.
- Starvation: thread không bao giờ được cấp tài nguyên (fairness giải quyết).

## Concurrent Collections
ConcurrentHashMap: thread-safe, khóa theo bucket (Java 8 dùng CAS + synchronized trên node), không khóa toàn map. CopyOnWriteArrayList: tốt khi đọc nhiều ghi hiếm. BlockingQueue (ArrayBlockingQueue, LinkedBlockingQueue): nền tảng producer-consumer, put/take tự block.
