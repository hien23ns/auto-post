# HƯỚNG DẪN CHẠY HỆ THỐNG 24/7 TRÊN MAKE.COM (CHƯA CẦN THUÊ VPS)

> **Dành riêng cho bạn: Hướng dẫn giải quyết lỗi truy cập trình duyệt, thiết lập kịch bản Make.com chạy độc lập 24/7 trên Cloud mà không cần tốn tiền thuê VPS hay cần mở máy tính.**

---

## 🔍 1. GIẢI THÍCH LỖI TRONG ẢNH CHỤP MÀN HÌNH CỦA BẠN

Trong hình ảnh bạn gửi:
```
http://0.0.0.0:8001/
This site can’t be reached - ERR_ADDRESS_INVALID
```

### Tại sao lại bị lỗi này?
1. **`0.0.0.0` là địa chỉ lắng nghe nội bộ (Bind Address)** của server để chấp nhận kết nối từ mọi card mạng. Tuy nhiên, các trình duyệt web (như Google Chrome, Cốc Cốc, Edge) trên hệ điều hành Windows **không cho phép người dùng gõ `0.0.0.0` vào thanh địa chỉ** và sẽ báo ngay lỗi `ERR_ADDRESS_INVALID`.
   - 👉 **Địa chỉ đúng để mở trên trình duyệt của bạn là:**
     `http://localhost:8001` hoặc `http://127.0.0.1:8001`
2. **Tại sao Make.com không thể gọi vào `localhost:8001`?**
   - Make.com là một dịch vụ chạy trên đám mây (Cloud) tại Mỹ/Châu Âu.
   - `localhost` chỉ là máy tính cá nhân trong phòng của bạn, mạng Internet công cộng và Make.com không thể nhìn thấy máy tính của bạn nếu bạn chưa thuê VPS hoặc chưa mở cổng công khai (Public HTTPS URL).

---

## 🌟 2. GIẢI PHÁP CHẠY 24/7 TRÊN MAKE.COM NGAY BÂY GIỜ (100% MIỄN PHÍ - CHƯA CẦN THUÊ VPS)

Bạn hoàn toàn có thể chạy hệ thống **tự động phân tích video bằng Gemini và đăng lên Facebook Fanpage Reels / YouTube 24/7 ngay trên Make.com** mà không cần mở máy tính cá nhân và không cần thuê VPS!

