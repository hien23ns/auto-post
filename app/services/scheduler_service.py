"""Scheduler service for timezone conversions and natural schedule parsing."""

import re
from datetime import UTC, datetime, timedelta

import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")


def get_current_time_vn() -> datetime:
    """Get current datetime in Asia/Ho_Chi_Minh timezone."""
    return datetime.now(VN_TZ)


def get_current_time_utc() -> datetime:
    """Get current datetime in UTC."""
    return datetime.now(UTC)


def utc_to_vn(dt: datetime | None) -> datetime | None:
    """Convert a UTC datetime to Asia/Ho_Chi_Minh timezone."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(VN_TZ)


def vn_to_utc(dt: datetime) -> datetime:
    """Convert an Asia/Ho_Chi_Minh datetime to UTC."""
    if dt.tzinfo is None:
        dt = VN_TZ.localize(dt)
    return dt.astimezone(UTC)


def format_vn_time(dt: datetime | None) -> str:
    """Format datetime into friendly Vietnamese display string."""
    if not dt:
        return "Chưa đặt lịch"
    vn_dt = utc_to_vn(dt)
    return vn_dt.strftime("%H:%M:%S %d/%m/%Y (GMT+7)")


def parse_schedule_expression(expr: str, base_time: datetime | None = None) -> datetime | None:
    """Parse schedule expression into UTC datetime.

    Supports:
    - "+30m", "+2h", "+1d" (relative offset)
    - "HH:MM" (e.g. "20:30", scheduled for today or tomorrow if passed)
    - "mai HH:MM" (e.g. "mai 08:00")
    - "YYYY-MM-DD HH:MM" (ISO format)
    """
    expr = expr.strip().lower()
    now_vn = get_current_time_vn() if base_time is None else utc_to_vn(base_time)

    # 1. Relative offset (+30m, +2h, +1d)
    rel_match = re.match(r"^\+(\d+)\s*(m|h|d|min|hour|day)$", expr)
    if rel_match:
        val = int(rel_match.group(1))
        unit = rel_match.group(2)
        delta = timedelta(minutes=val) if unit in ("m", "min") else (
            timedelta(hours=val) if unit in ("h", "hour") else timedelta(days=val)
        )
        scheduled_vn = now_vn + delta
        return vn_to_utc(scheduled_vn)

    # 2. "mai HH:MM" (Tomorrow at HH:MM)
    tomorrow_match = re.match(r"^mai\s+(\d{1,2}):(\d{2})$", expr)
    if tomorrow_match:
        hour = int(tomorrow_match.group(1))
        minute = int(tomorrow_match.group(2))
        tomorrow_vn = now_vn + timedelta(days=1)
        scheduled_vn = tomorrow_vn.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return vn_to_utc(scheduled_vn)

    # 3. "HH:MM" (Today or tomorrow if time already passed)
    time_match = re.match(r"^(\d{1,2}):(\d{2})$", expr)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        scheduled_vn = now_vn.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_vn <= now_vn:
            scheduled_vn += timedelta(days=1)
        return vn_to_utc(scheduled_vn)

    # 4. "YYYY-MM-DD HH:MM" or "DD/MM/YYYY HH:MM"
    for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(expr, fmt)
            scheduled_vn = VN_TZ.localize(parsed)
            return vn_to_utc(scheduled_vn)
        except ValueError:
            continue

    return None
