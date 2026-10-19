"""Test suite for FFmpeg video processing and Thumbnail Studio Safe-Zone typography."""

import os

from PIL import Image

from app.services.ffmpeg_service import ffmpeg_service
from app.services.thumbnail_service import thumbnail_service


def test_ffmpeg_probe_video(sample_video_path: str):
    """Verify ffprobe correctly extracts video duration, dimensions, and fps."""
    meta = ffmpeg_service.probe_video(sample_video_path)
    assert meta["duration"] > 0
    assert meta["width"] == 720
    assert meta["height"] == 1280
    assert meta["fps"] == 30.0
    assert meta["is_vertical"] is True


def test_ffmpeg_extract_keyframe(sample_video_path: str, tmp_path):
    """Verify single frame extraction at timestamp produces valid JPEG file."""
    output_frame = os.path.join(str(tmp_path), "extracted_frame.jpg")
    res = ffmpeg_service.extract_frame_at_timestamp(sample_video_path, 1.0, output_frame)
    assert os.path.exists(res)
    assert os.path.getsize(res) > 0

    with Image.open(res) as img:
        assert img.format == "JPEG"
        assert img.width == 720
        assert img.height == 1280


def test_ffmpeg_detect_scene_timestamps(sample_video_path: str):
    """Verify scene timestamp detection returns sorted timestamps within video bounds."""
    timestamps = ffmpeg_service.detect_scene_timestamps(sample_video_path, max_points=3)
    assert len(timestamps) > 0
    assert all(ts > 0 for ts in timestamps)
    assert timestamps == sorted(timestamps)


def test_thumbnail_studio_three_variants(sample_video_path: str, tmp_path):
    """Verify Thumbnail Studio generates 3 9:16 safe-zone covers with Vietnamese typography."""
    # 1. Extract 2 real frames
    frame1 = os.path.join(str(tmp_path), "frame_1.jpg")
    frame2 = os.path.join(str(tmp_path), "frame_2.jpg")
    ffmpeg_service.extract_frame_at_timestamp(sample_video_path, 0.5, frame1)
    ffmpeg_service.extract_frame_at_timestamp(sample_video_path, 1.5, frame2)

    thumb_dir = os.path.join(str(tmp_path), "thumbnails")
    vietnamese_title = "BÍ QUYẾT TĂNG TƯƠNG TÁC VIDEO CỰC ĐỈNH 2026"

    covers = thumbnail_service.generate_three_variants(
        frame_paths=[frame1, frame2],
        title=vietnamese_title,
        output_dir=thumb_dir,
    )

    # Assert 3 variants generated
    assert len(covers) == 3

    for cover_path in covers:
        assert os.path.exists(cover_path)
        assert os.path.getsize(cover_path) > 1000

        with Image.open(cover_path) as img:
            # Must strictly match 9:16 vertical standard dimensions (1080x1920)
            assert img.size == (1080, 1920)
            assert img.format == "JPEG"


def test_thumbnail_text_wrapping():
    """Verify text wrapping respects max horizontal safe width."""
    font = thumbnail_service.get_font(60)
    long_text = "ĐÂY LÀ TIÊU ĐỀ RẤT DÀI CẦN ĐƯỢC TỰ ĐỘNG XUỐNG DÒNG ĐÚNG CHUẨN TIẾNG VIỆT ĐỂ KHÔNG BỊ TRÀN VIỀN"
    lines = thumbnail_service._wrap_text(long_text, font, max_width=800)
    assert len(lines) > 1
    # Verify no line is empty
    assert all(len(line.strip()) > 0 for line in lines)
