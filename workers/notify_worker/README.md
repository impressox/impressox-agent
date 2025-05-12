# Notify Worker

Worker này gửi thông báo Telegram định kỳ 30 phút dựa trên dữ liệu từ API và quản lý danh sách user nhận notify qua Redis/MongoDB.

## Cài đặt

1. Cài đặt Python >= 3.9
2. Cài đặt thư viện:
```bash
pip install -r requirements.txt
```
3. Tạo file `.env` với các biến:
```
TELEGRAM_BOT_TOKEN=xxxx
REDIS_URL=redis://localhost:6379/0
MONGO_URI=mongodb://localhost:27017
```

## Chạy worker
```bash
python main.py
```

## Cấu trúc module
- `main.py`: Khởi động scheduler và redis pubsub listener
- `scheduler.py`: Lên lịch gửi notify mỗi 30 phút
- `data_fetcher.py`: Gọi API lấy dữ liệu cảnh báo
- `telegram_notifier.py`: Format và gửi message Telegram
- `store.py`: Quản lý active_users trên Redis/MongoDB
- `redis_listener.py`: Lắng nghe kênh notify_control để cập nhật trạng thái user

## Luồng hoạt động
- Định kỳ 30 phút, worker gọi 2 API lấy alert/airdrop, format và gửi cho tất cả user trong set `active_users` (Redis)
- Khi nhận message từ kênh Redis `notify_control`, worker cập nhật trạng thái user (bật/tắt notify) vào Redis và MongoDB
- Một bot Telegram khác sẽ publish message lên kênh này khi user gửi `/on` hoặc `/off` 