"""积分变更审计写入 helper。所有写 SeasonPlayer.current_score 的位置都应通过此函数
同步写一条 ScoreAuditLog，保证明细加总 = 当前积分，账目可追溯。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ScoreAuditLog


def write_score_audit(
    db: Session,
    *,
    season_id: int,
    player_id: int,
    delta: int,
    reason: str,
    match_id: int | None = None,
    note: str | None = None,
) -> None:
    """写一条积分审计日志。delta == 0 时直接跳过避免噪音。"""
    if delta == 0:
        return
    db.add(
        ScoreAuditLog(
            season_id=season_id,
            player_id=player_id,
            delta=delta,
            reason=reason,
            match_id=match_id,
            note=note,
        )
    )
