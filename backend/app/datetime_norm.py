"""SQLite 读回的 datetime 常为 naive；序列化到 JSON 时需带 tz，前端才能正确换算本地时间。"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def assume_utc_if_naive(dt: datetime | None) -> datetime | None:
    """created_at 等在 Python 侧按 UTC 写入，库内无时区信息时视为 UTC。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def assume_shanghai_if_naive(dt: datetime | None) -> datetime | None:
    """matchday_start 等业务时刻按 Asia/Shanghai 生成，库内 naive 时视为上海本地。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=_SHANGHAI)
