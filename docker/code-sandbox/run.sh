#!/bin/bash
# Nhận code Java qua stdin, compile và chạy, trả kết quả (timeout 15s)
set -euo pipefail

CODE_FILE="/tmp/Main.java"
CLASS_DIR="/tmp/classes"

mkdir -p "$CLASS_DIR"
cat > "$CODE_FILE"

# Compile
if ! timeout 10 javac -d "$CLASS_DIR" "$CODE_FILE" 2>&1; then
    exit 1
fi

# Chạy với giới hạn bộ nhớ và thời gian
timeout 15 java \
    -cp "$CLASS_DIR" \
    -Xmx128m \
    -Xss512k \
    -XX:+UseSerialGC \
    Main 2>&1
