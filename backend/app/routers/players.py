from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthToken
from app.matchday import get_matchday_start
from app.models import MatchPlayer, Player, SeasonPlayer
from app.schemas import (
    PlayerBulkImportBody,
    PlayerBulkImportResult,
    PlayerCreate,
    PlayerPatch,
    PlayerOut,
    PlayerStats,
)
from app.seasons import get_active_season, get_or_create_season_player
from app.stats import load_matchday_stats

router = APIRouter(prefix="/api/players", tags=["players"])


def _player_to_out(p: Player, sp: SeasonPlayer, played: int, won: int) -> PlayerOut:
    return PlayerOut(
        id=p.id,
        name=p.name,
        current_score=sp.current_score,
        is_online=sp.is_online,
        is_active=sp.is_active,
        stats=PlayerStats(matches_played=played, matches_won=won),
    )


@router.post("", response_model=PlayerOut)
def create_player(body: PlayerCreate, _: AuthToken, db: Session = Depends(get_db)):
    season = get_active_season(db)

    name = body.name.strip()
    existing = db.scalars(select(Player).where(Player.name == name)).first()
    if existing:
        # 选手身份已存在（可能是历史赛季的人）：在当前赛季激活并设积分
        sp = get_or_create_season_player(db, season.id, existing.id)
        sp.is_active = True
        sp.current_score = body.current_score
        sp.is_online = True
        db.commit()
        return _player_to_out(existing, sp, 0, 0)

    p = Player(name=name)
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="选手名称已存在")
    sp = SeasonPlayer(
        season_id=season.id,
        player_id=p.id,
        current_score=body.current_score,
        is_online=True,
        is_active=True,
    )
    db.add(sp)
    db.commit()
    db.refresh(p)
    return _player_to_out(p, sp, 0, 0)


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
    sp: SeasonPlayer,
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
    if not _tier_ok(sp.current_score, tier):
        return False
    if online_only is True and not sp.is_online:
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
    include_inactive: Annotated[bool, Query()] = False,
):
    """列出当前赛季的选手；默认只返回本赛季 is_active=True 的。"""
    if tier is not None and tier not in ("low", "mid", "high"):
        raise HTTPException(status_code=400, detail="tier 必须是 low / mid / high")

    season = get_active_season(db)
    md = get_matchday_start()
    stats_map = load_matchday_stats(db, md, season_id=season.id)

    # 查询 SeasonPlayer + Player（左外连接 Player 不存在的情况理论上不会有）
    rows = db.execute(
        select(SeasonPlayer, Player)
        .join(Player, Player.id == SeasonPlayer.player_id)
        .where(SeasonPlayer.season_id == season.id)
        .order_by(Player.name)
    ).all()

    out: list[PlayerOut] = []
    for sp, p in rows:
        if not include_inactive and not sp.is_active:
            continue
        played, won = stats_map.get(p.id, (0, 0))
        if not _apply_filters(
            sp, played, won,
            tier=tier,
            today_not_played=today_not_played,
            today_not_won=today_not_won,
            today_played_lte_1=today_played_lte_1,
            today_played_eq_1=today_played_eq_1,
            online_only=online_only,
        ):
            continue
        out.append(_player_to_out(p, sp, played, won))
    return out


@router.post("/import", response_model=PlayerBulkImportResult)
def bulk_import_players(body: PlayerBulkImportBody, _: AuthToken, db: Session = Depends(get_db)):
    """按姓名批量新建或覆盖（在当前赛季）。同名选手会更新其本赛季积分；不存在则新建。"""
    season = get_active_season(db)
    created = 0
    updated = 0
    for row in body.items:
        name = row.name.strip()
        if not name:
            continue
        existing = db.scalars(select(Player).where(Player.name == name)).first()
        if existing:
            sp = get_or_create_season_player(db, season.id, existing.id)
            sp.current_score = row.current_score
            sp.is_active = True
            updated += 1
        else:
            p = Player(name=name)
            db.add(p)
            db.flush()
            db.add(SeasonPlayer(
                season_id=season.id,
                player_id=p.id,
                current_score=row.current_score,
                is_online=True,
                is_active=True,
            ))
            created += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="批量导入失败：存在重复名称或其它约束冲突")
    return PlayerBulkImportResult(created=created, updated=updated, total=created + updated)


@router.delete("/{player_id}")
def delete_player(player_id: int, _: AuthToken, db: Session = Depends(get_db)):
    """从当前赛季移除选手（标记为 is_active=False，仅在选手池隐藏）。

    历史比赛记录、积分、和队友的同场记录全部保留。
    选手回归时直接把 is_active 改回 True 即可，积分接着累计。
    选手实体本身不会被删除（保留跨赛季身份）。
    """
    season = get_active_season(db)
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="选手不存在")

    sp = db.scalars(
        select(SeasonPlayer).where(
            SeasonPlayer.season_id == season.id,
            SeasonPlayer.player_id == player_id,
        )
    ).first()
    if sp is None:
        # 已不在本赛季中
        return {"ok": True, "id": player_id}
    sp.is_active = False
    db.commit()
    return {"ok": True, "id": player_id}


@router.patch("/{player_id}", response_model=PlayerOut)
def patch_player(
    player_id: int,
    body: PlayerPatch,
    _: AuthToken,
    db: Session = Depends(get_db),
):
    season = get_active_season(db)
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="选手不存在")

    sp = get_or_create_season_player(db, season.id, p.id)

    if body.name is not None:
        new_name = body.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="姓名不能为空")
        p.name = new_name  # 改名跨赛季生效（同一身份）
    if body.is_online is not None:
        sp.is_online = body.is_online
    if body.current_score is not None:
        sp.current_score = body.current_score
    if body.is_active is not None:
        sp.is_active = body.is_active

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该姓名已被其他选手使用")
    db.refresh(p)
    db.refresh(sp)
    md = get_matchday_start()
    stats_map = load_matchday_stats(db, md, season_id=season.id)
    played, won = stats_map.get(p.id, (0, 0))
    return _player_to_out(p, sp, played, won)
