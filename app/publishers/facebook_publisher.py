"""Facebook Fanpage Reels publisher using Meta Graph API (3-phase upload)."""

import logging
import os

import httpx

from app.config import get_settings
from app.models import PostStatus
from app.publishers.base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)
settings = get_settings()

GRAPH_API_VERSION = "v19.0"


class FacebookPublisher(BasePublisher):
    def __init__(self):
        super().__init__("FACEBOOK")
        self.page_id = settings.FACEBOOK_PAGE_ID
        self.page_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
        self.api_base = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

    def is_configured(self) -> bool:
        return bool(
            self.page_id
            and self.page_token
            and not self.page_token.startswith("EAAG_example")
        )

    async def publish(
        self,
        video_path: str,
        title: str,
        caption: str,
        hashtags: list[str],
        cover_path: str | None = None,
        privacy: str = "public",
    ) -> PublishResult:
        """Publish video reel to Facebook Fanpage via Meta Graph API."""
        if settings.PREVIEW_ONLY:
            logger.info("[FACEBOOK PREVIEW] Simulating Reels publish. Live API not invoked.")
            return PublishResult(
                success=True,
                status=PostStatus.PUBLISHED,
                remote_id="mock_fb_reel_id_67890",
                remote_url="https://facebook.com/reel/mock_fb_reel_id_67890",
                metadata={"page_id": self.page_id},
            )

        if not self.is_configured():
            logger.warning("[FACEBOOK BLOCKED] Missing Page credentials in live mode.")
            return PublishResult(
                success=False,
                status=PostStatus.BLOCKED_MISSING_CREDENTIALS,
                error="Chưa cấu hình FACEBOOK_PAGE_ID hoặc FACEBOOK_PAGE_ACCESS_TOKEN.",
            )

        if not os.path.exists(video_path):
            return PublishResult(success=False, status=PostStatus.FAILED, error=f"Video file not found: {video_path}")

        try:
            file_size = os.path.getsize(video_path)
            full_description = f"{caption}\n\n{' '.join(hashtags)}"

            async with httpx.AsyncClient(timeout=60.0) as client:
                # Phase 1: Initialize Reels Upload Session
                init_url = f"{self.api_base}/{self.page_id}/video_reels"
                init_params = {
                    "upload_phase": "start",
                    "access_token": self.page_token,
                }
                init_resp = await client.post(init_url, params=init_params)
                init_data = init_resp.json()

                if init_resp.status_code != 200 or "video_id" not in init_data:
                    return PublishResult(
                        success=False,
                        status=PostStatus.FAILED,
                        error=f"Facebook Reels start phase failed: {init_data.get('error', {}).get('message', init_resp.text)}",
                    )

                video_id = init_data["video_id"]
                upload_url = init_data.get("upload_url")

                # Phase 2: Binary Video Transfer
                upload_headers = {
                    "Authorization": f"OAuth {self.page_token}",
                    "offset": "0",
                    "file_size": str(file_size),
                    "Content-Type": "application/octet-stream",
                }
                with open(video_path, "rb") as vf:
                    upload_resp = await client.post(
                        upload_url,
                        headers=upload_headers,
                        content=vf.read(),
                        timeout=300.0,
                    )

                if upload_resp.status_code not in (200, 201):
                    return PublishResult(
                        success=False,
                        status=PostStatus.FAILED,
                        error=f"Facebook Reels binary transfer failed: {upload_resp.status_code} - {upload_resp.text}",
                    )

                # Phase 3: Finish and Publish Reel
                finish_url = f"{self.api_base}/{self.page_id}/video_reels"
                finish_data = {
                    "upload_phase": "finish",
                    "access_token": self.page_token,
                    "video_id": video_id,
                    "video_state": "PUBLISHED",
                    "description": full_description,
                }
                finish_resp = await client.post(finish_url, data=finish_data)
                finish_json = finish_resp.json()

                if not finish_json.get("success", False):
                    return PublishResult(
                        success=False,
                        status=PostStatus.FAILED,
                        error=f"Facebook Reels finish phase failed: {finish_json.get('error', {}).get('message', finish_resp.text)}",
                    )

                reel_url = f"https://www.facebook.com/reel/{video_id}"
                return PublishResult(
                    success=True,
                    status=PostStatus.SUBMITTED,
                    remote_id=video_id,
                    remote_url=reel_url,
                    is_processing=True,
                    metadata={"page_id": self.page_id},
                )

        except Exception as e:
            logger.error(f"Facebook publishing exception: {e}")
            return PublishResult(success=False, status=PostStatus.FAILED, error=str(e))

    async def check_processing_status(self, remote_id: str) -> PublishResult:
        """Poll Facebook video processing state."""
        if not self.is_configured() or settings.PREVIEW_ONLY:
            return PublishResult(
                success=True,
                status=PostStatus.PUBLISHED,
                remote_id=remote_id,
                remote_url=f"https://www.facebook.com/reel/{remote_id}",
                is_processing=False,
            )

        try:
            url = f"{self.api_base}/{remote_id}"
            params = {
                "fields": "status,published",
                "access_token": self.page_token,
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, params=params)
                data = resp.json()

            status_obj = data.get("status", {})
            video_status = status_obj.get("video_status")

            if video_status == "ready":
                return PublishResult(
                    success=True,
                    status=PostStatus.PUBLISHED,
                    remote_id=remote_id,
                    remote_url=f"https://www.facebook.com/reel/{remote_id}",
                    is_processing=False,
                )
            elif video_status == "error":
                return PublishResult(
                    success=False,
                    status=PostStatus.FAILED,
                    remote_id=remote_id,
                    error=status_obj.get("processing_subphase", "Unknown processing error"),
                )
            else:
                return PublishResult(
                    success=True,
                    status=PostStatus.PROCESSING,
                    remote_id=remote_id,
                    remote_url=f"https://www.facebook.com/reel/{remote_id}",
                    is_processing=True,
                )

        except Exception as e:
            return PublishResult(
                success=False, status=PostStatus.PROCESSING, remote_id=remote_id, error=str(e), is_processing=True
            )


facebook_publisher = FacebookPublisher()
