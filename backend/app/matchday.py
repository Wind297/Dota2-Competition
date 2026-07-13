from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings


def get_tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def get_matchday_start(now: datetime | None = None) -> datetime:
    """比赛日窗口起点：当日 9:00（Asia/Shanghai）。

    切换节点为次日 14:00——即：
    - 14:00 起 → 当日 9:00 起的窗口
    - 14:00 之前 → 昨日 9:00 起的窗口

    这样比赛可以打到次日凌晨/中午都还归属前一日的比赛日。"""
    tz = get_tz()
    if now is None:
        now = datetime.now(tz)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    today = now.date()
    two_pm_today = datetime.combine(today, time(14, 0, 0), tzinfo=tz)
    if now >= two_pm_today:
        # 14:00 起归属当日窗口
        return datetime.combine(today, time(9, 0, 0), tzinfo=tz)
    # 14:00 之前归属昨日窗口
    yesterday = today - timedelta(days=1)
    return datetime.combine(yesterday, time(9, 0, 0), tzinfo=tz)
