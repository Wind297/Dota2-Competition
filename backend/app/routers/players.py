from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthToken
from app.matchday import get_matchday_start
from app.models import MatchPlayer, Player
from app.schemas import (
    PlayerBulkImportBody,
    PlayerBulkImportResult,
    PlayerCreate,
    PlayerPatch,
    PlayerOut,
    PlayerStats,
)
from app.stats import load_matchday_stats

router = APIRouter(prefix="/api/players", tags=["players"])


@router.post("", response_model=PlayerOut)
def create_player(body: PlayerCreate, _: AuthToken, db: Session = Depends(get_db)):
    p = Player(name=body.name.strip(), current_score=body.current_score, is_online=True)
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="选手名称已存在")
    db.refresh(p)
    return PlayerOut(
        id=p.id,
        name=p.name,
        current_score=p.current_score,
        is_online=p.is_online,
        stats=PlayerStats(matches_played=0, matches_won=0),
    )


def _tier_ok(score: int, tier: str | None) -> bool:
    if tier is None:
        return True
    if tier == "low":
        return 0 <= score <= 4
    if tier == "mid":
        return 5 <= score <= 9
    if tier == "high":
        return score >= 10
    return True


def _apply_filters(
    p: Player,
    played: int,
    won: int,
    *,
    tier: str | None,
    today_not_played: bool | None,
    today_not_won: bool | None,
    today_played_lte_1: bool | None,
    today_played_eq_1: bool | None,
    online_only: bool | None,
) -> bool:
    if not _tier_ok(p.current_score, tier):
        return False
    if online_only is True and not p.is_online:
        return False
    if today_not_played is True and played != 0:
        return False
    if today_not_won is True and won != 0:
        return False
    if today_played_lte_1 is True and played > 1:
        return False
    if today_played_eq_1 is True and played != 1:
        return False
    return True


@router.get("", response_model=list[PlayerOut])
def list_players(
    _: AuthToken,
    db: Session = Depends(get_db),
    tier: Annotated[str | None, Query()] = None,
    today_not_played: Annotated[bool | None, Query()] = None,
    today_not_won: Annotated[bool | None, Query()] = None,
    today_played_lte_1: Annotated[bool | None, Query()] = None,
    today_played_eq_1: Annotated[bool | None, Query()] = None,
    online_only: Annotated[bool | None, Query()] = None,
):
    if tier is not None and tier not in ("low", "mid", "high"):
        raise HTTPException(status_code=400, detail="tier 必须是 low / mid / high")

    md = get_matchday_start()
    stats_map = load_matchday_stats(db, md)
    players = db.scalars(select(Player).order_by(Player.name)).all()
    out: list[PlayerOut] = []
    for p in players:
        played, won = stats_map.get(p.id, (0, 0))
        if not _apply_filters(
            p,
            played,
            won,
            tier=tier,
            today_not_played=today_not_played,
            today_not_won=today_not_won,
            today_played_lte_1=today_played_lte_1,
            today_played_eq_1=today_played_eq_1,
            online_only=online_only,
        ):
            continue
        out.append(
            PlayerOut(
                id=p.id,
                name=p.name,
                current_score=p.current_score,
                is_online=p.is_online,
                stats=PlayerStats(matches_played=played, matches_won=won),
            )
        )
    return out


@router.post("/import", response_model=PlayerBulkImportResult)
def bulk_import_players(body: PlayerBulkImportBody, _: AuthToken, db: Session = Depends(get_db)):
    """按姓名批量新建或覆盖积分（重名则更新 current_score）。"""
    created = 0
    updated = 0
    for row in body.items:
        name = row.name.strip()
        if not name:
            continue
        existing = db.scalars(select(Player).where(Player.name == name)).first()
        if existing:
            existing.current_score = row.current_score
            updated += 1
        else:
            db.add(Player(name=name, current_score=row.current_score, is_online=True))
            created += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="批量导入失败：存在重复名称或其它约束冲突")
    return PlayerBulkImportResult(created=created, updated=updated, total=created + updated)


@router.delete("/{player_id}")
def delete_player(player_id: int, _: AuthToken, db: Session = Depends(get_db)):
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="选手不存在")

    cnt = db.scalar(
        select(func.count()).select_from(MatchPlayer).where(MatchPlayer.player_id == player_id)
    )
    if cnt and cnt > 0:
        raise HTTPException(
            status_code=400,
            detail="该选手已有比赛记录，请先在「历史比赛」中删除相关场次后再删除选手",
        )

    db.delete(p)
    db.commit()
    return {"ok": True, "id": player_id}


@router.patch("/{player_id}", response_model=PlayerOut)
def patch_player(
    player_id: int,
    body: PlayerPatch,
    _: AuthToken,
    db: Session = Depends(get_db),
):
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="选手不存在")
    if body.is_online is not None:
        p.is_online = body.is_online
    if body.current_score is not None:
        p.current_score = body.current_score
    db.commit()
    db.refresh(p)
    md = get_matchday_start()
    stats_map = load_matchday_stats(db, md)
    played, won = stats_map.get(p.id, (0, 0))
    return PlayerOut(
        id=p.id,
        name=p.name,
        current_score=p.current_score,
        is_online=p.is_online,
        stats=PlayerStats(matches_played=played, matches_won=won),
    )
