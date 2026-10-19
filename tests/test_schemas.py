"""Test suite for Pydantic schemas and structured output models."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    EvidenceItem,
    GeminiVideoAnalysis,
    PlatformContent,
    TelegramUpdate,
)


def test_evidence_item_validation():
    """Verify EvidenceItem schema requires timestamp, description, and certainty_score."""
    item = EvidenceItem(
        timestamp="00:05",
        description="Chủ thể xuất hiện và giới thiệu tính năng",
        certainty_score=0.95,
        is_verified=True,
    )
    assert item.timestamp == "00:05"
    assert item.certainty_score == 0.95
    assert item.is_verified is True


def test_platform_content_validation():
    """Verify PlatformContent validates hooks count and properties."""
    content = PlatformContent(
        hooks=["Hook 1", "Hook 2", "Hook 3"],
        caption="Nội dung bài viết chi tiết tiếng Việt",
        hashtags=["#Shorts", "#AI", "#Tech"],
        cta="Đăng ký kênh ngay!",
    )
    assert len(content.hooks) == 3
    assert content.cta == "Đăng ký kênh ngay!"

    # Missing hooks should raise validation error
    with pytest.raises(ValidationError):
        PlatformContent(
            hooks=[],
            caption="Test",
            hashtags=[],
            cta="",
        )


def test_gemini_video_analysis_schema():
    """Verify GeminiVideoAnalysis complete structure and zero-hallucination evidence log."""
    data = {
        "summary": "Tóm tắt video",
        "key_events": ["Sự kiện 1", "Sự kiện 2"],
        "transcript_summary": "Lời thoại tóm tắt",
        "ocr_elements": ["Chữ trên màn hình"],
        "evidence_log": [
            {
                "timestamp": "00:02",
                "description": "Bắt đầu hướng dẫn",
                "certainty_score": 1.0,
                "is_verified": True,
            }
        ],
        "has_uncertain_facts": False,
        "suggested_cover_timestamps": [1.0, 2.0, 3.0],
        "youtube_shorts": {
            "hooks": ["Hook YT 1", "Hook YT 2", "Hook YT 3"],
            "caption": "Caption YouTube Shorts",
            "hashtags": ["#Shorts", "#VN"],
            "cta": "Sub kênh",
        },
        "facebook_reels": {
            "hooks": ["Hook FB 1", "Hook FB 2", "Hook FB 3"],
            "caption": "Caption Facebook Reels",
            "hashtags": ["#Reels"],
            "cta": "Bình luận",
        },
        "tiktok": {
            "hooks": ["Hook TT 1", "Hook TT 2", "Hook TT 3"],
            "caption": "Caption TikTok",
            "hashtags": ["#fyp"],
            "cta": "Follow",
        },
    }
    analysis = GeminiVideoAnalysis.model_validate(data)
    assert analysis.summary == "Tóm tắt video"
    assert len(analysis.evidence_log) == 1
    assert analysis.evidence_log[0].timestamp == "00:02"
    assert analysis.youtube_shorts.hooks[0] == "Hook YT 1"


def test_telegram_update_schema():
    """Verify Telegram update parsing with user and message."""
    raw = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "tester",
            },
            "chat": {
                "id": 123456789,
                "type": "private",
            },
            "date": 1700000000,
            "text": "/start",
        },
    }
    update = TelegramUpdate.model_validate(raw)
    assert update.update_id == 123456
    assert update.message.text == "/start"
    assert update.message.from_user.id == 123456789
