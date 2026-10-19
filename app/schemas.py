"""Pydantic schemas for API validation, Gemini AI structured outputs, and Telegram events."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ==============================================================================
# GEMINI AI STRUCTURED OUTPUT SCHEMAS (ZERO-HALLUCINATION EVIDENCE)
# ==============================================================================

class EvidenceItem(BaseModel):
    timestamp: str = Field(description="Mốc thời gian xuất hiện sự kiện trong video (định dạng MM:SS hoặc SS)")
    description: str = Field(description="Mô tả sự kiện thực tế quan sát được trong video")
    certainty_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Độ chắc chắn của chi tiết (0.0 đến 1.0)")
    is_verified: bool = Field(default=True, description="Được chứng minh bởi hình ảnh/âm thanh/chữ thực trong video")


class PlatformContent(BaseModel):
    hooks: list[str] = Field(description="3 tùy chọn hook/tiêu đề mở đầu hấp dẫn, không clickbait sai sự thật")
    caption: str = Field(description="Nội dung caption đầy đủ chuẩn phong cách nền tảng, đúng chính tả tiếng Việt")
    hashtags: list[str] = Field(description="5-7 hashtags tối ưu SEO, tự nhiên, không spam")
    cta: str = Field(description="Lời kêu gọi hành động (CTA) phù hợp")

    @field_validator("hooks")
    @classmethod
    def validate_hooks_count(cls, v: list[str]) -> list[str]:
        if len(v) < 1:
            raise ValueError("Cần ít nhất 1 hook/tiêu đề")
        return v


class GeminiVideoAnalysis(BaseModel):
    summary: str = Field(description="Tóm tắt ngắn gọn nội dung cốt lõi của video")
    key_events: list[str] = Field(description="Các sự kiện chính theo trình tự diễn biến")
    transcript_summary: str = Field(default="", description="Nội dung lời thoại/thuyết minh quan trọng")
    ocr_elements: list[str] = Field(default_factory=list, description="Chữ xuất hiện trên khung hình video")
    evidence_log: list[EvidenceItem] = Field(description="Danh sách bằng chứng kèm mốc thời gian xác thực")
    has_uncertain_facts: bool = Field(
        default=False,
        description="True nếu có yếu tố suy đoán hoặc thiếu bằng chứng xác thực trong video, yêu cầu người duyệt",
    )
    suggested_cover_timestamps: list[float] = Field(
        default_factory=lambda: [1.0, 3.0, 5.0],
        description="3 mốc thời gian (giây) có khung hình ấn tượng nhất để làm ảnh bìa thumbnail",
    )
    youtube_shorts: PlatformContent = Field(description="Nội dung tối ưu cho YouTube Shorts (kèm #Shorts)")
    facebook_reels: PlatformContent = Field(description="Nội dung tối ưu cho Facebook Fanpage Reels")
    tiktok: PlatformContent = Field(description="Nội dung tối ưu cho TikTok")


# ==============================================================================
# TELEGRAM BOT & WEBHOOK SCHEMAS
# ==============================================================================

class TelegramUser(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str = ""
    last_name: str | None = None
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str = "private"
    title: str | None = None
    username: str | None = None


class TelegramVideo(BaseModel):
    file_id: str
    file_unique_id: str
    width: int = 1080
    height: int = 1920
    duration: int = 0
    file_name: str | None = "video.mp4"
    mime_type: str | None = "video/mp4"
    file_size: int | None = 0


class TelegramDocument(BaseModel):
    file_id: str
    file_unique_id: str
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = 0


class TelegramMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: int
    from_user: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat
    date: int = 0
    text: str | None = None
    caption: str | None = None
    video: TelegramVideo | None = None
    document: TelegramDocument | None = None


class TelegramCallbackQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    from_user: TelegramUser = Field(alias="from")
    message: TelegramMessage | None = None
    data: str


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None
    callback_query: TelegramCallbackQuery | None = None


# ==============================================================================
# REVISION, SETTINGS & JOB SCHEMAS
# ==============================================================================

class JobRevisionCreate(BaseModel):
    platform: str
    hook: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    cta: str | None = None


class JobDetailResponse(BaseModel):
    id: str
    telegram_chat_id: int
    telegram_user_id: int
    status: str
    uncertain_warning: bool
    video_duration: float | None = None
    selected_cover_index: int
    cover_paths: list[str] | None = None
    platforms_enabled: list[str] | None = None
    scheduled_at_utc: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class WebhookResponse(BaseModel):
    ok: bool = True
    message: str
    job_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    worker_heartbeat: str
    uptime_seconds: float
    timezone: str
