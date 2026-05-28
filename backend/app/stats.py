from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Match, MatchPlayer


def load_matchday_stats(
    db: Session, matchday_start: datetime, season_id: int | None = None
) -> dict[int, tuple[int, int]]:
    """返回 player_id -> (matches_played, matches_won)。可选限定 season_id。"""
    stmt = (
        select(
            MatchPlayer.player_id,
            func.count(MatchPlayer.id).label("played"),
            func.sum(case((MatchPlayer.is_winner.is_(True), 1), else_=0)).label("won"),
        )
        .join(Match)
        .where(Match.matchday_start == matchday_start)
        .group_by(MatchPlayer.player_id)
    )
    if season_id is not None:
        stmt = stmt.where(Match.season_id == season_id)
    rows = db.execute(stmt).all()
    out: dict[int, tuple[int, int]] = {}
    for pid, played, won in rows:
        out[int(pid)] = (int(played or 0), int(won or 0))
    return out
