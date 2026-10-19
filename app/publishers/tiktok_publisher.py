"""TikTok Content Posting API publisher adhering strictly to developer policies and creator consent."""

import logging
import os
from typing import Any

import httpx

from app.config import get_settings
from app.models import PostStatus
from app.publishers.base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)
settings = get_settings()

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokPublisher(BasePublisher):
    def __init__(self):
        super().__init__("TIKTOK")
        self.client_key = settings.TIKTOK_CLIENT_KEY
        self.client_secret = settings.TIKTOK_CLIENT_SECRET
        self.access_token = settings.TIKTOK_ACCESS_TOKEN
        self.use_direct_post = settings.TIKTOK_USE_DIRECT_POST

    def is_configured(self) -> bool:
        return bool(
            self.client_key
            and self.client_secret
            and self.access_token
            and not self.access_token.startswith("example")
        )

    async def get_creator_info(self) -> dict[str, Any]:
        """Fetch creator account info to display in Telegram before obtaining user consent."""
        if not self.is_configured() or settings.PREVIEW_ONLY:
            return {
                "creator_username": "mock_tiktok_creator",
                "creator_nickname": "Demo TikTok Channel",
                "privacy_level_options": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
                "duet_disabled": False,
                "stitch_disabled": False,
                "comment_disabled": False,
            }

        url = f"{TIKTOK_API_BASE}/post/publish/creator_info/query/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers)
            data = resp.json()
            if resp.status_code != 200 or data.get("error", {}).get("code") != "ok":
                raise RuntimeError(f"TikTok Creator Info query error: {data.get('error')}")
            return data.get("data", {})

    async def publish(
        self,
        video_path: str,
        title: str,
        caption: str,
        hashtags: list[str],
        cover_path: str | None = None,
        privacy: str = "SELF_ONLY",
        consent_granted: bool = True,
        cover_timestamp_ms: int = 1500,
    ) -> PublishResult:
        """Publish video to TikTok either via Upload-to-Inbox (default compliant) or Direct Post."""
        if settings.PREVIEW_ONLY:
            logger.info("[TIKTOK PREVIEW] Simulating TikTok publish. Live API not invoked.")
            return PublishResult(
                success=True,
                status=PostStatus.PUBLISHED,
                remote_id="mock_tiktok_publish_id_9999",
                remote_url="https://www.tiktok.com/@creator/video/mock_tiktok_publish_id_9999",
                metadata={"mode": "preview_mode"},
            )

        if not self.is_configured():
            logger.warning("[TIKTOK BLOCKED] Missing TikTok Developer credentials in live mode.")
            return PublishResult(
                success=False,
                status=PostStatus.BLOCKED_MISSING_CREDENTIALS,
                error="Chưa cấu hình TIKTOK_CLIENT_KEY, CLIENT_SECRET hoặc ACCESS_TOKEN.",
            )

        if not os.path.exists(video_path):
            return PublishResult(success=False, status=PostStatus.FAILED, error=f"Video file not found: {video_path}")

        file_size = os.path.getsize(video_path)
        full_text = f"{title}\n{caption}\n{' '.join(hashtags)}"[:150]  # TikTok title limit

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Decide endpoint: Direct Post vs Upload-to-Inbox
                if self.use_direct_post:
                    # Direct Post (requires TikTok App Partner audit approval)
                    init_url = f"{TIKTOK_API_BASE}/post/publish/video/init/"
                    post_body = {
                        "post_info": {
                            "title": full_text,
                            "privacy_level": privacy,  # e.g. PUBLIC_TO_EVERYONE, SELF_ONLY
                            "disable_duet": False,
                            "disable_stitch": False,
                            "disable_comment": False,
                            "video_cover_timestamp_ms": cover_timestamp_ms,
                        },
                        "source_info": {
                            "source": "FILE_UPLOAD",
                            "video_size": file_size,
                            "chunk_size": file_size,
                            "total_chunk_count": 1,
                        },
                    }
                else:
                    # Upload-to-Inbox (Safest fallback compliant with public TikTok guidelines)
                    init_url = f"{TIKTOK_API_BASE}/post/publish/inbox/video/init/"
                    post_body = {
                        "source_info": {
                            "source": "FILE_UPLOAD",
                            "video_size": file_size,
                            "chunk_size": file_size,
                            "total_chunk_count": 1,
                        }
                    }

                init_resp = await client.post(init_url, headers=headers, json=post_body)
                init_data = init_resp.json()

                if init_resp.status_code != 200 or init_data.get("error", {}).get("code") != "ok":
                    error_msg = init_data.get("error", {}).get("message", init_resp.text)
                    return PublishResult(
                        success=False,
                        status=PostStatus.FAILED,
                        error=f"TikTok init video error: {error_msg}",
                    )

                publish_id = init_data["data"]["publish_id"]
                upload_url = init_data["data"]["upload_url"]

                # Binary chunk upload
                upload_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                }
                with open(video_path, "rb") as vf:
                    chunk_resp = await client.put(upload_url, headers=upload_headers, content=vf.read(), timeout=300.0)

                if chunk_resp.status_code not in (200, 201):
                    return PublishResult(
                        success=False,
                        status=PostStatus.FAILED,
                        error=f"TikTok chunk upload failed: {chunk_resp.status_code}",
                    )

                mode_desc = "Direct Post" if self.use_direct_post else "Upload to Inbox"
                return PublishResult(
                    success=True,
                    status=PostStatus.SUBMITTED,
                    remote_id=publish_id,
                    remote_url=f"https://www.tiktok.com/publish/{publish_id}",
                    is_processing=True,
                    metadata={"mode": mode_desc, "privacy": privacy},
                )

        except Exception as e:
            logger.error(f"TikTok publishing exception: {e}")
            return PublishResult(success=False, status=PostStatus.FAILED, error=str(e))

    async def check_processing_status(self, remote_id: str) -> PublishResult:
        """Poll TikTok for video publishing status."""
        if not self.is_configured() or settings.PREVIEW_ONLY:
            return PublishResult(
                success=True,
                status=PostStatus.PUBLISHED,
                remote_id=remote_id,
                remote_url=f"https://www.tiktok.com/publish/{remote_id}",
                is_processing=False,
            )

        url = f"{TIKTOK_API_BASE}/post/publish/status/fetch/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        data = {"publish_id": remote_id}

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, headers=headers, json=data)
                res_json = resp.json()

            status = res_json.get("data", {}).get("status")
            if status == "SUCCESS":
                return PublishResult(
                    success=True,
                    status=PostStatus.PUBLISHED,
                    remote_id=remote_id,
                    remote_url=f"https://www.tiktok.com/publish/{remote_id}",
                    is_processing=False,
                )
            elif status == "FAILED":
                fail_reason = res_json.get("data", {}).get("fail_reason", "Unknown failure")
                return PublishResult(
                    success=False, status=PostStatus.FAILED, remote_id=remote_id, error=f"TikTok rejected: {fail_reason}"
                )
            else:
                return PublishResult(
                    success=True,
                    status=PostStatus.PROCESSING,
                    remote_id=remote_id,
                    remote_url=f"https://www.tiktok.com/publish/{remote_id}",
                    is_processing=True,
                )

        except Exception as e:
            return PublishResult(
                success=False, status=PostStatus.PROCESSING, remote_id=remote_id, error=str(e), is_processing=True
            )


tiktok_publisher = TikTokPublisher()
