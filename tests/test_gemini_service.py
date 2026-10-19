"""Test suite for Gemini AI video understanding service."""

import pytest

from app.schemas import GeminiVideoAnalysis
from app.services.gemini_service import gemini_service


@pytest.mark.asyncio
async def test_gemini_video_analysis_fallback_and_evidence(sample_video_path: str):
    """Verify Gemini analysis produces evidence with timestamps and platform-tailored content."""
    analysis = await gemini_service.analyze_video(sample_video_path, video_duration=12.0)

    assert isinstance(analysis, GeminiVideoAnalysis)
    assert len(analysis.evidence_log) >= 2

    # Verify every evidence item has timestamp and is marked verified
    for ev in analysis.evidence_log:
        assert ev.timestamp is not None
        assert ev.certainty_score >= 0.9
        assert ev.is_verified is True

    # Verify zero-hallucination flag is checked
    assert analysis.has_uncertain_facts is False

    # Verify 3 suggested cover timestamps
    assert len(analysis.suggested_cover_timestamps) == 3

    # Verify platform content guidelines
    # YouTube Shorts
    assert len(analysis.youtube_shorts.hooks) == 3
    assert any("#Shorts" in hook for hook in analysis.youtube_shorts.hooks) or "#Shorts" in analysis.youtube_shorts.hashtags
    assert analysis.youtube_shorts.cta != ""

    # Facebook Fanpage Reels
    assert len(analysis.facebook_reels.hooks) == 3
    assert len(analysis.facebook_reels.caption) > 10

    # TikTok
    assert len(analysis.tiktok.hooks) == 3
    assert len(analysis.tiktok.hashtags) >= 3
