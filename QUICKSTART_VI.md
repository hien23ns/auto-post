# HƯỚNG DẪN KHỞI CHẠY NHANH: AI AUTO VIDEO PUBLISHER 24/7

> **Tài liệu hướng dẫn triển khai thực tế trên môi trường cục bộ (Local) và máy chủ VPS Ubuntu LTS.**

---

## 🚀 1. YÊU CẦU TIỀN ĐỀ (PREREQUISITES)

- **Python**: 3.11 trở lên.
- **FFmpeg**: 6.0 trở lên (hỗ trợ libx264, libmp3lame, libvpx, libass).
- **Docker & Docker Compose**: v2.20 trở lên.
- **Tài khoản**:
  - Telegram Bot (tạo qua [@BotFather](https://t.me/Botfather)).
  - Make.com (gói Core hoặc Pro).
  - Google AI Studio (lấy Gemini API Key).
  - (Tùy chọn cho pha xuất bản): Google Cloud Console (YouTube API), Meta for Developers (Page Access Token), TikTok Developer Portal.

---

## 🛠️ 2. CHẠY TRÊN MÁY LOCAL (LOCAL DEVELOPMENT)

### Bước 1: Chuẩn bị thư mục và biến môi trường
```bash
# Di chuyển vào thư mục dự án
cd auto-post

# Tạo file cấu hình từ template mẫu
cp .env.example .env
```

Mở `.env` và điền tối thiểu các biến sau cho chế độ chạy thử nghiệm an toàn:
```env
ENV=development
AUTOMATION_SECRET=my-super-secret-automation-key-12345
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
TELEGRAM_ALLOWED_USERS=123456789
GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere
PREVIEW_ONLY=true
DATABASE_URL=sqlite+aiosqlite:///./test_auto_post.db
```

### Bước 2: Cài đặt thư viện Python
```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

### Bước 3: Chạy kiểm thử tự động
```bash
pytest -v
```

### Bước 4: Khởi chạy FastAPI Backend
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Bước 5: Khởi chạy Background Worker
Mở một cửa sổ terminal mới:
```bash
python -m app.worker
```

---

## 🌐 3. TRIỂN KHAI TRÊN VPS DOCKER (PRODUCTION 24/7)

### Bước 1: Kết nối VPS Ubuntu LTS và cài đặt Docker
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git ufw ffmpeg

# Cài đặt Docker engine chính thức
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### Bước 2: Mở Firewall (UFW)
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (Caddy cert challenge)
sudo ufw allow 443/tcp   # HTTPS (Caddy)
sudo ufw enable
```

### Bước 3: Clone Code và Thiết lập .env
```bash
git clone <your-private-repo-url> /opt/auto-post
cd /opt/auto-post

cp .env.example .env
nano .env # Điền token chính thức, DATABASE_URL trỏ về postgres container
```

### Bước 4: Khởi động toàn bộ cụm dịch vụ
```bash
docker compose up -d --build
```

Kiểm tra trạng thái các container:
```bash
docker compose ps
docker compose logs -f web worker
```

---

## 🩺 4. KIỂM TRA SỨC KHỎE DỊCH VỤ (HEALTH CHECK)

Truy vấn endpoint kiểm tra trạng thái hoạt động:
```bash
curl -i https://your-domain.com/health
```

Kết quả phản hồi mong đợi:
```json
{
  "status": "healthy",
  "database": "connected",
  "worker_heartbeat": "active",
  "uptime_seconds": 3600,
  "timezone": "Asia/Ho_Chi_Minh"
}
```
Nếu worker bị dừng quá 90 giây hoặc Database mất kết nối, endpoint sẽ trả về HTTP `503 Service Unavailable`.
