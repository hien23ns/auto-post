# HƯỚNG DẪN CẤU HÌNH FACEBOOK FANPAGE & REELS API

> **Tài liệu hướng dẫn chi tiết quy trình xin quyền Meta Graph API, tạo Page Access Token dài hạn và cấu hình xuất bản Facebook Fanpage Reels.**

---

## ⚠️ LƯU Ý BẢO MẬT & QUY ĐỊNH BẮT BUỘC
1. **Chỉ hỗ trợ Facebook FANPAGE, không hỗ trợ Trang Cá Nhân (Personal Profile)**:
   - Meta Graph API chỉ cho phép đăng Reels tự động lên Trang (Facebook Page) do bạn làm Quản trị viên (Admin).
   - Tuyệt đối không dùng User Access Token để đăng bài, bắt buộc phải dùng **Page Access Token**.
2. **Quyền hạn (Permissions) bắt buộc**:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
3. **Graph API Version**: Kiểm tra phiên bản mới nhất (hiện tại v19.0 trở lên).

---

## 🛠️ CÁC BƯỚC THIẾT LẬP META DEVELOPER APP

### Bước 1: Tạo Meta App
1. Truy cập [Meta for Developers](https://developers.facebook.com/) -> Chọn **My Apps** -> **Create App**.
2. Chọn loại ứng dụng: **Business** (Doanh nghiệp) hoặc **Other** -> Nhấn **Next**.
3. Đặt tên ứng dụng (Ví dụ: `Auto Reels Publisher`) và nhập email liên hệ.
4. Nhấn **Create app**.

### Bước 2: Thêm sản phẩm Facebook Login for Business
1. Trong bảng điều khiển App, tìm mục **Facebook Login for Business** -> Nhấn **Set up**.
2. Thêm các quyền (Scopes) cần thiết vào mục Permissions:
   - `pages_show_list`
   - `pages_manage_posts`
   - `pages_read_engagement`

### Bước 3: Lấy Page ID và Tạo Page Access Token dài hạn (Never-Expiring)
1. Mở công cụ [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. Tại mục **Meta App**: Chọn ứng dụng vừa tạo.
3. Tại mục **User or Page**: Chọn **Get Page Access Token** -> Chọn Fanpage của bạn.
4. Cấp quyền truy cập trong cửa sổ xác thực của Facebook.
5. Sao chép chuỗi **Access Token** vừa tạo.
6. Mở công cụ [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/):
   - Dán token vừa lấy vào và bấm **Debug**.
   - Kéo xuống dưới cùng và nhấn **Extend Access Token** để đổi thành Long-lived Token (hạn 60 ngày hoặc vĩnh viễn).
7. Lấy **Page ID**:
   - Truy cập Fanpage trên Facebook -> Vào phần **Giới thiệu (About)** -> Tìm **ID Trang**.
   - Hoặc gọi endpoint Graph API: `GET /me/accounts` để lấy danh sách Page ID và Access Token tương ứng.

---

## 🎥 QUY TRÌNH 3 BƯỚC ĐĂNG REELS QUA META GRAPH API

API Endpoint: `https://graph.facebook.com/v19.0/{page_id}/video_reels`

### Bước 1: Khởi tạo phiên Upload (Upload Phase: START)
- **Method**: `POST`
- **URL**: `https://graph.facebook.com/v19.0/{page_id}/video_reels`
- **Params**:
  - `access_token`: `<PAGE_ACCESS_TOKEN>`
  - `upload_phase`: `start`
- **Kết quả trả về**:
  ```json
  {
    "video_id": "123456789012345",
    "upload_url": "https://rupload.facebook.com/video-upload/v19.0/123456789012345"
  }
  ```

### Bước 2: Tải file Video lên máy chủ Meta (Upload Phase: TRANSFER)
- **Method**: `POST`
- **URL**: `<upload_url nhận được từ Bước 1>`
- **Headers**:
  - `Authorization`: `OAuth <PAGE_ACCESS_TOKEN>`
  - `offset`: `0`
  - `file_size`: `<tổng số bytes của video>`
  - `Content-Type`: `application/octet-stream`
- **Body**: Dữ liệu nhị phân (Binary) của file video mp4 H264.

### Bước 3: Hoàn tất và Đăng bài (Upload Phase: FINISH)
- **Method**: `POST`
- **URL**: `https://graph.facebook.com/v19.0/{page_id}/video_reels`
- **Params**:
  - `access_token`: `<PAGE_ACCESS_TOKEN>`
  - `upload_phase`: `finish`
  - `video_id`: `<video_id từ Bước 1>`
  - `video_state`: `PUBLISHED` (hoặc `SCHEDULED` nếu lên lịch)
  - `description`: `<Nội dung Caption kèm Hashtags>`
- **Kết quả trả về**:
  ```json
  {
    "success": true
  }
  ```

---

## 📋 ĐIỀU CHỈNH TRONG FILE .ENV
Sau khi có đủ thông tin, điền vào file `.env` của hệ thống:
```env
FACEBOOK_PAGE_ID=109283746592812
FACEBOOK_PAGE_ACCESS_TOKEN=EAAG...YourLongLivedPageTokenHere...
ENABLE_FACEBOOK_PUBLISHER=true
```
Nếu chưa có Page Access Token hoặc đang trong quá trình xin cấp quyền ứng dụng, giữ nguyên `PREVIEW_ONLY=true` để hệ thống chạy giả lập an toàn và không gây lỗi.
