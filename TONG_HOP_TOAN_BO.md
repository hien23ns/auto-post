# TỔNG HỢP TOÀN BỘ HỆ THỐNG: AI AUTO VIDEO PUBLISHER 24/7

> **Tài liệu tổng hợp đối chiếu toàn diện về luồng dữ liệu, chính sách API, an toàn vận hành và hướng dẫn tích hợp.**

---

## 1. BẢNG ĐỐI CHIẾU CÁC YÊU CẦU CỦA HỆ THỐNG

| Thành phần | Yêu cầu kỹ thuật | Giải pháp triển khai | Trạng thái |
|---|---|---|---|
| **1. Telegram & Make** | Chỉ nhận từ allowlist User IDs; lệnh /start, /help, /status, /queue, /history, /cancel, /retry. Single webhook consumer qua Make. Không truyền nhị phân qua Make. | Endpoint `/webhook/telegram` xác thực header `X-Automation-Secret`. Tự động download qua Telegram API getFile (<20MB) hoặc Presigned S3/R2 (>20MB). | Sẵn sàng triển khai |
| **2. AI Video Analysis** | Gemini API model video-capable cấu hình động (default `gemini-2.5-flash`). Phân tích hình ảnh, âm thanh, thoại, OCR, mốc thời gian, cảm xúc. Pydantic schema chặt chẽ. Evidence timestamped, không bịa đặt số liệu/tên riêng. | Module `gemini_service.py` với structured JSON output. Nếu thông tin không có timestamp chứng minh, AI tự gắn `uncertain=True` và chuyển sang `NEEDS_REVIEW`. | Sẵn sàng triển khai |
| **3. Content Generation** | 3 hook/tiêu đề, caption, hashtags, SEO, CTA cho 3 nền tảng (TikTok, Fanpage, Shorts). Không clickbait sai sự thật. Hỗ trợ user edit text trước khi đăng. Lưu lịch sử revision. | Module sinh nội dung đa kênh, lưu vào bảng `job_revisions`. Bot gửi inline button cho phép người dùng bấm "Sửa nội dung". | Sẵn sàng triển khai |
| **4. Thumbnail Studio** | FFmpeg phân tích keyframe nét, không frame đen/mờ. 3 thumbnail 9:16 safe-zone, chữ tiếng Việt chuẩn dấu Unicode, gradient tương phản cao. Tùy chọn 16:9. | Module `thumbnail_service.py` trích xuất 3 frame tốt nhất bằng FFmpeg scene change filter + Pillow render text safe-zone. | Sẵn sàng triển khai |
| **5. Publishers** | YouTube Data API v3 (resumable, private test). Facebook Fanpage Reels (Page Access Token, 3-phase upload). TikTok Content Posting API (Upload-to-Inbox an toàn, Direct Post khi đủ điều kiện & consent). Feature flags từng nền tảng. | 3 modules riêng biệt kế thừa `BasePublisher`. Trạng thái `SUBMITTED` -> poll -> `PUBLISHED`. Anti-double-post lock. | Sẵn sàng triển khai |
| **6. Automation 24/7** | FastAPI + PostgreSQL durable jobs + Worker heartbeat + Docker Compose + Caddy HTTPS. Restart sau crash. Giờ Việt Nam `Asia/Ho_Chi_Minh`. Cảnh báo Telegram. Dọn dẹp retention 7 ngày. | Docker Compose gồm web, worker, postgres, caddy. Worker heartbeat mỗi 30s. Script backup DB và cleanup media. | Sẵn sàng triển khai |
| **7. CI/CD & Security** | Private repo, `.env.example`, `.gitignore`, GitHub Actions pytest/lint, Docker deployment runbook, không log token. | GitHub Actions workflow, secret masking trong log, Caddy reverse proxy HTTPS. | Sẵn sàng triển khai |

---

## 2. LUỒNG DỮ LIỆU ĐẦY ĐỦ (END-TO-END DATA FLOW)

