"""Test suite for Social Media Publishers (YouTube Shorts, Facebook Fanpage Reels, TikTok)."""

import pytest

from app.config import get_settings
from app.models import PostStatus
from app.publishers.facebook_publisher import FacebookPublisher
from app.publishers.tiktok_publisher import TikTokPublisher
from app.publishers.youtube_publisher import YouTubePublisher

settings = get_settings()


@pytest.mark.asyncio
async def test_youtube_publisher_preview_and_blocked(sample_video_path: str):
    """Verify YouTube publisher behavior in preview mode and when missing credentials."""
    pub = YouTubePublisher()

    # In PREVIEW_ONLY mode: safely returns simulated preview publish without calling live API
    res_preview = await pub.publish(
        video_path=sample_video_path,
        title="Tiêu đề thử nghiệm",
        caption="Mô tả thử nghiệm",
        hashtags=["#Shorts", "#Test"],
    )
    assert res_preview.success is True
    assert res_preview.status == PostStatus.PUBLISHED
    assert "youtube.com/shorts" in res_preview.remote_url

    # Test status checking
    status_check = await pub.check_processing_status("mock_yt_shorts_id_12345")
    assert status_check.status == PostStatus.PUBLISHED


@pytest.mark.asyncio
async def test_facebook_publisher_preview_and_blocked(sample_video_path: str):
    """Verify Facebook Fanpage Reels publisher behavior in preview mode."""
    pub = FacebookPublisher()

    res_preview = await pub.publish(
        video_path=sample_video_path,
        title="Reels thử nghiệm",
        caption="Caption Reels Facebook Fanpage",
        hashtags=["#Reels", "#Viral"],
    )
    assert res_preview.success is True
    assert res_preview.status == PostStatus.PUBLISHED
    assert "facebook.com/reel" in res_preview.remote_url

    # Status check
    status_check = await pub.check_processing_status("mock_fb_reel_id_67890")
    assert status_check.status == PostStatus.PUBLISHED


@pytest.mark.asyncio
async def test_tiktok_publisher_preview_and_creator_info(sample_video_path: str):
    """Verify TikTok publisher behavior and creator info retrieval."""
    pub = TikTokPublisher()

    # Test creator info
    creator_info = await pub.get_creator_info()
    assert "creator_username" in creator_info
    assert "privacy_level_options" in creator_info

    # Test preview publish
    res_preview = await pub.publish(
        video_path=sample_video_path,
        title="TikTok Video Test",
        caption="Caption test",
        hashtags=["#fyp", "#xuhuong"],
    )
    assert res_preview.success is True
    assert res_preview.status == PostStatus.PUBLISHED
    assert "tiktok.com" in res_preview.remote_url


@pytest.mark.asyncio
async def test_unconfigured_publisher_blocked():
    """Verify that if PREVIEW_ONLY is disabled and credentials are missing, publishers return BLOCKED_MISSING_CREDENTIALS."""
    # Temporarily instantiate publishers with empty credentials
    yt = YouTubePublisher()
    yt.client_id = None
    yt.refresh_token = None

    # Force PREVIEW_ONLY to False temporarily
    original_preview = settings.PREVIEW_ONLY
    settings.PREVIEW_ONLY = False
    try:
        res = await yt.publish("dummy.mp4", "Title", "Cap", [])
        assert res.success is False
        assert res.status == PostStatus.BLOCKED_MISSING_CREDENTIALS
    finally:
        settings.PREVIEW_ONLY = original_preview
