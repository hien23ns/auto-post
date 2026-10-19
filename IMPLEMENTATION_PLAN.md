# IMPLEMENTATION PLAN: AI AUTO VIDEO PUBLISHER 24/7

> **Lộ trình triển khai kỹ thuật từng bước (Phased Implementation Plan)**
> Đánh dấu chính xác hiện trạng, thiếu sót, rủi ro và các mốc kiểm thử thực tế.

---

## 1. BẢNG KIỂM TOÁN MÃ NGUỒN & API (AUDIT TABLE)

| Thành phần | Existing (Đã có) | Missing (Còn thiếu) | Risk (Rủi ro kỹ thuật / chính sách) | Proposed Fix (Giải pháp đề xuất) |
|---|---|---|---|---|
| **Repository Base** | Khởi tạo Git độc lập, cấu hình VS Code | Codebase `app/`, `tests/`, `compose.yaml`, `.env.example` | Mất cấu trúc module chuẩn, phân mảnh phụ thuộc | Tạo đầy đủ cấu trúc module FastAPI theo kiến trúc chuẩn sản xuất |
| **Telegram & Webhook** | Thư viện `httpx` trên máy | Webhook receiver, xác thực `X-Automation-Secret`, allowlist User ID, mapping Make payload | Bị spam request giả mạo, lộ webhook URL, Make payload không khớp schema | Bắt buộc middleware kiểm tra `X-Automation-Secret`, allowlist check trước khi tạo Job |
| **Video Ingestion (< 20MB)** | FFmpeg 8.0.1 có sẵn trên máy | Tự động tải file qua Telegram Bot API `getFile` | Telegram API rate limit (30 req/giây), file quá hạn 1 giờ | Lưu file vào thư mục `media/raw/`, kiểm tra hash MD5 chống trùng lặp |
| **Video Ingestion (> 20MB)** | Chưa có | Signed URL generator (S3/R2 compatible) hoặc Local Bot API Server config | Telegram Cloud Bot API từ chối tải file >20MB qua `getFile` | Thiết lập cơ chế signed S3/R2 upload URL + hướng dẫn Local Bot API Server |
| **AI Video Understanding** | Thư viện `google-genai` 2.11.0 có sẵn | Prompt video understanding, Pydantic strict schema, trích xuất evidence timestamps | Model bị ảo giác nội dung (hallucination), tên người, con số bịa đặt | Pydantic model bắt buộc `evidence_timestamps`; nếu không có mốc thời gian -> gắn cờ `uncertain` |
| **Content Generation** | Thư viện Python text handling | Bộ sinh nội dung riêng cho 3 nền tảng (TikTok, Fanpage, Shorts) | Spam hashtag, clickbait vi phạm chính sách cộng đồng | Bộ sinh theo tiêu chuẩn từng platform (Hook/Caption/Hashtag/CTA) có thể chỉnh sửa |
| **Thumbnail Studio** | FFmpeg 8.0.1 & Pillow 11.3.0 | Keyframe selector, 9:16 safe-zone overlay, Typography tiếng Việt 3 biến thể | Chữ bị che bởi UI của TikTok/Reels/Shorts, lỗi font ô vuông (tofu) | Tạo module Pillow Safe-Zone, tự động fallback font hệ thống Unicode (Arial, DejaVu) |
| **YouTube Publisher** | `google-auth` có sẵn | Module resumable upload `videos.insert`, kiểm tra trạng thái video processing | Quota YouTube Data API (10.000 units/ngày; upload tốn ~1600 units) | Resumable chunk upload; mặc định trạng thái `private` an toàn; lưu refresh token |
| **Facebook Fanpage Reels** | Chưa có | 3-phase upload (`start` -> `transfer` -> `finish`), kiểm tra quyền Page token | Dùng token cá nhân thay vì Page token -> lỗi 403; video sai tỷ lệ | Kiểm tra quyền Page Access Token (`pages_manage_posts`), chuẩn hóa video H264 9:16 |
| **TikTok Content Posting** | Chưa có | Video upload to Inbox fallback & Direct Post with consent metadata | Direct Post không được duyệt nếu app nội bộ chưa qua TikTok Partner Audit | Triển khai chế độ Upload to Inbox làm chuẩn an toàn, chỉ kích hoạt Direct Post khi có scope |
| **Durable Jobs & DB** | Thư viện `sqlalchemy` 2.1.4 | Mô hình Database PostgreSQL, job state lock, exponential backoff, worker loop | Worker restart làm mất trạng thái job hoặc đăng trùng bài (double post) | Lưu trạng thái vào PostgreSQL, dùng `locked_at` và `lock_version` chống race condition |
| **Deployment & 24/7** | Docker 29.5 & Docker Compose v5.1 | `compose.yaml`, Caddyfile HTTPS, health check, retention script, GitHub Actions | VPS hết dung lượng đĩa do lưu video quá hạn, database bị sập | Script dọn dẹp video sau 7 ngày, Docker healthcheck endpoint, backup DB định kỳ |

---

## 2. DANH SÁCH ĐIỂM KHÔNG THỂ KIỂM CHỨNG KHI THIẾU TOKEN

1. **Google Gemini API**: Không thể gọi AI thực tế nếu thiếu `GEMINI_API_KEY`.
   - *Cách giải quyết an toàn*: Cung cấp Mock Gemini Provider trả về dữ liệu mẫu thực tế kèm timestamp evidence khi chạy test hoặc khi `GEMINI_API_KEY` chưa có.
2. **Telegram Bot API**: Không thể nhận webhook thực tế nếu thiếu `TELEGRAM_BOT_TOKEN`.
   - *Cách giải quyết an toàn*: Tạo mock webhook client gửi payload Telegram chuẩn qua FastAPI endpoint để kiểm thử luồng nội bộ hoàn chỉnh.
