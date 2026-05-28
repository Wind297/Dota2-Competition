"""赛季工具：查询当前赛季、SeasonPlayer 解析。"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Season, SeasonPlayer, SeasonStatus


def get_active_season(db: Session) -> Season:
    """获取当前进行中的赛季。无活跃赛季时抛 400。"""
    s = db.scalars(
        select(Season).where(Season.status == SeasonStatus.active).order_by(Season.id.desc())
    ).first()
    if not s:
        raise HTTPException(status_code=400, detail="当前没有进行中的赛季，请先创建一个赛季")
    return s


def get_active_season_or_none(db: Session) -> Season | None:
    return db.scalars(
        select(Season).where(Season.status == SeasonStatus.active).order_by(Season.id.desc())
    ).first()


def get_or_create_season_player(db: Session, season_id: int, player_id: int) -> SeasonPlayer:
    sp = db.scalars(
        select(SeasonPlayer).where(
            SeasonPlayer.season_id == season_id,
            SeasonPlayer.player_id == player_id,
        )
    ).first()
    if sp is None:
        sp = SeasonPlayer(
            season_id=season_id,
            player_id=player_id,
            current_score=0,
            is_online=True,
            is_active=True,
        )
        db.add(sp)
        db.flush()
    return sp
