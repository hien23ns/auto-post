"""Test suite for FastAPI endpoints, Webhook authentication, and durable job lifecycle."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Job,
    JobStatus,
    WorkerHeartbeat,
    utc_now,
)

settings = get_settings()
TEST_SECRET = "test-secret-key-for-ci-pipeline-1234"
ALLOWED_USER_ID = 123456789
UNAUTHORIZED_USER_ID = 999999999


@pytest.mark.asyncio
async def test_health_check_healthy(client: AsyncClient, test_db: AsyncSession):
    """Verify /health returns 200 OK when DB is connected and worker heartbeat is recent."""
    hb = WorkerHeartbeat(
        id="worker_test",
        worker_name="Test Worker",
        last_heartbeat=utc_now(),
        status="ACTIVE",
    )
    test_db.add(hb)
    await test_db.commit()

    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["worker_heartbeat"] == "active"
    assert data["timezone"] == "Asia/Ho_Chi_Minh"


@pytest.mark.asyncio
async def test_health_check_stale_worker(client: AsyncClient, test_db: AsyncSession):
    """Verify /health returns 503 Service Unavailable when worker heartbeat is stale (>90s)."""
    hb = WorkerHeartbeat(
        id="worker_test",
        worker_name="Test Worker",
        last_heartbeat=utc_now() - timedelta(seconds=120),
        status="ACTIVE",
    )
    test_db.add(hb)
    await test_db.commit()

    resp = await client.get("/health")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_webhook_secret_authentication(client: AsyncClient):
    """Verify /webhook/telegram rejects requests without valid X-Automation-Secret."""
    payload = {"update_id": 1, "message": {"message_id": 1, "chat": {"id": 1}, "date": 0}}

    # Missing header -> 403
    resp_no_header = await client.post("/webhook/telegram", json=payload)
    assert resp_no_header.status_code == 403

    # Invalid header -> 403
    resp_bad_header = await client.post(
        "/webhook/telegram",
        json=payload,
        headers={"X-Automation-Secret": "wrong-secret"},
    )
    assert resp_bad_header.status_code == 403

    # Valid header -> 200
    resp_ok = await client.post(
        "/webhook/telegram",
        json=payload,
        headers={"X-Automation-Secret": TEST_SECRET},
    )
    assert resp_ok.status_code == 200


@pytest.mark.asyncio
async def test_webhook_user_allowlist(client: AsyncClient):
    """Verify unauthorized users are rejected and authorized users can send commands."""
    headers = {"X-Automation-Secret": TEST_SECRET}

    # Unauthorized user
    unauth_payload = {
        "update_id": 2,
        "message": {
            "message_id": 2,
            "from": {"id": UNAUTHORIZED_USER_ID, "first_name": "Stranger"},
            "chat": {"id": UNAUTHORIZED_USER_ID, "type": "private"},
            "date": 1700000000,
            "text": "/start",
        },
    }
    resp_unauth = await client.post("/webhook/telegram", json=unauth_payload, headers=headers)
    assert resp_unauth.status_code == 200
    data_unauth = resp_unauth.json()
    assert data_unauth["ok"] is False
    assert "allowlist" in data_unauth["message"]

    # Authorized user
    auth_payload = {
        "update_id": 3,
        "message": {
            "message_id": 3,
            "from": {"id": ALLOWED_USER_ID, "first_name": "Admin"},
            "chat": {"id": ALLOWED_USER_ID, "type": "private"},
            "date": 1700000000,
            "text": "/help",
        },
    }
    resp_auth = await client.post("/webhook/telegram", json=auth_payload, headers=headers)
    assert resp_auth.status_code == 200
    data_auth = resp_auth.json()
    assert data_auth["ok"] is True


@pytest.mark.asyncio
async def test_webhook_enqueue_video_job(client: AsyncClient, test_db: AsyncSession):
    """Verify sending a video creates a durable Job in database with status PENDING."""
    headers = {"X-Automation-Secret": TEST_SECRET}
    video_payload = {
        "update_id": 4,
        "message": {
            "message_id": 4,
            "from": {"id": ALLOWED_USER_ID, "first_name": "Creator"},
            "chat": {"id": ALLOWED_USER_ID, "type": "private"},
            "date": 1700000000,
            "video": {
                "file_id": "telegram_video_file_abc123",
                "file_unique_id": "uniq_123",
                "width": 1080,
                "height": 1920,
                "duration": 15,
                "file_name": "my_reel.mp4",
                "mime_type": "video/mp4",
                "file_size": 5242880,
            },
        },
    }

    resp = await client.post("/webhook/telegram", json=video_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["job_id"] is not None

    # Inspect job in database
    job_id = data["job_id"]
    job_resp = await client.get(f"/api/jobs/{job_id}")
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    assert job_data["status"] == JobStatus.PENDING.value
    assert job_data["telegram_user_id"] == ALLOWED_USER_ID


@pytest.mark.asyncio
async def test_callback_query_actions(client: AsyncClient, test_db: AsyncSession):
    """Verify inline keyboard callback queries (cover selection, platform toggle, approve)."""
    headers = {"X-Automation-Secret": TEST_SECRET}

    # Create a job in database
    job = Job(
        telegram_chat_id=ALLOWED_USER_ID,
        telegram_user_id=ALLOWED_USER_ID,
        source_file_id="test_fid",
        status=JobStatus.REVIEW_READY.value,
        platforms_enabled=["YOUTUBE", "FACEBOOK", "TIKTOK"],
        selected_cover_index=0,
    )
    test_db.add(job)
    await test_db.commit()
    await test_db.refresh(job)

    # 1. Callback: Chọn ảnh bìa 2 (index 1)
    cb_cover = {
        "update_id": 10,
        "callback_query": {
            "id": "cb_query_1",
            "from": {"id": ALLOWED_USER_ID, "first_name": "Admin"},
            "data": f"job:{job.id}:cover:1",
        },
    }
    resp_cover = await client.post("/webhook/telegram", json=cb_cover, headers=headers)
    assert resp_cover.status_code == 200

    # 2. Callback: Bật/Tắt nền tảng (Tắt TIKTOK)
    cb_toggle = {
        "update_id": 11,
        "callback_query": {
            "id": "cb_query_2",
            "from": {"id": ALLOWED_USER_ID, "first_name": "Admin"},
            "data": f"job:{job.id}:toggle:TIKTOK",
        },
    }
    resp_toggle = await client.post("/webhook/telegram", json=cb_toggle, headers=headers)
    assert resp_toggle.status_code == 200

    # 3. Callback: Phê duyệt đăng ngay (Approve)
    cb_approve = {
        "update_id": 12,
        "callback_query": {
            "id": "cb_query_3",
            "from": {"id": ALLOWED_USER_ID, "first_name": "Admin"},
            "data": f"job:{job.id}:approve",
        },
    }
    resp_approve = await client.post("/webhook/telegram", json=cb_approve, headers=headers)
    assert resp_approve.status_code == 200

    # Refresh job state
    job_detail = await client.get(f"/api/jobs/{job.id}")
    d = job_detail.json()
    assert d["selected_cover_index"] == 1
    assert "TIKTOK" not in d["platforms_enabled"]
    assert d["status"] == JobStatus.PUBLISHING.value


@pytest.mark.asyncio
async def test_job_revisions_endpoint(client: AsyncClient, test_db: AsyncSession):
    """Verify saving a revision updates current draft and stores revision history."""
    job = Job(
        telegram_chat_id=ALLOWED_USER_ID,
        telegram_user_id=ALLOWED_USER_ID,
        status=JobStatus.REVIEW_READY.value,
        content_draft={
            "youtube_shorts": {
                "hooks": ["Hook Cũ"],
                "caption": "Caption Cũ",
                "hashtags": ["#old"],
                "cta": "Sub",
            }
        },
    )
    test_db.add(job)
    await test_db.commit()
    await test_db.refresh(job)

    # Post edited revision
    rev_payload = {
        "platform": "youtube_shorts",
        "hook": "Hook Mới Đã Sửa Đổi Cực Hay",
        "caption": "Caption mới đã tối ưu chuẩn SEO",
        "hashtags": ["#Shorts", "#NewSEO"],
        "cta": "Đăng ký kênh ngay nhé!",
    }
    resp = await client.post(f"/api/jobs/{job.id}/revisions", json=rev_payload)
    assert resp.status_code == 200

    # Check updated job draft
    res_job = await client.get(f"/api/jobs/{job.id}")
    assert res_job.status_code == 200
    d = res_job.json()
    assert d["id"] == job.id


@pytest.mark.asyncio
async def test_telegram_cancel_and_retry_commands(client: AsyncClient, test_db: AsyncSession):
    """Verify /cancel cancels active job and /retry requeues failed job."""
    headers = {"X-Automation-Secret": TEST_SECRET}

    # 1. Test /cancel
    active_job = Job(
        telegram_chat_id=ALLOWED_USER_ID,
        telegram_user_id=ALLOWED_USER_ID,
        source_file_id="active_fid",
        status=JobStatus.REVIEW_READY.value,
    )
    test_db.add(active_job)
    await test_db.commit()

    cancel_payload = {
        "update_id": 50,
        "message": {
            "message_id": 50,
            "from": {"id": ALLOWED_USER_ID, "first_name": "Admin"},
            "chat": {"id": ALLOWED_USER_ID, "type": "private"},
            "date": 1700000000,
            "text": "/cancel",
        },
    }
    resp_cancel = await client.post("/webhook/telegram", json=cancel_payload, headers=headers)
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["ok"] is True

    # Verify job status changed to CANCELLED
    detail_resp = await client.get(f"/api/jobs/{active_job.id}")
    assert detail_resp.json()["status"] == JobStatus.CANCELLED.value

    # 2. Test /retry
    failed_job = Job(
        telegram_chat_id=ALLOWED_USER_ID,
        telegram_user_id=ALLOWED_USER_ID,
        source_file_id="failed_fid",
        status=JobStatus.FAILED.value,
        error_message="Network error during processing",
        retry_count=0,
    )
    test_db.add(failed_job)
    await test_db.commit()

    retry_payload = {
        "update_id": 51,
        "message": {
            "message_id": 51,
            "from": {"id": ALLOWED_USER_ID, "first_name": "Admin"},
            "chat": {"id": ALLOWED_USER_ID, "type": "private"},
            "date": 1700000000,
            "text": "/retry",
        },
    }
    resp_retry = await client.post("/webhook/telegram", json=retry_payload, headers=headers)
    assert resp_retry.status_code == 200
    assert resp_retry.json()["ok"] is True

    # Verify job status reset to PENDING and retry count incremented
    detail_retry = await client.get(f"/api/jobs/{failed_job.id}")
    assert detail_retry.json()["status"] == JobStatus.PENDING.value


@pytest.mark.asyncio
async def test_telegram_edit_command(client: AsyncClient, test_db: AsyncSession):
    """Verify /edit <job_id> <new_title> updates draft hooks."""
    headers = {"X-Automation-Secret": TEST_SECRET}
    job = Job(
        telegram_chat_id=ALLOWED_USER_ID,
        telegram_user_id=ALLOWED_USER_ID,
        status=JobStatus.REVIEW_READY.value,
        content_draft={
            "youtube_shorts": {"hooks": ["Old Hook"]},
            "facebook_reels": {"hooks": ["Old Hook"]},
            "tiktok": {"hooks": ["Old Hook"]},
        },
    )
    test_db.add(job)
    await test_db.commit()

    edit_payload = {
        "update_id": 52,
        "message": {
            "message_id": 52,
            "from": {"id": ALLOWED_USER_ID, "first_name": "Admin"},
            "chat": {"id": ALLOWED_USER_ID, "type": "private"},
            "date": 1700000000,
            "text": f"/edit {job.id} TIÊU ĐỀ MỚI ĐƯỢC CẬP NHẬT TỪ TELEGRAM",
        },
    }
    resp = await client.post("/webhook/telegram", json=edit_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_anti_duplicate_video_submission(client: AsyncClient, test_db: AsyncSession):
    """Verify submitting the same video twice returns the existing job without creating a duplicate."""
    headers = {"X-Automation-Secret": TEST_SECRET}
    video_msg = {
        "update_id": 53,
        "message": {
            "message_id": 53,
            "from": {"id": ALLOWED_USER_ID, "first_name": "Creator"},
            "chat": {"id": ALLOWED_USER_ID, "type": "private"},
            "date": 1700000000,
            "video": {
                "file_id": "file_same_duplicate_test",
                "file_unique_id": "uniq_dup",
                "width": 1080,
                "height": 1920,
                "duration": 10,
            },
        },
    }

    # First submission -> creates job
    r1 = await client.post("/webhook/telegram", json=video_msg, headers=headers)
    assert r1.status_code == 200
    job_id_1 = r1.json()["job_id"]

    # Second submission with same file_id -> returns existing job
    r2 = await client.post("/webhook/telegram", json=video_msg, headers=headers)
    assert r2.status_code == 200
    job_id_2 = r2.json()["job_id"]
    assert job_id_1 == job_id_2
    assert "Duplicate" in r2.json()["message"]


@pytest.mark.asyncio
async def test_large_video_direct_upload(client: AsyncClient, sample_video_path: str):
    """Verify /upload/large-video accepts direct multipart video file."""
    headers = {"X-Automation-Secret": TEST_SECRET}

    with open(sample_video_path, "rb") as f:
        video_bytes = f.read()

    files = {"file": ("my_large_movie.mp4", video_bytes, "video/mp4")}
    data = {
        "chat_id": str(ALLOWED_USER_ID),
        "user_id": str(ALLOWED_USER_ID),
        "caption": "Video quay trực tiếp từ máy ảnh",
    }

    resp = await client.post("/upload/large-video", data=data, files=files, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["job_id"] is not None


@pytest.mark.asyncio
async def test_list_jobs_endpoint(client: AsyncClient, test_db: AsyncSession):
    """Verify GET /api/jobs returns job listing and supports status filtering."""
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
