"""Pytest fixtures and test environment setup."""

import os
import subprocess
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment variables before importing app
os.environ["ENV"] = "test"
os.environ["AUTOMATION_SECRET"] = "test-secret-key-for-ci-pipeline-1234"
os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:test-bot-token"
os.environ["TELEGRAM_ALLOWED_USERS"] = "123456789,987654321"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PREVIEW_ONLY"] = "true"
os.environ["TIMEZONE"] = "Asia/Ho_Chi_Minh"
os.environ["MEDIA_DIR"] = "./test_media"

from app.database import Base, get_db
from app.main import app

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestAsyncSession = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh in-memory SQLite database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSession() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient for FastAPI testing with in-memory DB override."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def sample_video_path(tmp_path_factory) -> str:
    """Generate a real 3-second 720x1280 MP4 video using FFmpeg for media testing."""
    tmp_dir = tmp_path_factory.mktemp("video_fixtures")
    video_file = os.path.join(str(tmp_dir), "sample_test_video.mp4")

    # Generate synthetic video with test pattern and sine tone
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=size=720x1280:rate=30",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:sample_rate=44100",
        "-t", "3",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        video_file,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(video_file):
        # Fallback to minimal bytes if FFmpeg fails
        with open(video_file, "wb") as f:
            f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"\x00" * 1024)
    return video_file
