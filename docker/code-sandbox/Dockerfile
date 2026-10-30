# Code sandbox — Alpine + JDK 21 (OpenJ9 for low memory)
# Chạy trong isolated Docker network, không có internet access
# Chỉ nhận code qua stdin, trả kết quả về stdout/stderr
FROM eclipse-temurin:21-jdk-alpine

# Tạo user không có quyền root
RUN addgroup -S sandbox && adduser -S sandbox -G sandbox

# Giới hạn tài nguyên: ulimits được set ở docker-compose
WORKDIR /sandbox

# Cài Maven wrapper support
RUN apk add --no-cache bash curl

# Script chạy code Java
COPY run.sh /usr/local/bin/run-code
RUN chmod +x /usr/local/bin/run-code && chown sandbox:sandbox /sandbox

USER sandbox

# Tmpfs mount point (set trong docker-compose)
VOLUME /tmp

ENTRYPOINT ["run-code"]
