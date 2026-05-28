from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthToken
from app.models import Match, Player, Season, SeasonPlayer, SeasonStatus
from app.schemas import SeasonCreate, SeasonOut, SeasonRollover
from app.seasons import get_active_season_or_none

router = APIRouter(prefix="/api/seasons", tags=["seasons"])


def _season_to_out(s: Season, db: Session, *, current_id: int | None) -> SeasonOut:
    player_count = db.scalar(
        select(func.count(SeasonPlayer.id)).where(
            SeasonPlayer.season_id == s.id,
            SeasonPlayer.is_active.is_(True),
        )
    ) or 0
    match_count = db.scalar(
        select(func.count(Match.id)).where(Match.season_id == s.id)
    ) or 0
    return SeasonOut(
        id=s.id,
        name=s.name,
        status=s.status,
        started_at=s.started_at,
        ended_at=s.ended_at,
        is_current=(s.id == current_id),
        player_count=int(player_count),
        match_count=int(match_count),
    )


@router.get("", response_model=list[SeasonOut])
def list_seasons(_: AuthToken, db: Session = Depends(get_db)):
    seasons = db.scalars(select(Season).order_by(Season.id.desc())).all()
    current = get_active_season_or_none(db)
    cid = current.id if current else None
    return [_season_to_out(s, db, current_id=cid) for s in seasons]


@router.get("/current", response_model=SeasonOut | None)
def get_current_season(_: AuthToken, db: Session = Depends(get_db)):
    s = get_active_season_or_none(db)
    if s is None:
        return None
    return _season_to_out(s, db, current_id=s.id)


@router.post("", response_model=SeasonOut)
def create_season(body: SeasonCreate, _: AuthToken, db: Session = Depends(get_db)):
    """创建一个新赛季。前提：当前没有进行中的赛季。"""
    existing = get_active_season_or_none(db)
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail=f"当前已有进行中的赛季「{existing.name}」，请先结束后再开新赛季",
        )

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="赛季名称不能为空")

    s = Season(name=name, status=SeasonStatus.active)
    db.add(s)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="赛季名称已存在")

    if body.inherit_active_players:
        # 把上一季 is_active 的选手带进新赛季（积分清零，仍 active）
        prev = db.scalars(
            select(Season)
            .where(Season.id != s.id)
            .order_by(Season.id.desc())
        ).first()
        if prev is not None:
            prev_active = db.scalars(
                select(SeasonPlayer).where(
                    SeasonPlayer.season_id == prev.id,
                    SeasonPlayer.is_active.is_(True),
                )
            ).all()
            for sp in prev_active:
                db.add(SeasonPlayer(
                    season_id=s.id,
                    player_id=sp.player_id,
                    current_score=0,
                    is_online=True,
                    is_active=True,
                ))

    db.commit()
    db.refresh(s)
    return _season_to_out(s, db, current_id=s.id)


@router.post("/{season_id}/end", response_model=SeasonOut)
def end_season(season_id: int, _: AuthToken, db: Session = Depends(get_db)):
    """结束（归档）指定赛季。归档后该赛季的比赛不可再编辑。"""
    s = db.get(Season, season_id)
    if s is None:
        raise HTTPException(status_code=404, detail="赛季不存在")
    if s.status == SeasonStatus.archived:
        raise HTTPException(status_code=400, detail="该赛季已归档")
    s.status = SeasonStatus.archived
    s.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(s)
    current = get_active_season_or_none(db)
    return _season_to_out(s, db, current_id=current.id if current else None)


@router.post("/rollover", response_model=SeasonOut)
def rollover_season(body: SeasonRollover, _: AuthToken, db: Session = Depends(get_db)):
    """一键操作：结束当前赛季 → 开新赛季。"""
    current = get_active_season_or_none(db)
    if current is None:
        raise HTTPException(status_code=400, detail="当前没有进行中的赛季，请直接创建新赛季")

    new_name = body.new_season_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="新赛季名称不能为空")

    # 1) 归档当前赛季
    current.status = SeasonStatus.archived
    current.ended_at = datetime.now(timezone.utc)

    # 2) 创建新赛季
    new_s = Season(name=new_name, status=SeasonStatus.active)
    db.add(new_s)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="新赛季名称已存在")

    # 3) 继承活跃选手（若需）
    if body.inherit_active_players:
        prev_active = db.scalars(
            select(SeasonPlayer).where(
                SeasonPlayer.season_id == current.id,
                SeasonPlayer.is_active.is_(True),
            )
        ).all()
        for sp in prev_active:
            db.add(SeasonPlayer(
                season_id=new_s.id,
                player_id=sp.player_id,
                current_score=0,
                is_online=True,
                is_active=True,
            ))

    db.commit()
    db.refresh(new_s)
    return _season_to_out(new_s, db, current_id=new_s.id)
