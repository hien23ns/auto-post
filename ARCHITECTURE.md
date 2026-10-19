# ARCHITECTURE & SPECIFICATION: AI AUTO VIDEO PUBLISHER 24/7

> **Hệ thống tự động hóa xử lý và phân phối video đa nền tảng 24/7**
> Kiến trúc tiêu chuẩn sản xuất (Production-grade), bền bỉ, tuân thủ chính sách API và an toàn bảo mật.

---

## 1. TỔNG QUAN HỆ THỐNG (SYSTEM OVERVIEW)

```
 [Người dùng Telegram] (Allowlist User IDs)
          │
          │ (Gửi video / tương tác lệnh & inline buttons)
          ▼
 [Telegram Cloud Bot API]
          │
          │ (Single Webhook / Updates)
          ▼
   [Make.com Scenario] ──── (Header: X-Automation-Secret) ────┐
   (Webhook Receiver & Callback Router)                      │
                                                              ▼
                                                   [Caddy Reverse Proxy]
                                                   (HTTPS / SSL tự động)
                                                              │
                                                              ▼
                                                [FastAPI Backend Webhook API]
                                                (Rate Limit, Secret Auth, Job Dispatch)
                                                              │
                                                              ▼
                                                [PostgreSQL 16 Database]
                                                (Durable Jobs, Revisions, Audit Logs)
                                                              │
                                                              ▼
                                                 [Dedicated Background Worker]
                                                 (Heartbeat, Polling & State Lock)
                                                              │
         ┌────────────────────────────────────────────────────┴────────────────────────────────────────────────────┐
         │                                                    │                                                    │
         ▼                                                    ▼                                                    ▼
 [FFmpeg & Video Studio]                           [Gemini AI Engine]                                  [Social Publishers]
 - Probe aspect, duration, fps                     - Multimodal Video Understanding                    - YouTube Data API v3
 - Frame extraction & scoring                      - Structured Schema (Pydantic)                      - Meta Graph API (Reels)
 - 3x 9:16 Safe-Zone Thumbnails                    - Evidence Timestamps (No Hallucination)            - TikTok Content Posting API
 - H264/AAC Normalization                          - 3-Platform Tailored Content                       - Mock & Preview-Only Safe Mode
         │                                                    │                                                    │
         └────────────────────────────────────────────────────┼────────────────────────────────────────────────────┘
                                                              │
                                                              ▼
                                                [Telegram Notification & Approval]
                                                - Preview Card + 3 Covers + Content Revisions
                                                - Inline Keyboard: Sửa / Duyệt / Lên lịch / Hủy
                                                - Audit Consent & Anti-Double-Post Lock
```

---

## 2. NGUYÊN TẮC THIẾT KẾ & PHẠM VI (CORE PRINCIPLES)

1. **Durable Jobs (Không mất việc khi crash/restart)**:
   - Toàn bộ trạng thái công việc (Job State) được lưu trữ trong PostgreSQL (`pending`, `downloading`, `analyzing`, `review_ready`, `scheduled`, `publishing`, `published`, `failed`, `cancelled`).
   - Khóa phân tán lạc quan/bi quan (`locked_at`, `locked_by`, `lock_version`) ngăn chặn việc 2 worker cùng xử lý 1 video hoặc đăng trùng.
2. **Single Webhook qua Make.com**:
   - Telegram Bot API chỉ cho phép **1 URL webhook duy nhất**.
   - Make.com đóng vai trò Gateway tiếp nhận Webhook từ Telegram, lọc và forward payload sang FastAPI với secret bảo mật `X-Automation-Secret`.
   - Với video < 20MB: backend dùng `getFile` tải trực tiếp từ Telegram Bot API.
   - Với video > 20MB: bot phản hồi link signed upload (Cloudflare R2 / S3) hoặc sử dụng Telegram Local Bot API Server.
3. **AI Video Analysis Không Ảo Giác (Zero-Hallucination Evidence)**:
   - Sử dụng Google Gemini Multimodal Video API (`gemini-2.5-flash` / `gemini-1.5-flash` cấu hình qua biến môi trường).
   - Schema JSON Pydantic bắt buộc trường `evidence_timestamps` chứng minh sự kiện trong video. Nếu sự kiện không có bằng chứng, gắn cờ `uncertain=True` và yêu cầu người dùng duyệt tay.
4. **Thumbnail Studio Chuẩn Safe-Zone 9:16**:
   - Trích xuất keyframe nét qua FFmpeg (`select='gt(scene,0.3)'` kết hợp laplacian variance).
   - Thiết kế Typography tiếng Việt đúng dấu (Pillow/FreeType), tương phản cao, phủ bóng/gradient.
   - Tuân thủ Safe Zone 9:16 (tránh thanh công cụ TikTok/Reels bên phải và tiêu đề bên dưới).
