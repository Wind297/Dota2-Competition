"""全局可调配置：扣分阈值等。存 SystemKV 表，运行时可改、持久化。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import SystemKV

DEDUCT_THRESHOLD_KEY = "deduct_threshold"
DEFAULT_DEDUCT_THRESHOLD = 8


def get_deduct_threshold(db: Session) -> int:
    """读取全局扣分阈值。SystemKV 无记录或值非法时返回默认值 8。"""
    row = db.get(SystemKV, DEDUCT_THRESHOLD_KEY)
    if row is None:
        return DEFAULT_DEDUCT_THRESHOLD
    try:
        return int(row.value)
    except (ValueError, TypeError):
        return DEFAULT_DEDUCT_THRESHOLD


def set_deduct_threshold(db: Session, value: int) -> None:
    """写入全局扣分阈值（upsert）。调用方负责 commit。"""
    row = db.get(SystemKV, DEDUCT_THRESHOLD_KEY)
    if row is None:
        db.add(SystemKV(key=DEDUCT_THRESHOLD_KEY, value=str(value)))
    else:
        row.value = str(value)
