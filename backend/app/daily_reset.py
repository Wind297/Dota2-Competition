from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.matchday import get_matchday_start
from app.models import Player, SystemKV


def maybe_reset_daily_online(db: Session, now: datetime | None = None) -> None:
    """每个新比赛日将全员 is_online 置为 true（以 matchday_start 变化为准）。"""
    md = get_matchday_start(now)
    md_iso = md.isoformat()

    row = db.get(SystemKV, "last_online_reset_matchday")
    if row is None:
        db.add(SystemKV(key="last_online_reset_matchday", value=md_iso))
        db.execute(update(Player).values(is_online=True))
        db.commit()
        return

    try:
        last = datetime.fromisoformat(row.value)
    except ValueError:
        row.value = md_iso
        db.execute(update(Player).values(is_online=True))
        db.commit()
        return

    if last.tzinfo is None:
        last = last.replace(tzinfo=md.tzinfo)
    if last < md:
        db.execute(update(Player).values(is_online=True))
        row.value = md_iso
        db.commit()