Chúng tôi đã chuẩn bị sẵn cho bạn **File Kịch bản Blueprint mẫu chuẩn Make.com**:
📁 [docs/make_standalone_blueprint.json](file:///c:/Users/Lenovo/Downloads/auto-post/docs/make_standalone_blueprint.json)

---

### BƯỚC 1: IMPORT BLUEPRINT VÀO MAKE.COM
1. Đăng nhập vào tài khoản của bạn trên [Make.com](https://www.make.com/).
2. Nhấn nút **Create a new scenario** ở góc phải trên.
3. Ở thanh công cụ dưới đáy màn hình, nhấn vào biểu tượng **"..." (More options)** $\rightarrow$ Chọn **Import Blueprint**.
4. Chọn tệp [`docs/make_standalone_blueprint.json`](file:///c:/Users/Lenovo/Downloads/auto-post/docs/make_standalone_blueprint.json) từ thư mục dự án của bạn.
5. Toàn bộ kịch bản tự động hóa gồm Telegram, Gemini AI và Facebook Fanpage sẽ lập tức xuất hiện trực quan trên màn hình!

---

### BƯỚC 2: KẾT NỐI TELEGRAM BOT (MODULE 1 & 6)
1. Nhấn vào Module **1. Telegram: Watch Updates**:
   - Nhấn **Add** tại mục Connection.
   - Điền Bot Token nhận được từ `@BotFather`.
2. Nhấn vào Module **6. Telegram: Send a Message**:
   - Chọn cùng Connection Telegram vừa tạo.

---

### BƯỚC 3: KẾT NỐI GOOGLE GEMINI 2.5 FLASH (MODULE 4)
1. Nhấn vào Module **4. Gemini 2.5 Flash: Phân tích & Viết nội dung**.
2. Tại ô URL:
   `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`
3. Tại mục **Query String** (qs):
   - Thay giá trị `{{var.gemini_api_key}}` bằng **Gemini API Key thật** của bạn (lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/)).

---

### BƯỚC 4: KẾT NỐI FACEBOOK FANPAGE REELS (MODULE 8)
1. Nhấn vào Module **8. Facebook Graph: Khởi tạo Reel**:
   - Thay `{{var.facebook_page_id}}` bằng **Page ID** Fanpage của bạn.
   - Thay `{{var.facebook_page_token}}` bằng **Page Access Token dài hạn** của bạn (Xem hướng dẫn lấy token trong file [SETUP_MAKE_FANPAGE.md](file:///c:/Users/Lenovo/Downloads/auto-post/SETUP_MAKE_FANPAGE.md)).

---

### BƯỚC 5: BẬT CHẾ ĐỘ CHẠY 24/7 (SCHEDULING: ON)
1. Ở góc dưới cùng bên trái của kịch bản Make.com, gạt công tắc **Scheduling** từ `OFF` sang **`ON`**.
2. Chọn tần suất chạy: **Immediately as data arrives** (Chạy ngay lập tức khi có tin nhắn/video mới).
3. Nhấn nút **Save** (Hình đĩa mềm ở đáy màn hình).

🎉 **HOÀN THÀNH:** Kịch bản giờ đây đã chạy 24/7 trên đám mây của Make.com. Bất cứ khi nào bạn gửi video vào Telegram Bot, Make.com sẽ tự động kích hoạt, gọi Gemini phân tích và gửi bản nháp về Telegram để bạn duyệt trước khi đăng bài!

---

## 🚀 3. KHI NÀO ỔN ĐỊNH VÀ BẠN MUỐN THUÊ VPS?

Khi bạn chạy thử nghiệm trên Make.com cảm thấy ưng ý và muốn mở rộng:
1. Thuê một VPS Ubuntu (ví dụ: OVH, Hetzner, Vultr hoặc DigitalOcean khoảng 5$/tháng).
2. Chạy đúng 1 lệnh Docker duy nhất:
   ```bash
   git clone https://github.com/hien23ns/auto-post.git
   cd auto-post
   docker compose up -d --build
   ```
3. Chuyển webhook Make.com sang chế độ Forward tới VPS qua header `X-Automation-Secret` như hướng dẫn trong file [docs/make-com.md](file:///c:/Users/Lenovo/Downloads/auto-post/docs/make-com.md).
4. VPS sẽ đảm nhiệm thêm tính năng **FFmpeg Video Studio trích xuất 3 ảnh bìa thumbnail 9:16 chất lượng cao có chữ tiếng Việt safe-zone** và lưu trữ lịch sử sửa đổi không giới hạn.

---

## 💡 4. CÁCH CHẠY THỬ BACKEND TRÊN MÁY TÍNH BẰNG CLOUDFLARE TUNNEL (MIỄN PHÍ)

Nếu bạn muốn thử nghiệm cả phần tạo 3 Thumbnail tiếng Việt của backend Python ngay trên máy tính mà không cần thuê VPS:
1. Mở Terminal 1 trên máy bạn và chạy:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```
2. Mở trình duyệt thử vào đúng địa chỉ:
   ```
   http://localhost:8001/health
   ```
   *(Nhớ gõ `localhost`, không gõ `0.0.0.0`)*.
3. Để Make.com trên mạng Internet có thể gọi được vào máy tính của bạn miễn phí, tải [Cloudflare Tunnel](https://github.com/cloudflare/cloudflared/releases) và chạy lệnh:
   ```bash
   cloudflared tunnel --url http://localhost:8001
   ```
   Nó sẽ cấp ngay cho bạn 1 URL HTTPS dạng `https://xxx.trycloudflare.com` để dán vào Make.com cực kỳ nhanh chóng!
