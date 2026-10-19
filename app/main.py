"""FastAPI Web Application: Webhook Receiver, Health Monitoring, and Job Management."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, init_db
from app.models import (
    Job,
    JobRevision,
    JobStatus,
    WorkerHeartbeat,
    utc_now,
)
from app.schemas import (
    HealthResponse,
    JobDetailResponse,
    JobRevisionCreate,
    TelegramCallbackQuery,
    TelegramUpdate,
    WebhookResponse,
)
from app.services.scheduler_service import (
    format_vn_time,
    get_current_time_vn,
    parse_schedule_expression,
)
from app.services.telegram_service import telegram_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("auto_post.api")
settings = get_settings()

START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    logger.info("Initializing database schemas...")
    await init_db()
    logger.info("AI Auto Video Publisher API ready.")
    yield
    logger.info("Shutting down API service.")


app = FastAPI(
    title=settings.APP_NAME,
    description="24/7 AI-powered video analysis, thumbnail generator, and multi-platform social publisher",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# AUTHENTICATION DEPENDENCY FOR MAKE.COM WEBHOOK
# ==============================================================================

async def verify_automation_secret(
    x_automation_secret: str | None = Header(None, alias="X-Automation-Secret"),
) -> None:
    """Validate shared secret key from Make.com gateway."""
    if not x_automation_secret or x_automation_secret != settings.AUTOMATION_SECRET:
        logger.warning("Unauthorized webhook request: missing or invalid X-Automation-Secret header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing X-Automation-Secret header.",
        )


# ==============================================================================
# HEALTH CHECK & MONITORING ENDPOINT
# ==============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint checking Database connectivity and Worker Heartbeat freshness."""
    db_status = "connected"
    worker_status = "active"

    # 1. Check DB Connection
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "down"

    # 2. Check Worker Heartbeat
    try:
        stmt = select(WorkerHeartbeat).order_by(desc(WorkerHeartbeat.last_heartbeat)).limit(1)
        res = await db.execute(stmt)
        hb = res.scalar_one_or_none()

        if not hb:
            worker_status = "no_heartbeat_recorded"
        else:
            diff_seconds = (utc_now() - hb.last_heartbeat).total_seconds()
            if diff_seconds > 90.0:
                worker_status = f"stale_{int(diff_seconds)}s_ago"
            else:
                worker_status = "active"
    except Exception as e:
        logger.error(f"Worker heartbeat check failed: {e}")
        worker_status = "unknown"

    uptime = round(time.time() - START_TIME, 2)
    is_healthy = (db_status == "connected") and (not worker_status.startswith("stale"))

    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": db_status,
                "worker_heartbeat": worker_status,
                "uptime_seconds": uptime,
                "timezone": settings.TIMEZONE,
            },
        )

    return HealthResponse(
        status="healthy",
        database=db_status,
        worker_heartbeat=worker_status,
        uptime_seconds=uptime,
        timezone=settings.TIMEZONE,
    )


# ==============================================================================
# TELEGRAM & MAKE.COM WEBHOOK ROUTER
# ==============================================================================

@app.post("/webhook/telegram", response_model=WebhookResponse)
async def telegram_webhook(
    update: TelegramUpdate,
    _auth: None = Depends(verify_automation_secret),
    db: AsyncSession = Depends(get_db),
):
    """Single Webhook endpoint handling updates from Make.com."""
    # 1. Process Callback Query (User clicked inline keyboard button)
    if update.callback_query:
        return await handle_callback_query(update.callback_query, db)

    # 2. Process Message (Command or Video)
    if update.message:
        return await handle_message(update.message, db)

    return WebhookResponse(ok=True, message="Update ignored (no message or callback)")


