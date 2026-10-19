"""Dedicated background worker executing video downloading, AI analysis, thumbnail studio, and social publishing."""

import asyncio
import logging
import os
import signal
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, init_db
from app.models import (
    Job,
    JobStatus,
    PlatformPost,
    PlatformType,
    PostStatus,
    WorkerHeartbeat,
    utc_now,
)
from app.publishers.facebook_publisher import facebook_publisher
from app.publishers.tiktok_publisher import tiktok_publisher
from app.publishers.youtube_publisher import youtube_publisher
from app.services.ffmpeg_service import ffmpeg_service
from app.services.gemini_service import gemini_service
from app.services.storage_service import storage_service
from app.services.telegram_service import telegram_service
from app.services.thumbnail_service import thumbnail_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [WORKER] %(name)s: %(message)s",
)
logger = logging.getLogger("auto_post.worker")
settings = get_settings()

WORKER_ID = f"worker_{os.getpid()}"
RUNNING = True


def handle_shutdown(signum, frame):
    """Graceful shutdown signal handler."""
    global RUNNING
    logger.info("Received shutdown signal. Stopping worker gracefully...")
    RUNNING = False


class BackgroundWorker:
    def __init__(self):
        self.last_cleanup_time = 0.0

    async def update_heartbeat(self, db: AsyncSession) -> None:
        """Record worker liveness heartbeat in database."""
        try:
            stmt = select(WorkerHeartbeat).where(WorkerHeartbeat.id == WORKER_ID)
            res = await db.execute(stmt)
            hb = res.scalar_one_or_none()

            if not hb:
                hb = WorkerHeartbeat(
                    id=WORKER_ID,
                    worker_name=f"Worker on {os.uname().nodename if hasattr(os, 'uname') else 'localhost'}",
                    last_heartbeat=utc_now(),
                    status="ACTIVE",
                )
                db.add(hb)
            else:
                hb.last_heartbeat = utc_now()
                hb.status = "ACTIVE"

            await db.commit()
        except Exception as e:
            logger.error(f"Failed to record heartbeat: {e}")

    async def run(self) -> None:
        """Main worker execution loop."""
        logger.info(f"Worker {WORKER_ID} started. Initializing database...")
        await init_db()

        while RUNNING:
            try:
                async with AsyncSessionLocal() as db:
                    # 1. Update Heartbeat
                    await self.update_heartbeat(db)

                    # 2. Hourly media retention cleanup
                    if time.time() - self.last_cleanup_time > 3600:
                        del_count = storage_service.cleanup_old_files()
                        if del_count > 0:
                            logger.info(f"Retention policy: cleaned up {del_count} old media files.")
                        self.last_cleanup_time = time.time()

                    # 3. Process Scheduled Jobs that reached their target time
                    await self.process_scheduled_jobs(db)

                    # 4. Process Pending Ingestion / Analysis Jobs
                    await self.process_pending_job(db)

                    # 5. Process Publishing Jobs
                    await self.process_publishing_job(db)

            except Exception as e:
                logger.error(f"Worker iteration loop error: {e}", exc_info=True)

            await asyncio.sleep(4.0)

        logger.info(f"Worker {WORKER_ID} stopped cleanly.")

    async def process_scheduled_jobs(self, db: AsyncSession) -> None:
        """Check for scheduled jobs whose time has arrived."""
        now = utc_now()
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.SCHEDULED.value)
            .where(Job.scheduled_at_utc <= now)
        )
        res = await db.execute(stmt)
        scheduled_jobs = res.scalars().all()

        for job in scheduled_jobs:
            logger.info(f"Job {job.id} reached scheduled time. Switching to PUBLISHING.")
            job.status = JobStatus.PUBLISHING.value
            job.locked_at = utc_now()
            job.locked_by = WORKER_ID
            job.lock_version += 1
            await db.commit()

    async def process_pending_job(self, db: AsyncSession) -> None:
        """Find and process the oldest pending video job."""
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.PENDING.value)
            .order_by(Job.created_at)
            .limit(1)
        )
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return

        logger.info(f"Acquired Job {job.id} for processing. Downloading & analyzing...")
        job.status = JobStatus.ANALYZING.value
        job.locked_at = utc_now()
        job.locked_by = WORKER_ID
        job.lock_version += 1
        await db.commit()

        try:
            # Step A: Download Video File from Telegram
            raw_file_name = job.source_file_name or "video.mp4"
            dest_raw_path = os.path.join(storage_service.raw_dir, f"{job.id}_{raw_file_name}")

            if job.source_file_id:
                await telegram_service.download_file(job.source_file_id, dest_raw_path)
            else:
                raise ValueError("Job is missing source_file_id")

            job.source_file_path = dest_raw_path
            job.file_checksum = storage_service.calculate_file_hash(dest_raw_path)

            # Step B: Probe Video Metadata with FFprobe
            meta = ffmpeg_service.probe_video(dest_raw_path)
            job.video_duration = meta["duration"]
            job.video_width = meta["width"]
            job.video_height = meta["height"]
            job.video_fps = meta["fps"]

            # Step C: Normalize Video to 1080x1920 MP4 H264
            norm_path = os.path.join(storage_service.processed_dir, f"{job.id}_normalized.mp4")
            try:
                ffmpeg_service.normalize_video_9_16(dest_raw_path, norm_path)
                final_video_path = norm_path
            except Exception as e:
                logger.warning(f"Normalization skipped or failed: {e}. Using raw video.")
                final_video_path = dest_raw_path

            # Step D: Multimodal Video Analysis via Gemini
            analysis = await gemini_service.analyze_video(final_video_path, job.video_duration or 15.0)
            job.analysis_raw = analysis.model_dump()
            job.evidence_log = [e.model_dump() for e in analysis.evidence_log]
            job.uncertain_warning = analysis.has_uncertain_facts
            job.content_draft = {
                "youtube_shorts": analysis.youtube_shorts.model_dump(),
                "facebook_reels": analysis.facebook_reels.model_dump(),
                "tiktok": analysis.tiktok.model_dump(),
            }

            # Step E: Extract Keyframes
            job_thumb_dir = os.path.join(storage_service.thumbnails_dir, job.id)
            os.makedirs(job_thumb_dir, exist_ok=True)

            timestamps = analysis.suggested_cover_timestamps
            if not timestamps:
                timestamps = ffmpeg_service.detect_scene_timestamps(final_video_path, max_points=3)

            extracted_frames = ffmpeg_service.extract_keyframes(final_video_path, timestamps, job_thumb_dir)
            if not extracted_frames:
                # If extraction failed, fallback to 1 frame at start
                fallback_frame = os.path.join(job_thumb_dir, "frame_0.jpg")
                ffmpeg_service.extract_frame_at_timestamp(final_video_path, 0.5, fallback_frame)
                extracted_frames = [fallback_frame]

            # Step F: Generate 3 Safe-Zone 9:16 Thumbnails
            main_title = analysis.youtube_shorts.hooks[0]
            cover_paths = thumbnail_service.generate_three_variants(
                extracted_frames, main_title, job_thumb_dir
            )
            job.cover_paths = cover_paths
            job.selected_cover_index = 0
            job.status = JobStatus.REVIEW_READY.value
            job.locked_at = None
            job.locked_by = None
            await db.commit()

            # Step G: Send Telegram Review Card + 3 Photo Covers
            card_text = telegram_service.format_job_preview_card({
                "id": job.id,
                "video_duration": job.video_duration,
                "selected_cover_index": job.selected_cover_index,
                "platforms_enabled": job.platforms_enabled,
                "scheduled_at_utc": job.scheduled_at_utc,
                "content_draft": job.content_draft,
                "uncertain_warning": job.uncertain_warning,
            })
            keyboard = telegram_service.build_review_inline_keyboard(
                job.id, job.selected_cover_index, job.platforms_enabled
            )

            # Send photo album of 3 covers first
            await telegram_service.send_media_group_photos(
                job.telegram_chat_id,
                cover_paths,
                caption="🖼️ <b>3 LỰA CHỌN ẢNH BÌA 9:16 SAFE-ZONE</b>",
            )
            # Send control card with buttons
            await telegram_service.send_message(job.telegram_chat_id, card_text, reply_markup=keyboard)

            logger.info(f"Job {job.id} preview sent to chat {job.telegram_chat_id} successfully.")

        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}", exc_info=True)
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            job.locked_at = None
            job.locked_by = None
            await db.commit()

            await telegram_service.send_message(
                job.telegram_chat_id,
                f"❌ <b>XỬ LÝ VIDEO THẤT BẠI</b>\n"
                f"Job ID: <code>{job.id}</code>\n"
                f"Nguyên nhân: {str(e)[:150]}\n"
                f"<i>Dùng lệnh /retry để thử lại.</i>",
            )

    async def process_publishing_job(self, db: AsyncSession) -> None:
        """Find and publish a job ready for multi-platform distribution."""
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.PUBLISHING.value)
            .limit(1)
        )
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return

        logger.info(f"Publishing Job {job.id} to platforms: {job.platforms_enabled}...")

        norm_path = os.path.join(storage_service.processed_dir, f"{job.id}_normalized.mp4")
        video_path = norm_path if os.path.exists(norm_path) else (job.source_file_path or "")
        cover_path = None
        if job.cover_paths and len(job.cover_paths) > job.selected_cover_index:
            cover_path = job.cover_paths[job.selected_cover_index]

        draft = job.content_draft or {}
        platforms = job.platforms_enabled or ["YOUTUBE", "FACEBOOK", "TIKTOK"]

        results = {}
        all_success = True

        for p in platforms:
            platform_upper = p.upper()
            post_record = PlatformPost(
                job_id=job.id,
                platform=platform_upper,
                status=PostStatus.PENDING.value,
            )
            db.add(post_record)
            await db.commit()

            res_obj = None
            if platform_upper == PlatformType.YOUTUBE.value:
                yt_draft = draft.get("youtube_shorts", {})
                title = yt_draft.get("hooks", ["Video ngắn #Shorts"])[0]
                caption = yt_draft.get("caption", "")
                tags = yt_draft.get("hashtags", ["#Shorts"])
                res_obj = await youtube_publisher.publish(video_path, title, caption, tags, cover_path)

            elif platform_upper == PlatformType.FACEBOOK.value:
                fb_draft = draft.get("facebook_reels", {})
                title = fb_draft.get("hooks", ["Reels hay"])[0]
                caption = fb_draft.get("caption", "")
                tags = fb_draft.get("hashtags", ["#Reels"])
                res_obj = await facebook_publisher.publish(video_path, title, caption, tags, cover_path)

            elif platform_upper == PlatformType.TIKTOK.value:
                tt_draft = draft.get("tiktok", {})
                title = tt_draft.get("hooks", ["Video TikTok"])[0]
                caption = tt_draft.get("caption", "")
                tags = tt_draft.get("hashtags", ["#fyp"])
                res_obj = await tiktok_publisher.publish(video_path, title, caption, tags, cover_path)

            if res_obj:
                post_record.status = res_obj.status.value
                post_record.remote_post_id = res_obj.remote_id
                post_record.remote_url = res_obj.remote_url
                post_record.error_detail = res_obj.error
                if res_obj.success:
                    post_record.published_at = utc_now()
                else:
                    all_success = False
                results[platform_upper] = res_obj

            await db.commit()

        job.status = JobStatus.PUBLISHED.value if all_success else JobStatus.NEEDS_REVIEW.value
        job.locked_at = None
        job.locked_by = None
        await db.commit()

        # Send Telegram publication summary
        lines = [f"🎉 <b>KẾT QUẢ XUẤT BẢN VIDEO ({job.id})</b>\n"]
        for p, r in results.items():
            if r.success:
                lines.append(f"✅ <b>{p}:</b> <a href='{r.remote_url}'>Xem bài đăng</a> ({r.status.value})")
            else:
                lines.append(f"⚠️ <b>{p}:</b> {r.status.value} - <i>{r.error or 'Lỗi'}</i>")

        await telegram_service.send_message(job.telegram_chat_id, "\n".join(lines))
        logger.info(f"Job {job.id} publication finished. Status: {job.status}")


def main():
    """Worker entrypoint."""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    worker = BackgroundWorker()
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
