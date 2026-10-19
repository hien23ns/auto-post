# AI AUTO VIDEO PUBLISHER 24/7 🚀

> **Hệ thống tự động hóa phân tích video và phân phối đa nền tảng 24/7 dành riêng cho YouTube Shorts, Facebook Fanpage Reels và TikTok.**
> Thiết kế chuẩn Production: FastAPI + PostgreSQL Durable Jobs + Google Gemini AI + FFmpeg Video Studio + Make.com Webhook Gateway + Docker/Caddy.

---

## 🌟 TÍNH NĂNG NỔI BẬT

1. **Telegram Bot & Make.com Hub**:
   - Nhận video trực tiếp từ Telegram thông qua Webhook Make.com an toàn (`X-Automation-Secret`).
   - Kiểm tra User ID Allowlist chặt chẽ, từ chối mọi truy cập trái phép.
   - Hỗ trợ video < 20MB tải trực tiếp qua Telegram Bot API và cơ chế Signed R2/S3 / Local Bot API cho video dung lượng lớn.
2. **AI Video Analysis Không Ảo Giác (Gemini Multimodal)**:
   - Phân tích hình ảnh, âm thanh, lời thoại và chữ xuất hiện trong video.
   - Trích xuất bằng chứng theo mốc thời gian (`evidence_timestamps`), không tự bịa đặt chi tiết, số liệu hay tên riêng.
3. **Nội dung Đa Nền Tảng Tùy Biến**:
   - Tự động sinh nội dung phù hợp đặc thù từng nền tảng:
     - **YouTube Shorts**: Tiêu đề tối ưu SEO, mô tả súc tích kèm `#Shorts`.
     - **Facebook Fanpage Reels**: Caption thu hút, CTA hướng hành động cho cộng đồng.
     - **TikTok**: Hook 3 giây đầu mạnh mẽ, trào lưu hashtag thịnh hành.
   - 3 lựa chọn Hook/Tiêu đề và hỗ trợ người dùng chỉnh sửa trực tiếp trên Telegram trước khi đăng.
4. **Thumbnail Studio Chuẩn Safe-Zone 9:16**:
   - Trích xuất 3 keyframe nét nhất từ video thật (FFmpeg scene change & sharpness scoring).
   - Thiết kế Typography tiếng Việt chuẩn Unicode, phủ bóng/gradient tương phản cao.
   - Canh lề chuẩn Safe Zone 9:16, không bị che khuất bởi giao diện nút bấm của TikTok/Reels.
5. **Bộ Publishers Mạng Xã Hội Chính Thức**:
   - **YouTube Data API v3**: Resumable upload, mặc định trạng thái `private` khi thử nghiệm.
   - **Facebook Fanpage Meta Graph API**: Quy trình 3 bước (Start -> Upload -> Finish) sử dụng Page Access Token.
   - **TikTok Content Posting API**: Chế độ Upload to Inbox chuẩn quy định, chỉ Direct Post khi đã qua kiểm duyệt ứng dụng.
   - Ghi nhận trạng thái rõ ràng: `SUBMITTED != PUBLISHED`, kiểm tra xử lý từ xa trước khi hoàn tất.
6. **Vận Hành 24/7 Bền Bỉ**:
   - Hàng đợi bền bỉ (Durable Jobs) trên PostgreSQL, không mất dữ liệu khi worker restart hoặc VPS reboot.
   - Khóa chống đăng trùng lặp (`lock_version`).
   - Múi giờ hiển thị chuẩn Việt Nam (`Asia/Ho_Chi_Minh`), lưu trữ UTC trong database.
   - Giám sát sức khỏe hệ thống (Health Check) kết hợp Worker Heartbeat.

---

## 🏗️ KIẾN TRÚC HỆ THỐNG

Xem tài liệu chi tiết tại:
- [ARCHITECTURE.md](file:///c:/Users/Lenovo/Downloads/auto-post/ARCHITECTURE.md) - Kiến trúc chi tiết và đặc tả kỹ thuật.
- [IMPLEMENTATION_PLAN.md](file:///c:/Users/Lenovo/Downloads/auto-post/IMPLEMENTATION_PLAN.md) - Kế hoạch triển khai qua 6 giai đoạn và bảng kiểm toán.
- [QUICKSTART_VI.md](file:///c:/Users/Lenovo/Downloads/auto-post/QUICKSTART_VI.md) - Hướng dẫn khởi chạy nhanh.
- [TONG_HOP_TOAN_BO.md](file:///c:/Users/Lenovo/Downloads/auto-post/TONG_HOP_TOAN_BO.md) - Bản đồ tính năng và checklist tổng hợp.

---

## ⚡ CÀI ĐẶT NHANH (QUICK START)

### 1. Chuẩn bị môi trường
```bash
# Clone repository (Private repo)
git clone <repo-url> auto-post
cd auto-post

# Cấu hình biến môi trường
cp .env.example .env
# Chỉnh sửa các giá trị bí mật trong .env
```

### 2. Khởi chạy bằng Docker Compose
```bash
docker compose up -d --build
```

### 3. Kiểm tra trạng thái
```bash
curl http://localhost:8001/health
```

---

## 🔒 AN TOÀN VÀ BẢO MẬT
- **Không bao giờ commit file `.env` hoặc token bí mật** lên Git.
- Mọi Webhook gọi từ Make.com đều bắt buộc có header `X-Automation-Secret`.
- Chỉ người dùng trong `TELEGRAM_ALLOWED_USERS` mới có quyền kích hoạt hệ thống.
- Cơ chế tự động dọn dẹp file tạm và video gốc sau 7 ngày để bảo vệ dữ liệu và giải phóng bộ nhớ.

---

## 📄 GIẤY PHÉP
Dự án nội bộ được bảo vệ bản quyền. Không công khai mã nguồn hoặc phân phối khi chưa có sự đồng ý.