5. **Publishers Tuân Thủ & Rõ Ràng Trạng Thái**:
   - `SUBMITTED != PUBLISHED`: Mọi API đăng bài đều trải qua pha nộp video và pha kiểm tra trạng thái remote (`processing` -> `complete`).
   - Mặc định kiểm thử ở chế độ **PREVIEW_ONLY** hoặc **PRIVATE/DRAFT**.
   - Không giả vờ thành công (No Fake Success). Nếu thiếu credentials hoặc scope, đánh dấu rõ ràng `BLOCKED_MISSING_CREDENTIALS`.
6. **Múi Giờ Chuẩn**:
   - Lưu trữ dữ liệu: chuẩn UTC trong database.
   - Giao tiếp người dùng: định dạng `Asia/Ho_Chi_Minh` (GMT+7).

---

## 3. CẤU TRÚC THƯ MỤC CHUẨN CỦA DỰ ÁN

```
auto-post/
├── .github/
│   └── workflows/
│       └── ci-cd.yml             # Lint, tests, type checks, build verification
├── app/
│   ├── __init__.py
│   ├── config.py                 # Pydantic Settings & Environment Variables
│   ├── database.py               # SQLAlchemy async/sync engine, sessionmaker
│   ├── models.py                 # Job, PlatformPost, Revision, AuditLog ORM models
│   ├── schemas.py                # Pydantic Schemas (API, Telegram, AI, Platform)
│   ├── main.py                   # FastAPI Application & Endpoints
│   ├── worker.py                 # Background Worker & Job Scheduler loop
│   ├── services/
│   │   ├── __init__.py
│   │   ├── telegram_service.py   # Telegram Bot API client & Make parser
│   │   ├── gemini_service.py     # Gemini Video Understanding & Schema Extractor
│   │   ├── ffmpeg_service.py     # Frame extraction, video normalize, probe
│   │   ├── thumbnail_service.py  # 9:16 Safe-zone typography & 3 cover variations
│   │   ├── storage_service.py    # Local disk & signed S3/R2 storage handlers
│   │   └── scheduler_service.py  # Time calculation (Asia/Ho_Chi_Minh <-> UTC)
│   └── publishers/
│       ├── __init__.py
│       ├── base.py               # Abstract Publisher Base Class & Result schema
│       ├── youtube_publisher.py  # YouTube Data API v3 (Resumable, Private)
│       ├── facebook_publisher.py # Meta Graph API Fanpage Reels (3-phase)
│       └── tiktok_publisher.py   # TikTok Content Posting API (Inbox fallback + Direct)
├── docs/
│   ├── make-com.md               # Make.com Scenario setup & Blueprint JSON
│   ├── telegram-bot.md           # Telegram BotFather commands & setup
│   └── api-compliance.md         # API limits, scopes, quotas & audit notes
├── tests/
│   ├── conftest.py               # Test fixtures, temp dirs, mock DB
│   ├── test_schemas.py           # Schema validations & strict JSON models
│   ├── test_gemini_service.py    # Gemini mock responses & evidence parsing
│   ├── test_thumbnail_service.py # Keyframe & safe-zone typography rendering
│   ├── test_publishers.py        # Social publisher state machines & error handling
│   ├── test_worker_durable.py    # Job locks, retries, and state transitions
│   └── test_api_endpoints.py     # FastAPI webhook authentication & payloads
├── scripts/
│   ├── backup_db.sh              # Postgres backup script
│   ├── restore_db.sh             # Postgres restore verification script
│   └── setup_vps.sh              # VPS Ubuntu LTS initialization script
├── Caddyfile                     # Caddy reverse proxy HTTPS configuration
├── compose.yaml                  # Production Docker Compose (FastAPI, Worker, Postgres, Caddy)
├── Dockerfile                    # Multi-stage Python 3.11 + FFmpeg image
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Testing & Linting dependencies
├── .env.example                  # Sanitized environment template
├── .gitignore                    # Excludes secrets, videos, dumps, cache
├── ARCHITECTURE.md               # File này: Tổng quan kiến trúc & thiết kế
├── IMPLEMENTATION_PLAN.md        # Kế hoạch triển khai qua 6 giai đoạn
├── QUICKSTART_VI.md              # Hướng dẫn khởi chạy nhanh cho kỹ sư
├── SETUP_MAKE_FANPAGE.md         # Hướng dẫn chi tiết Make.com & Meta Fanpage
└── TONG_HOP_TOAN_BO.md           # Bản đồ tính năng và đối chiếu toàn diện
```

---

## 4. CHI TIẾT CÁC PHÂN HỆ KỸ THUẬT

