# Java Core — Kiến thức nền tảng

## Collections Framework

### HashMap
HashMap lưu dữ liệu dạng key-value dùng cơ chế hashing. Bên trong là một mảng các bucket (Node[]). Khi put(key, value): tính hashCode() của key, áp dụng hàm hash nội bộ để phân tán đều, rồi dùng `(n-1) & hash` để tìm index bucket.

Collision xảy ra khi hai key khác nhau cho ra cùng index bucket. Java xử lý bằng separate chaining: các entry trong cùng bucket nối thành linked list. Từ Java 8, khi số entry trong một bucket vượt ngưỡng TREEIFY_THRESHOLD = 8 (và capacity >= 64), linked list chuyển thành red-black tree để tra cứu từ O(n) xuống O(log n).

Load factor mặc định 0.75: khi số entry vượt capacity * loadFactor, HashMap resize (rehash) gấp đôi capacity. Capacity luôn là lũy thừa của 2.

HashMap KHÔNG thread-safe. Dùng ConcurrentHashMap trong môi trường đa luồng — nó khóa theo từng segment/bucket thay vì khóa toàn bộ map.

### ArrayList vs LinkedList
ArrayList dùng mảng động: truy cập ngẫu nhiên O(1), nhưng thêm/xóa giữa list là O(n) do phải dịch phần tử. LinkedList dùng danh sách liên kết đôi: thêm/xóa đầu-cuối O(1), nhưng truy cập theo index O(n). Thực tế ArrayList hầu như luôn nhanh hơn do cache locality tốt hơn.

### HashSet, TreeSet, LinkedHashSet
HashSet không bảo đảm thứ tự, O(1) cho add/contains. TreeSet giữ thứ tự sắp xếp (red-black tree), O(log n). LinkedHashSet giữ thứ tự chèn.

## String
String là immutable (bất biến) — mọi thao tác nối chuỗi tạo ra object String mới. Lợi ích: thread-safe, có thể cache hashCode, dùng được làm key HashMap an toàn, và String pool tiết kiệm bộ nhớ.

String literal được lưu trong String Constant Pool. `new String("abc")` tạo object mới trên heap, không dùng pool. Dùng `.intern()` để đưa về pool.

Nối chuỗi trong vòng lặp nên dùng StringBuilder (mutable, không đồng bộ, nhanh). StringBuffer giống StringBuilder nhưng synchronized (thread-safe, chậm hơn).

## Exception Handling
- Checked Exception: kiểm tra lúc compile, bắt buộc catch hoặc khai báo throws (IOException, SQLException). Dùng cho lỗi có thể phục hồi.
- Unchecked Exception (RuntimeException): không bắt buộc xử lý (NullPointerException, IllegalArgumentException). Dùng cho lỗi lập trình.
- Error: lỗi nghiêm trọng của JVM (OutOfMemoryError, StackOverflowError), không nên bắt.

try-with-resources tự động đóng tài nguyên (AutoCloseable), tránh rò rỉ. finally luôn chạy trừ khi JVM thoát.

## equals() và hashCode()
Hợp đồng: nếu a.equals(b) thì a.hashCode() == b.hashCode(). Vi phạm sẽ làm HashMap/HashSet hoạt động sai. Khi override equals() phải override hashCode(). == so sánh tham chiếu, equals() so sánh giá trị logic.

## Generics
Generics cung cấp type safety lúc compile. Type erasure: thông tin generic bị xóa lúc runtime (List<String> và List<Integer> cùng là List). Wildcard: `? extends T` (covariant, đọc), `? super T` (contravariant, ghi) — nguyên tắc PECS: Producer Extends, Consumer Super.

## Java 8+ Features
- Lambda expression: biểu thức hàm ẩn danh, implement functional interface.
- Stream API: xử lý collection theo kiểu khai báo (map, filter, reduce, collect). Lazy evaluation, có thể parallel.
- Optional: tránh NullPointerException, biểu diễn giá trị có thể vắng mặt.
- Functional interface: interface có đúng một abstract method (@FunctionalInterface) — Function, Consumer, Supplier, Predicate.
- Default method trong interface: cho phép thêm method có body vào interface mà không phá vỡ class đã implement.

## abstract class vs interface
Abstract class: có thể có state (field), constructor, method có body và abstract; một class chỉ extends một abstract class. Interface: từ Java 8 có default/static method, nhưng không có state (chỉ constant); một class implements nhiều interface. Dùng interface cho "khả năng/hành vi", abstract class cho quan hệ "is-a" có chia sẻ code.
