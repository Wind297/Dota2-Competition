from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Match, MatchPlayer, PlayerTag, Tag
from app.schemas import TopTagItem


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


def load_top_tags_for_season(
    db: Session, season_id: int, top_n: int = 5
) -> dict[int, list[TopTagItem]]:
    """返回 player_id -> 该选手在本赛季得票最多的前 N 个标签（带 label）。"""
    rows = db.execute(
        select(
            PlayerTag.player_id,
            PlayerTag.tag_id,
            func.count(PlayerTag.id).label("cnt"),
        )
        .where(PlayerTag.season_id == season_id)
        .group_by(PlayerTag.player_id, PlayerTag.tag_id)
    ).all()
    if not rows:
        return {}

    tag_ids = {int(r[1]) for r in rows}
    tag_labels: dict[int, str] = {}
    if tag_ids:
        for t in db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all():
            tag_labels[t.id] = t.label

    by_player: dict[int, list[tuple[int, int]]] = {}
    for pid, tid, cnt in rows:
        by_player.setdefault(int(pid), []).append((int(tid), int(cnt)))
    out: dict[int, list[TopTagItem]] = {}
    for pid, items in by_player.items():
        items.sort(key=lambda x: (-x[1], x[0]))
        out[pid] = [
            TopTagItem(tag_id=tid, label=tag_labels.get(tid, f"#{tid}"), count=cnt)
            for tid, cnt in items[:top_n]
        ]
    return out