### 4.1. Telegram Bot & Make.com Integration
- **Allowlist User Authentication**: Kiểm tra `telegram_user_id` trong danh sách `TELEGRAM_ALLOWED_USERS`. Bất kỳ yêu cầu nào ngoài danh sách sẽ bị từ chối và ghi log cảnh báo bảo mật.
- **Webhook Security**: Header `X-Automation-Secret` bắt buộc phải khớp với `AUTOMATION_SECRET` đã định nghĩa.
- **Callback Routing**: Xử lý các action:
  - `edit_text`: Chỉnh sửa Hook/Caption/Hashtag trước khi xuất bản.
  - `select_cover`: Chọn 1 trong 3 thumbnail hoặc giữ frame mặc định.
  - `toggle_platform`: Bật/tắt đăng lên TikTok, Facebook Reels, hoặc YouTube Shorts.
  - `set_schedule`: Lên lịch đăng (UTC lưu vào DB, hiển thị giờ VN).
  - `approve_publish`: Kích hoạt đăng bài ngay.
  - `cancel`: Hủy bỏ job.

### 4.2. AI Video Analysis & Content Engine (Gemini)
- Sử dụng Google GenAI SDK hiện hành, hỗ trợ nạp video qua URI hoặc File API.
- Prompt kèm Schema bắt buộc trả về:
  1. `visual_summary`: Mô tả hình ảnh chi tiết theo thời gian.
  2. `audio_transcript`: Lời thoại và âm thanh nền.
  3. `ocr_text`: Chữ viết xuất hiện trên màn hình.
  4. `evidence_log`: Mảng `[{timestamp: "00:03", description: "...", confirmed: true}]`.
  5. `platforms`: Cấu trúc riêng cho YouTube Shorts, Facebook Reels, TikTok:
     - 3 tùy chọn Hook/Tiêu đề.
     - Caption đầy đủ theo phong cách nền tảng.
     - Danh sách Hashtags có chọn lọc (5-7 tags tối ưu, không spam).
     - Call To Action (CTA) tự nhiên.

### 4.3. FFmpeg & Thumbnail Typography Studio
- **Trích xuất Keyframe**: Tìm 3-5 frame tiêu biểu thông qua bộ lọc scene change và độ sắc nét.
- **Safe Zone 9:16**:
  - Chiều rộng 1080px, chiều cao 1920px.
  - Vùng an toàn hiển thị chữ: Top margin >= 200px (tránh nút Back/Search), Bottom margin >= 420px (tránh tên kênh, caption và thanh tiến trình), Right margin >= 140px (tránh nút Like, Comment, Share).
  - Phông chữ tiếng Việt: Tự động dùng phông Unicode (DejaVu Sans / Arial / Segoe UI), kiểm tra dấu đầy đủ không bị lỗi ô vuông (`tofu`).

### 4.4. Social Media Publishers
| Nền tảng | API chuẩn | Cơ chế Upload | Quy định Thumbnail | Trạng thái & Rủi ro |
|---|---|---|---|---|
| **YouTube Shorts** | YouTube Data API v3 (`videos.insert`) | Resumable Upload (chunked) | Shorts thường lấy frame từ video; API thumbnail có thể bị ghi đè bởi app di động | Cần OAuth 2.0 Refresh Token. Mặc định publish ở chế độ `private` để test. |
| **Facebook Fanpage** | Meta Graph API (`/{page_id}/video_reels`) | 3 bước: `start` -> `upload` binary -> `finish` | Phải chọn frame timestamp hoặc upload thumbnail tương thích | Cần Page Access Token có quyền `pages_manage_posts`. Không dùng User Profile token. |
| **TikTok** | TikTok Content Posting API v2 | Direct Post (`video.publish`) hoặc Upload to Inbox (`video.upload`) | Timestamp cover frame | Direct Post yêu cầu TikTok App Audit. Nếu chưa audit, fallback sang Upload to Inbox hoặc thông báo `BLOCKED_AUDIT_REQUIRED`. |

---

## 5. BẢO MẬT VÀ ĐỘ TIN CẬY 24/7 (SRE & SECURITY)
- **Rate Limiting**: Giới hạn số lượng request nạp video từ mỗi user và webhook IP.
- **SSRF & File Validation**: Kiểm tra MIME type thật của file bằng binary sniffing (magic bytes), không chỉ dựa vào phần mở rộng `.mp4`.
- **Worker Heartbeat**: Worker cập nhật timestamp `last_heartbeat` vào database mỗi 30 giây. Endpoint `/health` trả về `503 Service Unavailable` nếu worker bị treo quá 90 giây.
- **Auto Data Retention**: Video gốc và thumbnail được xóa sau `RETENTION_DAYS` (mặc định 7 ngày) sau khi đã xuất bản thành công để tiết kiệm dung lượng ổ cứng VPS.
