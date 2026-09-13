import datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_PAUSE_MINUTES = 7 * 24 * 60
_DURATION_PATTERN = re.compile(r"^\s*(\d+)\s*([mhd]?)\s*$", re.IGNORECASE)


def parse_pause_duration(value: str) -> datetime.timedelta:
    """Parse 30, 30m, 2h, or 1d into a bounded duration."""
    match = _DURATION_PATTERN.fullmatch(value)
    if not match:
        raise ValueError("30m、2h、1d のように指定してください。")
    amount = int(match.group(1))
    unit = match.group(2).lower() or "m"
    minutes = amount * {"m": 1, "h": 60, "d": 24 * 60}[unit]
    if not 1 <= minutes <= MAX_PAUSE_MINUTES:
        raise ValueError("停止時間は1分以上、7日以内で指定してください。")
    return datetime.timedelta(minutes=minutes)


def get_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"不明なタイムゾーンです: {name}") from exc


def is_in_notification_window(now: datetime.datetime, start_hour: int, end_hour: int) -> bool:
    """Return whether now is in the configured window; equal hours mean all day."""
    if not 0 <= start_hour <= 23 or not 0 <= end_hour <= 23:
        raise ValueError("通知時間は0から23の間で指定してください。")
    if start_hour == end_hour:
        return True
    if start_hour < end_hour:
        return start_hour <= now.hour < end_hour
    return now.hour >= start_hour or now.hour < end_hour


def parse_stored_datetime(value: object) -> datetime.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)

