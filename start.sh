#!/usr/bin/env bash
# ShopDesk — script khởi động cho Linux / Mac
# Cách dùng: mở Terminal, cd vào thư mục shopdesk, chạy: ./start.sh
set -e

cd "$(dirname "$0")"

echo "=== ShopDesk ==="

# 1. Kiểm tra Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "LỖI: Chưa cài Python 3. Hãy cài Python 3.10 trở lên rồi chạy lại."
    echo "  - Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  - Mac: brew install python3 (hoặc tải tại https://www.python.org/downloads/)"
    exit 1
fi
echo "Python: $(python3 --version)"

# 2. Cài thư viện nếu thiếu Flask
if ! python3 -c "import flask" >/dev/null 2>&1; then
    echo "Đang cài thư viện cần thiết (Flask, requests)..."
    python3 -m pip install -r requirements.txt
fi

# 3. Chạy app
echo "Khởi động ShopDesk tại http://localhost:8000"
echo "Nhấn Ctrl+C để dừng."
python3 app.py