async def handle_message(msg: Any, db: AsyncSession) -> WebhookResponse:
    """Handle text commands and incoming video files."""
    user = msg.from_user
    chat = msg.chat

    if not user:
        return WebhookResponse(ok=False, message="Missing from_user")

    # Security check: User allowlist
    if not settings.is_user_allowed(user.id):
        logger.warning(f"Unauthorized Telegram User ID {user.id} ({user.username}). Rejected.")
        await telegram_service.send_message(
            chat.id,
            "⛔ <b>TRUY CẬP BỊ TỪ CHỐI</b>\nTài khoản Telegram của bạn không nằm trong danh sách được cấp quyền sử dụng hệ thống này.",
        )
        return WebhookResponse(ok=False, message="User not in allowlist")

    # Command Handling
    if msg.text and msg.text.startswith("/"):
        cmd = msg.text.split()[0].lower()
        return await handle_command(cmd, msg, db)

    # Check for incoming Video or Video Document
    video_file_id = None
    file_name = "video.mp4"
    duration = 0
    width = 1080
    height = 1920

    if msg.video:
        video_file_id = msg.video.file_id
        file_name = msg.video.file_name or "video.mp4"
        duration = msg.video.duration
        width = msg.video.width
        height = msg.video.height
    elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("video/"):
        video_file_id = msg.document.file_id
        file_name = msg.document.file_name or "video.mp4"

    if video_file_id:
        logger.info(f"Received video from user {user.id} (file_id: {video_file_id}). Enqueueing job.")

        # Create Durable Job in database
        job = Job(
            telegram_chat_id=chat.id,
            telegram_user_id=user.id,
            source_file_id=video_file_id,
            source_file_name=file_name,
            video_duration=float(duration),
            video_width=width,
            video_height=height,
            status=JobStatus.PENDING.value,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        # Notify user on Telegram
        await telegram_service.send_message(
            chat.id,
            f"📥 <b>ĐÃ TIẾP NHẬN VIDEO</b>\n"
            f"🆔 Job ID: <code>{job.id}</code>\n"
            f"⚡ Đang nạp video vào hàng đợi xử lý AI và FFmpeg Studio...",
        )
        return WebhookResponse(ok=True, message="Job enqueued", job_id=job.id)

    # General chat reply
    await telegram_service.send_message(
        chat.id,
        "👋 Gửi cho tôi một video (MP4) để phân tích bằng Gemini và tạo 3 ảnh bìa thumbnail tự động!",
    )
    return WebhookResponse(ok=True, message="Sent instructions")


async def handle_command(cmd: str, msg: Any, db: AsyncSession) -> WebhookResponse:
    """Process bot commands."""
    chat_id = msg.chat.id

    if cmd in ("/start", "/help"):
        help_text = (
            "🤖 <b>AI AUTO VIDEO PUBLISHER 24/7</b>\n\n"
            "<b>Các lệnh hỗ trợ:</b>\n"
            "• Gửi file video: Tự động phân tích và tạo 3 ảnh bìa\n"
            "• /status - Kiểm tra trạng thái hệ thống và worker\n"
            "• /queue - Xem danh sách video đang chờ xử lý\n"
            "• /history - Xem các video đã xuất bản gần nhất\n"
            "• /cancel - Hủy công việc hiện tại\n"
            "• /retry - Thử lại công việc gần nhất bị lỗi\n\n"
            "🔒 <i>Hệ thống chạy 24/7 trên VPS độc lập, tự động hóa an toàn.</i>"
        )
        await telegram_service.send_message(chat_id, help_text)
        return WebhookResponse(ok=True, message="Sent help")

    elif cmd == "/status":
        now_vn = get_current_time_vn().strftime("%H:%M:%S %d/%m/%Y (GMT+7)")
        status_text = (
            f"📊 <b>TRẠNG THÁI HỆ THỐNG 24/7</b>\n"
            f"🕒 Giờ hệ thống: <code>{now_vn}</code>\n"
            f"🛡️ Môi trường: <code>{settings.ENV}</code>\n"
            f"🤖 Gemini Model: <code>{settings.GEMINI_MODEL}</code>\n"
            f"⚠️ Chế độ an toàn (PREVIEW_ONLY): <b>{'BẬT' if settings.PREVIEW_ONLY else 'TẮT'}</b>"
        )
        await telegram_service.send_message(chat_id, status_text)
        return WebhookResponse(ok=True, message="Sent status")

    elif cmd == "/queue":
        stmt = (
            select(Job)
            .where(Job.status.in_([JobStatus.PENDING.value, JobStatus.ANALYZING.value, JobStatus.SCHEDULED.value]))
            .order_by(Job.created_at)
            .limit(10)
        )
        res = await db.execute(stmt)
        jobs = res.scalars().all()
        if not jobs:
            await telegram_service.send_message(chat_id, "📭 Hiện không có video nào trong hàng đợi.")
        else:
            lines = ["📋 <b>DANH SÁCH VIDEO ĐANG CHỜ:</b>\n"]
            for j in jobs:
                lines.append(f"• <code>{j.id[:8]}</code> | Trạng thái: <b>{j.status}</b> | Lịch: {format_vn_time(j.scheduled_at_utc)}")
            await telegram_service.send_message(chat_id, "\n".join(lines))
        return WebhookResponse(ok=True, message="Sent queue")

    elif cmd == "/history":
        stmt = (
            select(Job)
            .where(Job.status.in_([JobStatus.PUBLISHED.value, JobStatus.FAILED.value]))
            .order_by(desc(Job.created_at))
            .limit(5)
        )
        res = await db.execute(stmt)
        jobs = res.scalars().all()
        if not jobs:
            await telegram_service.send_message(chat_id, "📜 Chưa có lịch sử bài đăng nào.")
        else:
            lines = ["📜 <b>LỊCH SỬ XUẤT BẢN GẦN ĐÂY:</b>\n"]
            for j in jobs:
                icon = "✅" if j.status == JobStatus.PUBLISHED.value else "❌"
                lines.append(f"{icon} <code>{j.id[:8]}</code>: {j.status} ({format_vn_time(j.updated_at)})")
            await telegram_service.send_message(chat_id, "\n".join(lines))
        return WebhookResponse(ok=True, message="Sent history")

    return WebhookResponse(ok=True, message="Command recognized")


async def handle_callback_query(cb: TelegramCallbackQuery, db: AsyncSession) -> WebhookResponse:
    """Handle interactive inline keyboard callbacks from Telegram."""
    data = cb.data
    user = cb.from_user

    # Security check: User allowlist
    if not settings.is_user_allowed(user.id):
        await telegram_service.answer_callback_query(cb.id, "Từ chối truy cập!", show_alert=True)
        return WebhookResponse(ok=False, message="User not in allowlist")

    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "job":
        return WebhookResponse(ok=False, message="Unknown callback format")

    job_id = parts[1]
    action = parts[2]

    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        await telegram_service.answer_callback_query(cb.id, "Không tìm thấy công việc này!", show_alert=True)
        return WebhookResponse(ok=False, message="Job not found")

    # 1. Chọn ảnh bìa
    if action == "cover" and len(parts) >= 4:
        cover_idx = int(parts[3])
        job.selected_cover_index = cover_idx
        await db.commit()
        await telegram_service.answer_callback_query(cb.id, f"Đã chọn ảnh bìa #{cover_idx + 1}")

    # 2. Bật/Tắt nền tảng
    elif action == "toggle" and len(parts) >= 4:
        platform = parts[3].upper()
        current = list(job.platforms_enabled or [])
        if platform in current:
            current.remove(platform)
        else:
            current.append(platform)
        job.platforms_enabled = current
        await db.commit()
        await telegram_service.answer_callback_query(cb.id, f"Đã cập nhật trạng thái {platform}")

    # 3. Phê duyệt đăng ngay (Approve Publish)
    elif action == "approve":
        if job.status == JobStatus.PUBLISHED.value:
            await telegram_service.answer_callback_query(cb.id, "Video này đã được đăng trước đó!", show_alert=True)
            return WebhookResponse(ok=True, message="Already published")

        # Anti-double-post lock
        job.status = JobStatus.PUBLISHING.value
        job.locked_at = utc_now()
        job.locked_by = f"user_{user.id}"
        job.lock_version += 1
        await db.commit()

        await telegram_service.answer_callback_query(cb.id, "🚀 Bắt đầu xuất bản đa nền tảng...")
        if cb.message:
            await telegram_service.send_message(
                cb.message.chat.id,
                f"🚀 <b>ĐANG XUẤT BẢN VIDEO</b>\n"
                f"Job: <code>{job.id}</code> đang được nộp lên các nền tảng mạng xã hội...",
            )

    # 4. Hủy công việc
    elif action == "cancel":
        job.status = JobStatus.CANCELLED.value
        await db.commit()
        await telegram_service.answer_callback_query(cb.id, "Đã hủy công việc!")
        if cb.message:
            await telegram_service.send_message(cb.message.chat.id, f"❌ Đã hủy công việc <code>{job.id}</code>.")

    # 5. Lên lịch hẹn giờ
    elif action == "schedule":
        # Default schedule +2h for quick testing
        scheduled_utc = parse_schedule_expression("+2h")
        job.scheduled_at_utc = scheduled_utc
        job.status = JobStatus.SCHEDULED.value
        await db.commit()
        vn_str = format_vn_time(scheduled_utc)
        await telegram_service.answer_callback_query(cb.id, f"Đã lên lịch đăng lúc {vn_str}")

    return WebhookResponse(ok=True, message="Callback handled")


# ==============================================================================
# REST API ENDPOINTS FOR JOB INSPECTION & REVISION
# ==============================================================================

@app.get("/api/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job_detail(job_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch complete job state and audit details."""
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobDetailResponse(
        id=job.id,
        telegram_chat_id=job.telegram_chat_id,
        telegram_user_id=job.telegram_user_id,
        status=job.status,
        uncertain_warning=job.uncertain_warning,
        video_duration=job.video_duration,
        selected_cover_index=job.selected_cover_index,
        cover_paths=job.cover_paths,
        platforms_enabled=job.platforms_enabled,
        scheduled_at_utc=job.scheduled_at_utc,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@app.post("/api/jobs/{job_id}/revisions")
async def create_job_revision(
    job_id: str,
    rev_in: JobRevisionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Save an edited revision of hook/caption/hashtags."""
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    rev = JobRevision(
        job_id=job.id,
        platform=rev_in.platform,
        hook=rev_in.hook,
        caption=rev_in.caption,
        hashtags=rev_in.hashtags,
        cta=rev_in.cta,
    )
    db.add(rev)

    # Update current draft
    draft = dict(job.content_draft or {})
    platform_key = rev_in.platform.lower()
    if platform_key in draft:
        if rev_in.caption:
            draft[platform_key]["caption"] = rev_in.caption
        if rev_in.hook:
            draft[platform_key]["hooks"] = [rev_in.hook] + draft[platform_key].get("hooks", [])[1:]
        if rev_in.hashtags:
            draft[platform_key]["hashtags"] = rev_in.hashtags
    job.content_draft = draft

    await db.commit()
    return {"ok": True, "message": "Revision saved"}
