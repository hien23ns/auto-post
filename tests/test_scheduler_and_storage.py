"""Test suite for Scheduler and Storage services."""

import os
import time
from datetime import UTC, datetime

from app.services.scheduler_service import (
    format_vn_time,
    parse_schedule_expression,
    utc_to_vn,
    vn_to_utc,
)
from app.services.storage_service import StorageService


def test_timezone_conversions():
    """Verify UTC to Asia/Ho_Chi_Minh conversion is exactly +7 hours."""
    utc_dt = datetime(2026, 10, 20, 10, 0, 0, tzinfo=UTC)
    vn_dt = utc_to_vn(utc_dt)
    assert vn_dt.hour == 17
    assert vn_dt.day == 20
    assert str(vn_dt.tzinfo) == "Asia/Ho_Chi_Minh"

    # Convert back to UTC
    back_to_utc = vn_to_utc(vn_dt)
    assert back_to_utc == utc_dt


def test_format_vn_time():
    """Verify friendly Vietnamese time formatting."""
    utc_dt = datetime(2026, 10, 20, 5, 30, 0, tzinfo=UTC)
    formatted = format_vn_time(utc_dt)
    assert "12:30:00 20/10/2026 (GMT+7)" in formatted
    assert format_vn_time(None) == "Chưa đặt lịch"


def test_parse_schedule_expression():
    """Verify natural language schedule parsing."""
    base_utc = datetime(2026, 10, 20, 3, 0, 0, tzinfo=UTC)  # 10:00 AM VN

    # +2h
    res_plus_2h = parse_schedule_expression("+2h", base_time=base_utc)
    assert res_plus_2h is not None
    assert (res_plus_2h - base_utc).total_seconds() == 7200

    # +30m
    res_plus_30m = parse_schedule_expression("+30m", base_time=base_utc)
    assert res_plus_30m is not None
    assert (res_plus_30m - base_utc).total_seconds() == 1800

    # Specific time "20:00"
    res_time = parse_schedule_expression("20:00", base_time=base_utc)
    assert res_time is not None
    vn_time = utc_to_vn(res_time)
    assert vn_time.hour == 20
    assert vn_time.minute == 0


def test_storage_service_file_operations(tmp_path):
    """Verify storage hashing, MIME sniffing, and cleanup retention."""
    storage = StorageService(base_dir=str(tmp_path))
    assert os.path.exists(storage.raw_dir)
    assert os.path.exists(storage.processed_dir)
    assert os.path.exists(storage.thumbnails_dir)

    # Test valid MP4 magic bytes header
    valid_mp4_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42"
    assert storage.is_valid_video_header(valid_mp4_header) is True

    # Test invalid header
    invalid_header = b"NOT_A_VIDEO_FILE_DATA_HERE"
    assert storage.is_valid_video_header(invalid_header) is False

    # Test checksum calculation
    test_file = os.path.join(str(tmp_path), "test.txt")
    with open(test_file, "wb") as f:
        f.write(b"Hello Auto Publisher 24/7")

    sha256 = storage.calculate_file_hash(test_file, "sha256")
    md5 = storage.calculate_file_hash(test_file, "md5")
    assert len(sha256) == 64
    assert len(md5) == 32

    # Test retention cleanup
    old_file = os.path.join(storage.raw_dir, "old_video.mp4")
    with open(old_file, "wb") as f:
        f.write(b"old")
    # Set mtime to 10 days ago
    ten_days_ago = time.time() - (10 * 86400)
    os.utime(old_file, (ten_days_ago, ten_days_ago))

    deleted = storage.cleanup_old_files(retention_days=7)
    assert deleted >= 1
    assert not os.path.exists(old_file)


def test_large_video_upload_link(tmp_path):
    """Verify large video upload link generator returns structured instructions."""
    storage = StorageService(base_dir=str(tmp_path))
    link_info = storage.generate_large_video_upload_link("big_movie.mp4")
    assert "upload_url" in link_info
    assert "instructions" in link_info
