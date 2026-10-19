"""YouTube Shorts publisher using Google Data API v3 with resumable upload."""

import logging
import os

import httpx

from app.config import get_settings
from app.models import PostStatus
from app.publishers.base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)
settings = get_settings()


class YouTubePublisher(BasePublisher):
    def __init__(self):
        super().__init__("YOUTUBE")
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET
        self.refresh_token = settings.YOUTUBE_REFRESH_TOKEN
        self.default_privacy = settings.YOUTUBE_DEFAULT_PRIVACY or "private"

    def is_configured(self) -> bool:
        return bool(
            self.client_id
            and self.client_secret
            and self.refresh_token
            and not self.refresh_token.startswith("example")
        )

    async def _get_access_token(self) -> str:
        """Obtain short-lived access token using stored refresh token without logging secrets."""
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(token_url, data=data)
            if resp.status_code != 200:
                raise RuntimeError(f"Google OAuth token refresh failed: {resp.status_code}")
            return resp.json()["access_token"]

    async def publish(
        self,
        video_path: str,
        title: str,
        caption: str,
        hashtags: list[str],
        cover_path: str | None = None,
        privacy: str | None = None,
    ) -> PublishResult:
        """Upload video to YouTube as a Short using resumable upload."""
        if settings.PREVIEW_ONLY:
            logger.info("[YOUTUBE PREVIEW] Simulating preview publish. Live API not invoked.")
            return PublishResult(
                success=True,
                status=PostStatus.PUBLISHED,
                remote_id="mock_yt_shorts_id_12345",
                remote_url="https://youtube.com/shorts/mock_yt_shorts_id_12345",
                metadata={"privacy": "preview_mode"},
            )

        if not self.is_configured():
            logger.warning("[YOUTUBE BLOCKED] Missing OAuth credentials in live mode.")
            return PublishResult(
                success=False,
                status=PostStatus.BLOCKED_MISSING_CREDENTIALS,
                error="Chưa cấu hình YOUTUBE_CLIENT_ID, SECRET hoặc REFRESH_TOKEN.",
            )

        if not os.path.exists(video_path):
            return PublishResult(success=False, status=PostStatus.FAILED, error=f"Video file not found: {video_path}")

        try:
            access_token = await self._get_access_token()
            file_size = os.path.getsize(video_path)

            # Ensure #Shorts tag is present in title or description
            full_title = title if "#Shorts" in title else f"{title} #Shorts"
            # YouTube title maximum 100 characters
            if len(full_title) > 100:
                full_title = full_title[:92] + " #Shorts"

            full_desc = f"{caption}\n\n{' '.join(hashtags)}"
            privacy_status = privacy or self.default_privacy

            # Phase 1: Initialize Resumable Upload Session
            init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(file_size),
                "X-Upload-Content-Type": "video/mp4",
            }
            body = {
                "snippet": {
                    "title": full_title,
                    "description": full_desc,
                    "tags": [tag.replace("#", "") for tag in hashtags],
                    "categoryId": "22",  # People & Blogs
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                init_resp = await client.post(init_url, headers=headers, json=body)
                if init_resp.status_code != 200:
                    return PublishResult(
                        success=False,
                        status=PostStatus.FAILED,
                        error=f"YouTube init upload failed: {init_resp.status_code} - {init_resp.text}",
                    )

                upload_session_url = init_resp.headers.get("Location")
                if not upload_session_url:
                    return PublishResult(
                        success=False,
                        status=PostStatus.FAILED,
                        error="Missing Location header in YouTube resumable upload response",
                    )

                # Phase 2: Upload Video Binary Stream
                with open(video_path, "rb") as video_file:
                    upload_resp = await client.put(
                        upload_session_url,
                        headers={"Content-Length": str(file_size), "Content-Type": "video/mp4"},
                        content=video_file.read(),
                        timeout=300.0,
                    )

                if upload_resp.status_code not in (200, 201):
                    return PublishResult(
                        success=False,
                        status=PostStatus.FAILED,
                        error=f"YouTube video stream upload failed: {upload_resp.status_code} - {upload_resp.text}",
                    )

                res_data = upload_resp.json()
                video_id = res_data.get("id")
                video_url = f"https://youtube.com/shorts/{video_id}"

                return PublishResult(
                    success=True,
                    status=PostStatus.SUBMITTED,
                    remote_id=video_id,
                    remote_url=video_url,
                    is_processing=True,
                    metadata={"privacy": privacy_status},
                )

        except Exception as e:
            logger.error(f"YouTube publishing exception: {e}")
            return PublishResult(success=False, status=PostStatus.FAILED, error=str(e))

    async def check_processing_status(self, remote_id: str) -> PublishResult:
        """Check video processing status on YouTube."""
        if not self.is_configured() or settings.PREVIEW_ONLY:
            return PublishResult(
                success=True,
                status=PostStatus.PUBLISHED,
                remote_id=remote_id,
                remote_url=f"https://youtube.com/shorts/{remote_id}",
                is_processing=False,
            )

        try:
            access_token = await self._get_access_token()
            url = f"https://www.googleapis.com/youtube/v3/videos?part=status,processingDetails&id={remote_id}"
            headers = {"Authorization": f"Bearer {access_token}"}

            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, headers=headers)
                data = resp.json()

            items = data.get("items", [])
            if not items:
                return PublishResult(
                    success=False, status=PostStatus.FAILED, remote_id=remote_id, error="Video not found on YouTube"
                )

            status_info = items[0].get("status", {})
            upload_status = status_info.get("uploadStatus")

            if upload_status == "processed":
                return PublishResult(
                    success=True,
                    status=PostStatus.PUBLISHED,
                    remote_id=remote_id,
                    remote_url=f"https://youtube.com/shorts/{remote_id}",
                    is_processing=False,
                )
            elif upload_status == "failed":
                reason = status_info.get("rejectionReason", "Unknown failure")
                return PublishResult(
                    success=False,
                    status=PostStatus.FAILED,
                    remote_id=remote_id,
                    error=f"YouTube processing rejected: {reason}",
                )
            else:
                # Still processing or uploaded
                return PublishResult(
                    success=True,
                    status=PostStatus.PROCESSING,
                    remote_id=remote_id,
                    remote_url=f"https://youtube.com/shorts/{remote_id}",
                    is_processing=True,
                )

        except Exception as e:
            return PublishResult(
                success=False, status=PostStatus.PROCESSING, remote_id=remote_id, error=str(e), is_processing=True
            )


youtube_publisher = YouTubePublisher()
