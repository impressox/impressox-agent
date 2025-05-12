# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Cài đặt các gói hệ thống cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy requirements và cài đặt dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn và thư mục config
COPY keyword_scraper.py ./

# Thiết lập biến môi trường (nếu cần)
ENV PYTHONUNBUFFERED=1

# Lệnh chạy script chính
CMD ["python", "keyword_scraper.py"] 