```mermaid
sequenceDiagram
    autonumber
    actor User as Telegram User
    participant TG as Telegram Bot API
    participant Make as Make.com Scenario
    participant API as FastAPI Backend (VPS)
    participant DB as PostgreSQL 16
    participant Worker as Background Worker
    participant Gemini as Google Gemini AI
    participant Studio as FFmpeg Studio
    participant Social as YouTube / Meta / TikTok

    User->>TG: Gửi video (mp4) kèm caption (nếu có)
    TG->>Make: Webhook update (Message / Video)
    Make->>API: POST /webhook/telegram (X-Automation-Secret)
    API->>API: Kiểm tra Allowlist & Secret
    API->>DB: Tạo Job (Status: PENDING)
    API-->>Make: 200 OK (Job Enqueued)
    Make-->>TG: Thông báo "Đã nhận video, đang xử lý..."

    Worker->>DB: Nhận job PENDING (Đặt lock: ANALYZING)
    Worker->>TG: Tải video gốc (getFile hoặc Storage)
    Worker->>Studio: Trích xuất 3 keyframe nét nhất (FFmpeg)
    Worker->>Gemini: Gửi video phân tích nội dung & bằng chứng
    Gemini-->>Worker: Trả về JSON Schema (Transcript, Evidence, Hooks, Captions)
    Worker->>Studio: Thiết kế 3 ảnh bìa 9:16 Safe-Zone
    Worker->>DB: Cập nhật Job (Status: REVIEW_READY)
    Worker->>TG: Gửi 3 Thumbnail + Bản nháp 3 nền tảng + Nút tương tác

    User->>TG: Bấm nút Duyệt / Sửa / Chọn bìa / Lên lịch
    TG->>Make: Webhook callback_query
    Make->>API: POST /webhook/telegram (X-Automation-Secret)
    API->>DB: Cập nhật lựa chọn & Revision
    API-->>Make: 200 OK

    alt Đăng ngay (Approve)
        Worker->>DB: Khóa Job (Status: PUBLISHING)
        Worker->>Social: Nộp video lên YouTube / Facebook / TikTok
        Social-->>Worker: Trả về Remote Video ID (Status: SUBMITTED)
        loop Kiểm tra xử lý từ xa
            Worker->>Social: Kiểm tra status (polling)
        end
        Worker->>DB: Cập nhật Job (Status: PUBLISHED)
        Worker->>TG: Gửi thông báo thành công kèm Link bài viết
    else Lên lịch (Schedule)
        Worker->>DB: Đặt Job (Status: SCHEDULED, scheduled_at_utc)
        Note over Worker: Worker tự động kích hoạt khi đến giờ hẹn
    end
```

---

## 3. DANH SÁCH BIẾN MÔI TRƯỜNG CHUẨN (.ENV)

| Biến môi trường | Ý nghĩa | Mặc định | Bắt buộc |
|---|---|---|---|
| `ENV` | Môi trường (`production` / `development`) | `development` | Có |
| `AUTOMATION_SECRET` | Khóa bí mật giao tiếp giữa Make.com và FastAPI | (Cần tạo chuỗi ngẫu nhiên >= 32 ký tự) | Có |
| `TELEGRAM_BOT_TOKEN` | Token Telegram Bot do @BotFather cấp | - | Có |
| `TELEGRAM_ALLOWED_USERS` | Danh sách User ID được phép tương tác (cách nhau bằng dấu phẩy) | - | Có |
| `DATABASE_URL` | Kết nối PostgreSQL database | `postgresql+asyncpg://app_user:app_pass@postgres:5432/auto_post_db` | Có |
| `GEMINI_API_KEY` | Khóa Google AI Studio để gọi Gemini API | - | Có |
| `GEMINI_MODEL` | Tên model Gemini phân tích video | `gemini-2.5-flash` | Không |
| `PREVIEW_ONLY` | Chế độ an toàn: chỉ tạo preview, không đăng lên mạng xã hội | `true` | Không |
| `YOUTUBE_CLIENT_ID` | OAuth Client ID Google Cloud | - | Khi bật YouTube |
| `YOUTUBE_CLIENT_SECRET` | OAuth Client Secret Google Cloud | - | Khi bật YouTube |
| `YOUTUBE_REFRESH_TOKEN` | OAuth Refresh Token tài khoản YouTube | - | Khi bật YouTube |
| `FACEBOOK_PAGE_ID` | ID của Facebook Fanpage đăng Reels | - | Khi bật Facebook |
| `FACEBOOK_PAGE_ACCESS_TOKEN`| Page Access Token dài hạn có quyền `pages_manage_posts` | - | Khi bật Facebook |
| `TIKTOK_CLIENT_KEY` | Client Key TikTok Developer App | - | Khi bật TikTok |
| `TIKTOK_CLIENT_SECRET` | Client Secret TikTok Developer App | - | Khi bật TikTok |
| `TIKTOK_ACCESS_TOKEN` | Access Token người dùng TikTok | - | Khi bật TikTok |
| `TIMEZONE` | Múi giờ hiển thị và tính toán | `Asia/Ho_Chi_Minh` | Không |
| `RETENTION_DAYS` | Số ngày lưu trữ video gốc trước khi tự động dọn dẹp | `7` | Không |