3. **YouTube Data API v3**: Không thể upload lên kênh thật nếu thiếu `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
   - *Cách giải quyết an toàn*: Cung cấp chế độ `PREVIEW_ONLY=true` và Mock YouTube Publisher giả lập đầy đủ phản hồi của Google API.
4. **Meta Graph API**: Không thể tạo Reels trên Page thật nếu thiếu `FACEBOOK_PAGE_ID` và `FACEBOOK_PAGE_ACCESS_TOKEN`.
   - *Cách giải quyết an toàn*: Cung cấp Mock Facebook Publisher giả lập 3 phase (`start`, `upload`, `finish`).
5. **TikTok Content Posting API**: Không thể nộp video nếu thiếu `TIKTOK_ACCESS_TOKEN` và Scope kiểm duyệt.
   - *Cách giải quyết an toàn*: Cung cấp Mock TikTok Publisher và cơ chế Upload-to-Inbox an toàn.

---

## 3. LỘ TRÌNH THỰC HIỆN 6 GIAI ĐOẠN (6-PHASE ROADMAP)

### Giai đoạn 0: Kiểm toán & Thiết lập Nền tảng (Baseline & Core Foundation)
- [x] Tạo `ARCHITECTURE.md` và `IMPLEMENTATION_PLAN.md`.
- [x] Tạo tài liệu hướng dẫn bắt buộc: `README.md`, `TONG_HOP_TOAN_BO.md`, `QUICKSTART_VI.md`, `docs/make-com.md`, `SETUP_MAKE_FANPAGE.md`.
- [x] Tạo `.env.example`, `.gitignore`, `compose.yaml`, `Dockerfile`, `requirements.txt`.
- [x] Tạo khung kiến trúc `app/`: `config.py`, `database.py`, `models.py`, `schemas.py`, `main.py`.
- [x] Viết bộ tests kiểm tra schema, cấu hình và tính toàn vẹn (Giai đoạn 0 passed).

### Giai đoạn 1: Ổn định MVP Nhỏ (< 19MB, Gemini, 3 Thumbnail, Telegram Review)
- [ ] Xây dựng `app/services/telegram_service.py` (xử lý payload từ Make/Telegram, kiểm tra allowlist, gửi tin nhắn preview có nút inline keyboard).
- [ ] Xây dựng `app/services/gemini_service.py` (tích hợp Gemini video analysis với schema Pydantic, trích xuất bằng chứng timestamp, chế độ mock khi thiếu key).
- [ ] Xây dựng `app/services/ffmpeg_service.py` & `app/services/thumbnail_service.py` (trích xuất 3 keyframe nét, render chữ tiếng Việt 9:16 safe-zone, không vỡ layout).
- [ ] Chế độ `PREVIEW_ONLY`: Người dùng gửi video thật -> nhận được 3 ảnh bìa thiết kế và bản nháp nội dung 3 nền tảng trên Telegram mà không cần token mạng xã hội.
- [ ] Viết test tự động cho toàn bộ luồng Giai đoạn 1 và chạy kiểm thử.

### Giai đoạn 2: Ingestion Video Lớn (>20MB) & Video Normalization
- [ ] Hỗ trợ video lớn: cơ chế Presigned URL (S3/Cloudflare R2) và hướng dẫn Local Bot API Server.
- [ ] Chuẩn hóa video qua FFmpeg: Chuyển đổi định dạng về chuẩn tối ưu H264/AAC, fps 30/60, kiểm tra tỷ lệ khung hình 9:16.
- [ ] Viết tests cho module ingestion và normalization.

### Giai đoạn 3: Tương tác Telegram Nâng cao, Revision History & Chống Đăng Trùng
- [ ] Xử lý callback chỉnh sửa Hook/Caption/Hashtag trong Telegram.
- [ ] Quản lý lịch sử chỉnh sửa (`JobRevision`) để đối soát bản duyệt cuối cùng.
- [ ] Cơ chế khóa chống đăng trùng (`lock_version`, `status_lock`) khi người dùng ấn nút nhiều lần.
- [ ] Lên lịch đăng bài (chuyển đổi múi giờ `Asia/Ho_Chi_Minh` sang UTC và ngược lại).
- [ ] Viết tests cho revision history và anti-double-post lock.

### Giai đoạn 4: Bộ Publishers Mạng Xã Hội (YouTube, Facebook, TikTok)
- [ ] YouTube Publisher: Resumable chunk upload qua YouTube Data API v3, mặc định `privacyStatus='private'`, quản lý token refresh an toàn.
- [ ] Facebook Fanpage Publisher: Meta Graph API 3-phase Reels upload với Page Token và Page ID.
- [ ] TikTok Publisher: Upload-to-Inbox fallback và Direct Post có kiểm tra Consent, Privacy và Creator Info.
- [ ] Feature Flags bật/tắt từng nền tảng độc lập. Đánh dấu `BLOCKED_MISSING_CREDENTIALS` khi thiếu cấu hình.
- [ ] Viết tests mock API errors, quota exhaustion, network retry cho cả 3 publisher.

### Giai đoạn 5: Production Hardening, 24/7 SRE & CI/CD
- [ ] Cấu hình Caddy HTTPS, Rate Limiting, CORS, Security Headers.
- [ ] Worker Heartbeat, Auto-Recovery, Graceful Shutdown.
- [ ] Script backup PostgreSQL định kỳ và script dọn dẹp media cũ (`scripts/backup_db.sh`, `scripts/cleanup_media.sh`).
- [ ] GitHub Actions CI/CD pipeline (`.github/workflows/ci-cd.yml`).
- [ ] Hoàn thiện trọn bộ tài liệu vận hành và checklist sẵn sàng cho production.
