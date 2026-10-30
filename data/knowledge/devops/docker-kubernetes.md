# DevOps — Docker, Kubernetes, CI/CD

## Docker cơ bản
Image là template bất biến (read-only), gồm nhiều layer xếp chồng. Container là instance đang chạy của image, có thêm writable layer trên cùng. Mỗi lệnh trong Dockerfile (RUN, COPY, ADD) tạo một layer — layer được cache, giúp build nhanh khi không đổi.

ENTRYPOINT định nghĩa lệnh chính không dễ override; CMD cung cấp tham số mặc định, dễ override khi `docker run`. Kết hợp: ENTRYPOINT ["java","-jar","app.jar"] + CMD ["--spring.profiles.active=prod"].

## Dockerfile tối ưu cho Java
Multi-stage build: stage build dùng maven/JDK để tạo jar, stage runtime dùng JRE nhỏ (eclipse-temurin:21-jre-alpine) chỉ copy jar. Kết quả image nhỏ hơn nhiều, ít lỗ hổng bảo mật.

Tối ưu layer cache: copy pom.xml và chạy `mvn dependency:go-offline` TRƯỚC khi copy source — dependency chỉ tải lại khi pom đổi. Dùng .dockerignore loại bỏ target/, .git. Chạy bằng user non-root để bảo mật.

## Kubernetes — các đối tượng cốt lõi
- Pod: đơn vị nhỏ nhất, chứa một hoặc nhiều container chia sẻ network/storage. Pod là ephemeral.
- ReplicaSet: đảm bảo số lượng pod replica mong muốn.
- Deployment: quản lý ReplicaSet, hỗ trợ rolling update và rollback. Đối tượng thường dùng nhất cho stateless app.
- Service: địa chỉ ổn định cho tập pod (pod IP thay đổi). ClusterIP (nội bộ), NodePort (mở port trên node), LoadBalancer (cloud LB).
- Ingress: route HTTP/HTTPS từ ngoài vào Service theo host/path, kèm TLS termination.
- ConfigMap / Secret: tách cấu hình và thông tin nhạy cảm khỏi image.
- StatefulSet: cho app có state (database), pod có identity ổn định và persistent volume.

## Health Probes
- Liveness probe: container còn sống không — fail thì kubelet restart. Dùng để phục hồi deadlock.
- Readiness probe: pod sẵn sàng nhận traffic chưa — fail thì bị loại khỏi Service endpoints (không restart). Dùng khi app cần warmup.
- Startup probe: cho app khởi động chậm, tạm hoãn liveness/readiness cho đến khi app lên.

Lỗi thường gặp: liveness quá nhạy gây restart loop; thiếu readiness khiến traffic vào pod chưa sẵn sàng.

## Resource management
requests: tài nguyên tối thiểu bảo đảm (dùng để scheduling). limits: trần tối đa. Vượt memory limit → OOMKilled; vượt CPU limit → throttle. QoS class: Guaranteed (requests=limits), Burstable, BestEffort. HorizontalPodAutoscaler (HPA) scale số pod theo CPU/memory/custom metric.

## CI/CD Pipeline
Các stage điển hình: checkout → build → unit test → static analysis (SonarQube) → build image → push registry → deploy staging → integration test → deploy production.

Tối ưu build time: cache dependency (Maven local repo, Docker layer), chạy test song song, chỉ build module thay đổi (monorepo). Dùng artifact versioning rõ ràng. Blue-green hoặc canary deployment giảm rủi ro khi release.

GitOps (ArgoCD, Flux): trạng thái mong muốn mô tả trong Git, tool tự đồng bộ cluster về trạng thái đó — audit được, dễ rollback.

## 12-Factor App (liên quan DevOps)
Config qua environment variable, log ra stdout (không ghi file), stateless process, port binding, dev/prod parity. Giúp app chạy tốt trong container và scale ngang.

## Observability
Ba trụ cột: Metrics (Prometheus + Grafana), Logs (ELK/Loki), Traces (Jaeger/Tempo, distributed tracing qua trace ID). Correlation ID xuyên suốt request giúp debug microservices. Alerting dựa trên SLO/SLI.
