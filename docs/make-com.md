# HƯỚNG DẪN CẤU HÌNH MAKE.COM SCENARIO CHO TELEGRAM WEBHOOK

> **Tài liệu hướng dẫn cài đặt kịch bản (Scenario) trên Make.com làm Webhook Gateway trung gian giữa Telegram Bot và FastAPI Backend.**

---

## 1. NGUYÊN LÝ HOẠT ĐỘNG
Telegram Bot API chỉ hỗ trợ **01 URL Webhook duy nhất** cho mỗi Bot Token. Để vừa nhận tin nhắn, video, lệnh điều khiển vừa nhận các tương tác bấm nút (Callback Query), ta sử dụng Make.com làm Single Webhook Receiver.

Make.com sẽ:
1. Nhận toàn bộ cập nhật (Updates) từ Telegram.
2. Kiểm tra tính hợp lệ cơ bản.
3. Chuyển tiếp (Forward) toàn bộ payload JSON sang endpoint của FastAPI Backend: `POST https://your-domain.com/webhook/telegram`.
4. Kèm theo Header xác thực bí mật: `X-Automation-Secret: <your-automation-secret>`.

---

## 2. CẤU TRÚC SCENARIO TRÊN MAKE.COM

```
 [Telegram Bot: Watch Updates]
               │
               ▼
   [Router: Phân loại sự kiện]
     ├── Nhánh 1: Tin nhắn có Video hoặc Lệnh
     │      │
     │      ▼
     │   [HTTP: Make a request]
     │   URL: https://api.yourdomain.com/webhook/telegram
     │   Method: POST
     │   Headers:
     │     - Content-Type: application/json
     │     - X-Automation-Secret: {{secret_token}}
     │   Body: JSON Raw Payload
     │
     └── Nhánh 2: Tương tác nút bấm (Callback Query)
            │
            ▼
         [HTTP: Make a request]
         URL: https://api.yourdomain.com/webhook/telegram
         Method: POST
         Headers:
           - Content-Type: application/json
           - X-Automation-Secret: {{secret_token}}
         Body: JSON Raw Callback Payload
```

---

## 3. CÁC BƯỚC THIẾT LẬP CHI TIẾT

### Bước 1: Tạo Webhook trên Make.com
1. Đăng nhập Make.com -> Nhấn **Create a new scenario**.
2. Thêm module đầu tiên: Tìm kiếm **Telegram Bot** -> Chọn **Watch Updates**.
3. Tại ô **Connection**:
   - Chọn **Add** nếu chưa có kết nối.
   - Điền API Token nhận được từ `@BotFather`.
4. Tại ô **Limit**: Đặt là `10`.
5. Lưu module. Make.com sẽ tự động đăng ký Webhook URL của Make với Telegram Cloud API.

### Bước 2: Thiết lập Router phân luồng
1. Thêm module **Router** ngay sau module Telegram Watch Updates.
2. Tạo 2 nhánh xử lý:

#### Nhánh 1: New Video hoặc Command
- **Điều kiện lọc (Filter)**:
  - `message.video` Exists HOẶC `message.document` Exists HOẶC `message.text` Starts with `/`.
- **Module kế tiếp**: **HTTP - Make a request**.
  - **URL**: `https://api.yourdomain.com/webhook/telegram`
  - **Method**: `POST`
  - **Headers**:
    - Name: `X-Automation-Secret`, Value: `<chuỗi bí mật giống trong .env>`
    - Name: `Content-Type`, Value: `application/json`
  - **Body type**: `Raw`
  - **Content type**: `JSON (application/json)`
  - **Request content**:
    ```json
    {
      "update_id": {{update_id}},
      "message": {{message}}
    }
    ```

#### Nhánh 2: Callback Query (Bấm nút Inline Keyboard)
- **Điều kiện lọc (Filter)**:
  - `callback_query` Exists.
- **Module kế tiếp**: **HTTP - Make a request**.
  - **URL**: `https://api.yourdomain.com/webhook/telegram`
  - **Method**: `POST`
  - **Headers**:
    - Name: `X-Automation-Secret`, Value: `<chuỗi bí mật giống trong .env>`
    - Name: `Content-Type`, Value: `application/json`
  - **Body type**: `Raw`
  - **Content type**: `JSON (application/json)`
  - **Request content**:
    ```json
    {
      "update_id": {{update_id}},
      "callback_query": {{callback_query}}
    }
    ```

---

## 4. XỬ LÝ LỖI VÀ CHỐNG TRÙNG LẶP (ERROR HANDLING)

1. **Auto-Retry trên Make**:
   - Bật tùy chọn **Immediately commit** trong cài đặt Scenario.
   - Thêm Error Directive: **Rollback** hoặc **Resume** nếu HTTP trả về lỗi tạm thời (502, 504).
2. **Không gửi file nhị phân qua Make**:
   - Make.com chỉ chuyển tiếp metadata (`file_id`, `file_unique_id`, `file_size`, `duration`, `mime_type`).
   - Việc tải file nhị phân do FastAPI Worker trực tiếp thực hiện thông qua Telegram Bot API `getFile` hoặc qua Storage link để tránh tốn dung lượng và hạn mức của Make.com.
