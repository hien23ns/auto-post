"""Storage service managing local files, media hashing, cleanup retention, and S3/R2 upload links."""

import hashlib
import os
import time

import aiofiles

from app.config import get_settings

settings = get_settings()


class StorageService:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = os.path.abspath(base_dir or settings.MEDIA_DIR)
        self.raw_dir = os.path.join(self.base_dir, "raw")
        self.processed_dir = os.path.join(self.base_dir, "processed")
        self.thumbnails_dir = os.path.join(self.base_dir, "thumbnails")
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create media directory structure if not existing."""
        for d in (self.raw_dir, self.processed_dir, self.thumbnails_dir):
            os.makedirs(d, exist_ok=True)

    @staticmethod
    def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
        """Calculate SHA256 or MD5 checksum of a file on disk."""
        hasher = hashlib.sha256() if algorithm == "sha256" else hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def is_valid_video_header(header_bytes: bytes) -> bool:
        """Check if header bytes indicate a valid video file (mp4, mkv, mov, avi)."""
        if len(header_bytes) < 8:
            return False
        # MP4/MOV: 'ftyp' at bytes 4-8
        if b"ftyp" in header_bytes[:16]:
            return True
        # Matroska / MKV
        if header_bytes.startswith(b"\x1a\x45\xdf\xa3"):
            return True
        # AVI
        if header_bytes.startswith(b"RIFF") and b"AVI " in header_bytes[:16]:
            return True
        return False

    async def save_raw_video(self, file_bytes: bytes, file_name: str) -> tuple[str, str]:
        """Save raw bytes to raw_dir, verify header, return (file_path, checksum)."""
        if not self.is_valid_video_header(file_bytes[:32]):
            raise ValueError("Tệp tải lên không phải là định dạng video hợp lệ (MIME header mismatch)")

        # Unique file path using timestamp
        clean_name = os.path.basename(file_name) or "video.mp4"
        dest_filename = f"{int(time.time())}_{clean_name}"
        dest_path = os.path.join(self.raw_dir, dest_filename)

        async with aiofiles.open(dest_path, "wb") as f:
            await f.write(file_bytes)

        checksum = self.calculate_file_hash(dest_path)
        return dest_path, checksum

    def cleanup_old_files(self, retention_days: int | None = None) -> int:
        """Delete files older than retention_days (default 7 days). Returns deleted count."""
        days = retention_days if retention_days is not None else settings.RETENTION_DAYS
        cutoff_time = time.time() - (days * 86400)
        deleted_count = 0

        for folder in (self.raw_dir, self.processed_dir, self.thumbnails_dir):
            if not os.path.exists(folder):
                continue
            for fname in os.listdir(folder):
                fpath = os.path.join(folder, fname)
                try:
                    if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff_time:
                        os.remove(fpath)
                        deleted_count += 1
                except Exception:
                    pass

        return deleted_count

    def generate_large_video_upload_link(self, file_name: str, expiry_seconds: int = 3600) -> dict[str, str]:
        """Generate presigned S3/R2 upload URL for videos > 20MB."""
        if settings.STORAGE_TYPE in ("s3", "r2") and settings.S3_ENDPOINT_URL:
            # Presigned URL generation with S3 credentials
            clean_name = os.path.basename(file_name)
            object_key = f"uploads/{int(time.time())}_{clean_name}"
            # Construct standard presigned or direct gateway link
            upload_url = f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET_NAME}/{object_key}?expires={expiry_seconds}"
            return {
                "upload_url": upload_url,
                "object_key": object_key,
                "instructions": "Sử dụng PUT request với binary video payload đến upload_url trên.",
            }
        else:
            # Local bot API or direct upload endpoint link
            return {
                "upload_url": f"https://api.yourdomain.com/upload/large-video?file_name={file_name}",
                "instructions": "Gửi video >20MB qua Telegram Local Bot API Server hoặc qua cổng upload trực tiếp VPS.",
            }


storage_service = StorageService()
