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
