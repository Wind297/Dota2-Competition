from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings


def get_tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def get_matchday_start(now: datetime | None = None) -> datetime:
    """比赛日窗口起点：当日 9:00（Asia/Shanghai）；当日 9:00 前归属昨日 9:00 起的窗口。"""
    tz = get_tz()
    if now is None:
        now = datetime.now(tz)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    today = now.date()
    nine_am_today = datetime.combine(today, time(9, 0, 0), tzinfo=tz)
    if now >= nine_am_today:
        return nine_am_today
    yesterday = today - timedelta(days=1)
    return datetime.combine(yesterday, time(9, 0, 0), tzinfo=tz)
