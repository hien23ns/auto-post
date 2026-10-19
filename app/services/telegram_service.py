"""Telegram Bot API service handling messages, media albums, inline keyboards, and file downloads."""

import logging
import os
from typing import Any

import httpx

from app.config import get_settings
from app.services.scheduler_service import format_vn_time

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramService:
    def __init__(self, bot_token: str | None = None):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self.file_base = f"https://api.telegram.org/file/bot{self.bot_token}"

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and not self.bot_token.endswith("_EXAMPLE"))

    async def get_file_info(self, file_id: str) -> dict[str, Any]:
        """Fetch file metadata including file_path from Telegram Bot API."""
        if not self.is_configured:
            return {"file_path": f"mock_telegram_path/{file_id}.mp4"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.api_base}/getFile", params={"file_id": file_id})
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram getFile error: {data.get('description')}")
            return data["result"]

    async def download_file(self, file_id: str, dest_path: str) -> str:
        """Download binary file from Telegram and save to destination path."""
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        if not self.is_configured:
            # Create a small valid test mp4 header if in test/mock mode
            with open(dest_path, "wb") as f:
                f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42")
            return dest_path

        info = await self.get_file_info(file_id)
        remote_path = info.get("file_path")
        file_url = f"{self.file_base}/{remote_path}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("GET", file_url) as stream:
                stream.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in stream.aiter_bytes(65536):
                        f.write(chunk)

        return dest_path

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str = "HTML",
    ) -> dict[str, Any]:
        """Send a text message with optional inline keyboard."""
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        if not self.is_configured:
            logger.info(f"[MOCK TG SEND] Chat {chat_id}: {text[:100]}...")
            return {"ok": True, "result": {"message_id": 999999}}

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(f"{self.api_base}/sendMessage", json=payload)
            return resp.json()

    async def answer_callback_query(self, callback_query_id: str, text: str = "", show_alert: bool = False) -> None:
        """Acknowledge a Telegram callback query."""
        if not self.is_configured:
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{self.api_base}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_query_id,
                    "text": text,
                    "show_alert": show_alert,
                },
            )

    async def send_media_group_photos(self, chat_id: int, photo_paths: list[str], caption: str = "") -> list[dict[str, Any]]:
        """Send an album of photos (e.g. the 3 generated thumbnail covers)."""
        if not self.is_configured:
            logger.info(f"[MOCK TG MEDIA GROUP] Sending {len(photo_paths)} photos to {chat_id}")
            return [{"message_id": 100000 + i} for i in range(len(photo_paths))]

        files = {}
        media = []
        for idx, path in enumerate(photo_paths):
            attach_name = f"photo_{idx}"
            media.append({
                "type": "photo",
                "media": f"attach://{attach_name}",
                "caption": caption if idx == 0 else "",
                "parse_mode": "HTML",
            })
            files[attach_name] = (os.path.basename(path), open(path, "rb"), "image/jpeg")

        data = {"chat_id": str(chat_id), "media": httpx._compat.json_dumps(media)}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.api_base}/sendMediaGroup", data=data, files=files)
                return resp.json().get("result", [])
        finally:
            for f in files.values():
                f[1].close()

    def build_review_inline_keyboard(
        self,
        job_id: str,
        selected_cover: int = 0,
        platforms_enabled: list[str] | None = None,
    ) -> dict[str, Any]:
        """Construct standard interactive inline keyboard for job preview & approval."""
        enabled = platforms_enabled or ["YOUTUBE", "FACEBOOK", "TIKTOK"]

        c0 = "🔘 Bìa 1 (Top)" if selected_cover == 0 else "⚪ Bìa 1"
        c1 = "🔘 Bìa 2 (Center)" if selected_cover == 1 else "⚪ Bìa 2"
        c2 = "🔘 Bìa 3 (Bottom)" if selected_cover == 2 else "⚪ Bìa 3"

        yt_btn = "📺 YT: BẬT" if "YOUTUBE" in enabled else "📺 YT: TẮT"
        fb_btn = "📘 FB: BẬT" if "FACEBOOK" in enabled else "📘 FB: TẮT"
        tt_btn = "🎵 TT: BẬT" if "TIKTOK" in enabled else "🎵 TT: TẮT"

        keyboard = [
            # Row 1: Chọn ảnh bìa
            [
                {"text": c0, "callback_data": f"job:{job_id}:cover:0"},
                {"text": c1, "callback_data": f"job:{job_id}:cover:1"},
                {"text": c2, "callback_data": f"job:{job_id}:cover:2"},
            ],
            # Row 2: Bật/Tắt nền tảng
            [
                {"text": yt_btn, "callback_data": f"job:{job_id}:toggle:YOUTUBE"},
                {"text": fb_btn, "callback_data": f"job:{job_id}:toggle:FACEBOOK"},
                {"text": tt_btn, "callback_data": f"job:{job_id}:toggle:TIKTOK"},
            ],
            # Row 3: Chỉnh sửa & Chi tiết
            [
                {"text": "✏️ Sửa nội dung", "callback_data": f"job:{job_id}:edit_text"},
                {"text": "⏰ Lên lịch", "callback_data": f"job:{job_id}:schedule"},
            ],
            # Row 4: Phê duyệt hoặc Hủy bỏ
            [
                {"text": "🚀 DUYỆT ĐĂNG NGAY", "callback_data": f"job:{job_id}:approve"},
                {"text": "❌ HỦY", "callback_data": f"job:{job_id}:cancel"},
            ],
        ]
        return {"inline_keyboard": keyboard}

    def format_job_preview_card(self, job_dict: dict[str, Any]) -> str:
        """Format comprehensive HTML preview message for Telegram user."""
        job_id = job_dict.get("id", "N/A")
        duration = int(job_dict.get("video_duration") or 0)
        selected_cover = job_dict.get("selected_cover_index", 0) + 1
        platforms = ", ".join(job_dict.get("platforms_enabled") or [])
        scheduled = format_vn_time(job_dict.get("scheduled_at_utc"))
        draft = job_dict.get("content_draft") or {}

        yt = draft.get("youtube_shorts", {})
        fb = draft.get("facebook_reels", {})
        tt = draft.get("tiktok", {})

        warning_line = ""
        if job_dict.get("uncertain_warning"):
            warning_line = "\n⚠️ <b>CẢNH BÁO AI:</b> Có chi tiết cần người dùng kiểm tra kỹ trước khi duyệt!\n"

        text = (
            f"🎬 <b>BẢN NHÁP XUẤT BẢN VIDEO 24/7</b>\n"
            f"🆔 <code>{job_id}</code> | ⏱️ {duration}s | 🖼️ Bìa đã chọn: #{selected_cover}\n"
            f"🌐 Nền tảng: <b>{platforms}</b>\n"
            f"⏰ Lịch đăng: <b>{scheduled}</b>\n"
            f"{warning_line}\n"
            f"🔴 <b>YOUTUBE SHORTS:</b>\n"
            f"• <b>Tiêu đề:</b> {yt.get('hooks', [''])[0]}\n"
            f"• <b>Hashtags:</b> {' '.join(yt.get('hashtags', []))}\n\n"
            f"🔵 <b>FACEBOOK REELS:</b>\n"
            f"• <b>Caption:</b> {fb.get('caption', '')[:120]}...\n\n"
            f"🎵 <b>TIKTOK:</b>\n"
            f"• <b>Hook:</b> {tt.get('hooks', [''])[0]}\n"
            f"• <b>Hashtags:</b> {' '.join(tt.get('hashtags', []))}\n\n"
            f"👇 <i>Chọn ảnh bìa, nền tảng hoặc bấm 'DUYỆT ĐĂNG NGAY' bên dưới:</i>"
        )
        return text


telegram_service = TelegramService()
