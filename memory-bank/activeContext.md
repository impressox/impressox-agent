### 2025-05-08

- Đã cập nhật kiến trúc hệ thống: thêm backend service layer (tầng dịch vụ nghiệp vụ, truy xuất dữ liệu, tích hợp hệ thống ngoài, tách biệt với API layer).
- Đã cập nhật toàn bộ memory bank (projectbrief.md, productContext.md, systemPatterns.md, techContext.md) để phản ánh vai trò và vị trí của backend trong hệ thống.
- Các bước tiếp theo: chuẩn hóa giao tiếp giữa API và backend, bổ sung tài liệu/diagram kiến trúc, rà soát các worker/service tích hợp backend.

### 2025-05-06

- Đã thêm tool `summary_social` cho GENERAL_NODE, cho phép tóm tắt thông tin trên X/Twitter hoặc các truy vấn tương tự.
- Tool sử dụng API cấu hình trong `configs/api.yaml` (`summary_social.url`) và gọi qua hàm `call_api`.
- Đăng ký tool qua decorator `@register_tool(NodeName.GENERAL_NODE, "summary_social")`.
- Đã cập nhật cấu hình API, tạo file tool, và đăng ký tool vào hệ thống.
