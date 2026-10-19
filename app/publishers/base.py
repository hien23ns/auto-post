"""Abstract base class and result schemas for social media publishers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.models import PostStatus


@dataclass
class PublishResult:
    success: bool
    status: PostStatus
    remote_id: str | None = None
    remote_url: str | None = None
    error: str | None = None
    is_processing: bool = False
    metadata: dict[str, Any] | None = None


class BasePublisher(ABC):
    """Abstract base class that all platform publishers must implement."""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if necessary API credentials and tokens are present."""

    @abstractmethod
    async def publish(
        self,
        video_path: str,
        title: str,
        caption: str,
        hashtags: list[str],
        cover_path: str | None = None,
        privacy: str = "private",
    ) -> PublishResult:
        """Execute publication or submit video to platform."""

    @abstractmethod
    async def check_processing_status(self, remote_id: str) -> PublishResult:
        """Poll platform for remote transcoding or publishing state."""
