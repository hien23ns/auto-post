"""Application configuration module using Pydantic Settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core environment settings
    ENV: str = Field(default="development", description="Environment: development, staging, production, test")
    APP_NAME: str = Field(default="AI Auto Video Publisher", description="Service application name")
    APP_HOST: str = Field(default="0.0.0.0", description="FastAPI host")
    APP_PORT: int = Field(default=8000, description="FastAPI port")
    DEBUG: bool = Field(default=False, description="Debug mode")
    TIMEZONE: str = Field(default="Asia/Ho_Chi_Minh", description="Display and business timezone")

    # Security & Webhook authentication
    AUTOMATION_SECRET: str = Field(
        default="change-me-to-a-very-secure-random-token-32-chars-min",
        description="Shared secret key required in X-Automation-Secret header from Make.com",
    )

    # Telegram integration
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",
        description="Telegram bot token obtained from @BotFather",
    )
    TELEGRAM_ALLOWED_USERS: str = Field(
        default="",
        description="Comma-separated list of Telegram User IDs authorized to interact with bot",
    )

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/auto_post.db",
        description="Async database connection string",
    )

    # Google Gemini AI settings
    GEMINI_API_KEY: str = Field(default="", description="Google AI Studio Gemini API Key")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash", description="Configurable Gemini video analysis model")

    # Safety Preview Mode & Feature Flags
    PREVIEW_ONLY: bool = Field(
        default=True,
        description="When true, generate full thumbnails and drafts for Telegram preview without publishing to social networks",
    )
    ENABLE_YOUTUBE: bool = Field(default=False, description="Enable YouTube Shorts publication")
    ENABLE_FACEBOOK: bool = Field(default=False, description="Enable Facebook Fanpage Reels publication")
    ENABLE_TIKTOK: bool = Field(default=False, description="Enable TikTok publication")

    # YouTube Data API v3 (OAuth 2.0)
    YOUTUBE_CLIENT_ID: str | None = None
    YOUTUBE_CLIENT_SECRET: str | None = None
    YOUTUBE_REFRESH_TOKEN: str | None = None
    YOUTUBE_DEFAULT_PRIVACY: str = Field(default="private", description="Default privacy: private, unlisted, public")

    # Facebook Fanpage Reels (Meta Graph API)
    FACEBOOK_PAGE_ID: str | None = None
    FACEBOOK_PAGE_ACCESS_TOKEN: str | None = None

    # TikTok Content Posting API
    TIKTOK_CLIENT_KEY: str | None = None
    TIKTOK_CLIENT_SECRET: str | None = None
    TIKTOK_ACCESS_TOKEN: str | None = None
    TIKTOK_USE_DIRECT_POST: bool = Field(
        default=False,
        description="If false, use safe Upload-to-Inbox. If true, use Direct Post (requires TikTok app audit approval)",
    )

    # Media & Storage configuration
    STORAGE_TYPE: str = Field(default="local", description="Storage backend: local, s3, r2")
    MEDIA_DIR: str = Field(default="./media", description="Local directory for temporary media storage")
    RETENTION_DAYS: int = Field(default=7, description="Number of days to retain processed media before auto-deletion")

    # S3 / Cloudflare R2 compatibility
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str = Field(default="auto-post-videos")
    S3_REGION: str = Field(default="auto")

    @property
    def allowed_user_ids(self) -> list[int]:
        """Parse comma-separated user IDs into list of integers."""
        if not self.TELEGRAM_ALLOWED_USERS:
            return []
        ids = []
        for raw_id in self.TELEGRAM_ALLOWED_USERS.split(","):
            cleaned = raw_id.strip()
            if cleaned and cleaned.isdigit():
                ids.append(int(cleaned))
        return ids

    def is_user_allowed(self, user_id: int) -> bool:
        """Check if Telegram user ID is present in allowlist."""
        allowed = self.allowed_user_ids
        if not allowed:
            # If no allowed users configured, deny all for security
            return False
        return user_id in allowed

    def is_youtube_configured(self) -> bool:
        """Check if YouTube credentials are fully provided."""
        return bool(
            self.YOUTUBE_CLIENT_ID
            and self.YOUTUBE_CLIENT_SECRET
            and self.YOUTUBE_REFRESH_TOKEN
        )

    def is_facebook_configured(self) -> bool:
        """Check if Facebook Fanpage credentials are fully provided."""
        return bool(self.FACEBOOK_PAGE_ID and self.FACEBOOK_PAGE_ACCESS_TOKEN)

    def is_tiktok_configured(self) -> bool:
        """Check if TikTok credentials are fully provided."""
        return bool(
            self.TIKTOK_CLIENT_KEY
            and self.TIKTOK_CLIENT_SECRET
            and self.TIKTOK_ACCESS_TOKEN
        )


@lru_cache
def get_settings() -> Settings:
    """Cached singleton instance of application settings."""
    return Settings()
