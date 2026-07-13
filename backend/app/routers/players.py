from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthToken
from app.matchday import get_matchday_start
from app.audit import write_score_audit
from app.datetime_norm import assume_shanghai_if_naive, assume_utc_if_naive
from app.models import (
    Match, MatchPlayer, Player, PlayerLike, PlayerTag, ScoreAuditLog, SeasonPlayer, Tag,
)
from app.schemas import (
    PlayerBulkImportBody,
    PlayerBulkImportResult,
    PlayerCreate,
    PlayerPatch,
    PlayerOut,
    PlayerStats,
    ScoreAuditEntry,
    TagVoteOut,
    TagVoteRow,
    TopTagItem,
    VoteBody,
)
from app.seasons import get_active_season, get_or_create_season_player
from app.stats import load_matchday_stats, load_top_tags_for_season

router = APIRouter(prefix="/api/players", tags=["players"])


def _load_player_total_stats(db: Session, season_id: int) -> dict[int, tuple[int, int]]:
    """返回 player_id -> (total_played_in_season, total_won_in_season)。"""
    stmt = (
        select(
            MatchPlayer.player_id,
            func.count(MatchPlayer.id).label("played"),
            func.sum(case((MatchPlayer.is_winner.is_(True), 1), else_=0)).label("won"),
        )
        .join(Match)
        .where(Match.season_id == season_id)
        .group_by(MatchPlayer.player_id)
    )
    rows = db.execute(stmt).all()
    return {int(pid): (int(p or 0), int(w or 0)) for pid, p, w in rows}


def _load_like_counts(db: Session, season_id: int) -> dict[int, int]:
    rows = db.execute(
        select(PlayerLike.player_id, func.count(PlayerLike.id))
        .where(PlayerLike.season_id == season_id)
        .group_by(PlayerLike.player_id)
    ).all()
    return {int(pid): int(c) for pid, c in rows}


def _player_to_out(
    p: Player,
    sp: SeasonPlayer,
    today_played: int,
    today_won: int,
    total_played: int = 0,
    total_won: int = 0,
    like_count: int = 0,
    top_tags: list[TopTagItem] | None = None,
    prev_season_rank: int | None = None,
) -> PlayerOut:
    win_rate = (total_won / total_played) if total_played > 0 else 0.0
    return PlayerOut(
        id=p.id,
        name=p.name,
        current_score=sp.current_score,
        is_online=sp.is_online,
        is_active=sp.is_active,
        stats=PlayerStats(matches_played=today_played, matches_won=today_won),
        like_count=like_count,
        total_played=total_played,
        total_won=total_won,
        win_rate=win_rate,
        top_tags=top_tags or [],
        prev_season_rank=prev_season_rank,
    )


@router.post("", response_model=PlayerOut)
def create_player(body: PlayerCreate, _: AuthToken, db: Session = Depends(get_db)):
    season = get_active_season(db)

    name = body.name.strip()
    existing = db.scalars(select(Player).where(Player.name == name)).first()
    if existing:
        sp = get_or_create_season_player(db, season.id, existing.id)
        sp.is_active = True
        old_score = sp.current_score
        sp.current_score = body.current_score
        sp.is_online = True
        write_score_audit(
            db, season_id=season.id, player_id=existing.id,
            delta=body.current_score - old_score,
            reason="initial_score",
            note=f"重新激活并设积分 {old_score} → {body.current_score}",
        )
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
    write_score_audit(
        db, season_id=season.id, player_id=p.id,
        delta=body.current_score,
        reason="initial_score",
        note=f"新建选手初始积分 {body.current_score}",
    )
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
    if tier is not None and tier not in ("low", "mid", "high"):
        raise HTTPException(status_code=400, detail="tier 必须是 low / mid / high")

    season = get_active_season(db)
    md = get_matchday_start()
    today_stats = load_matchday_stats(db, md, season_id=season.id)
    total_stats = _load_player_total_stats(db, season.id)
    like_map = _load_like_counts(db, season.id)
    top_tags_map = load_top_tags_for_season(db, season.id, top_n=5)

    # 上赛季名次
    from app.models import Season as _Season, SeasonStatus as _SS
    prev_season = db.scalars(
        select(_Season).where(
            _Season.status == _SS.archived,
            _Season.id < season.id,
        ).order_by(_Season.id.desc())
    ).first()
    prev_rank_map: dict[int, int] = {}
    if prev_season:
        rank_rows = db.execute(
            select(SeasonPlayer.player_id, SeasonPlayer.final_rank).where(
                SeasonPlayer.season_id == prev_season.id,
                SeasonPlayer.final_rank.isnot(None),
            )
        ).all()
        prev_rank_map = {int(pid): int(r) for pid, r in rank_rows}

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
        played, won = today_stats.get(p.id, (0, 0))
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
        tp, tw = total_stats.get(p.id, (0, 0))
        out.append(_player_to_out(
            p, sp, played, won,
            total_played=tp, total_won=tw,
            like_count=like_map.get(p.id, 0),
            top_tags=top_tags_map.get(p.id, []),
            prev_season_rank=prev_rank_map.get(p.id),
        ))
    return out


@router.post("/import", response_model=PlayerBulkImportResult)
def bulk_import_players(body: PlayerBulkImportBody, _: AuthToken, db: Session = Depends(get_db)):
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
            old_score = sp.current_score
            sp.current_score = row.current_score
            sp.is_active = True
            write_score_audit(
                db, season_id=season.id, player_id=existing.id,
                delta=row.current_score - old_score,
                reason="bulk_import",
                note=f"批量导入覆盖 {old_score} → {row.current_score}",
            )
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
            write_score_audit(
                db, season_id=season.id, player_id=p.id,
                delta=row.current_score,
                reason="bulk_import",
                note=f"批量导入新建 {row.current_score}",
            )
            created += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="批量导入失败：存在重复名称或其它约束冲突")
    return PlayerBulkImportResult(created=created, updated=updated, total=created + updated)


@router.delete("/{player_id}")
def delete_player(player_id: int, _: AuthToken, db: Session = Depends(get_db)):
    """从当前赛季选手池移除（标记 is_active=False，仅前端隐藏）。"""
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
        p.name = new_name
    if body.is_online is not None:
        sp.is_online = body.is_online
    if body.current_score is not None:
        old_score = sp.current_score
        sp.current_score = body.current_score
        write_score_audit(
            db, season_id=season.id, player_id=p.id,
            delta=body.current_score - old_score,
            reason="manual_adjust",
            note=f"管理员手动调整 {old_score} → {body.current_score}",
        )
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
    today_stats = load_matchday_stats(db, md, season_id=season.id)
    total_stats = _load_player_total_stats(db, season.id)
    like_map = _load_like_counts(db, season.id)
    top_tags_map = load_top_tags_for_season(db, season.id, top_n=5)
    played, won = today_stats.get(p.id, (0, 0))
    tp, tw = total_stats.get(p.id, (0, 0))
    return _player_to_out(
        p, sp, played, won,
        total_played=tp, total_won=tw,
        like_count=like_map.get(p.id, 0),
        top_tags=top_tags_map.get(p.id, []),
    )


# ─────────────────────────────────────────────────────────────────
# 互动：点赞 / 打标签
# 使用游客匿名 voter_token（前端 localStorage UUID）实现一人一票。
# 当前赛季是归档赛季时拒绝写入。
# ─────────────────────────────────────────────────────────────────


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, _: AuthToken, db: Session = Depends(get_db)):
    """按 id 拉单个选手的当前赛季信息。供前端在排行榜入口点开选手详情时使用。"""
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
        # 选手不在当前赛季：返回零值 PlayerOut（仍带姓名/在线状态等基础信息）
        return _player_to_out(
            p,
            SeasonPlayer(
                season_id=season.id, player_id=p.id,
                current_score=0, is_online=True, is_active=False,
            ),
            0, 0,
        )
    md = get_matchday_start()
    today_stats = load_matchday_stats(db, md, season_id=season.id)
    total_stats = _load_player_total_stats(db, season.id)
    like_map = _load_like_counts(db, season.id)
    top_tags_map = load_top_tags_for_season(db, season.id, top_n=5)
    played, won = today_stats.get(p.id, (0, 0))
    tp, tw = total_stats.get(p.id, (0, 0))
    return _player_to_out(
        p, sp, played, won,
        total_played=tp, total_won=tw,
        like_count=like_map.get(p.id, 0),
        top_tags=top_tags_map.get(p.id, []),
    )


@router.get("/{player_id}/score-history", response_model=list[ScoreAuditEntry])
def get_player_score_history(
    player_id: int,
    _: AuthToken,
    db: Session = Depends(get_db),
    season_id: int | None = Query(None, description="按赛季过滤，缺省=当前赛季"),
):
    """返回该选手在指定赛季（缺省=当前）的所有积分变更记录，按时间升序。
    每条带 match_summary（如果是比赛产生的），前端无需再请求 match detail。"""
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="选手不存在")
    if season_id is None:
        season = get_active_season(db)
        sid = season.id
    else:
        sid = season_id

    logs = db.scalars(
        select(ScoreAuditLog)
        .where(
            ScoreAuditLog.season_id == sid,
            ScoreAuditLog.player_id == player_id,
        )
        .order_by(ScoreAuditLog.created_at.asc(), ScoreAuditLog.id.asc())
    ).all()

    # 批量拉相关比赛信息以拼装 match_summary
    match_ids = {log.match_id for log in logs if log.match_id is not None}
    match_map: dict[int, Match] = {}
    if match_ids:
        match_map = {
            m.id: m for m in db.scalars(select(Match).where(Match.id.in_(match_ids))).all()
        }

    out: list[ScoreAuditEntry] = []
    for log in logs:
        match_summary = None
        m = match_map.get(log.match_id) if log.match_id is not None else None
        if m is not None:
            md_str = assume_shanghai_if_naive(m.matchday_start).strftime("%Y-%m-%d")
            prefix = "【板命】" if m.is_banming else ""
            match_summary = f"{prefix}#{m.id} · {md_str} 比赛日"
        out.append(ScoreAuditEntry(
            id=log.id,
            delta=log.delta,
            reason=log.reason,
            note=log.note,
            match_id=log.match_id,
            match_summary=match_summary,
            created_at=assume_utc_if_naive(log.created_at),
        ))
    return out


# ─────────────────────────────────────────────────────────────────
# 互动：点赞 / 打标签
# 使用游客匿名 voter_token（前端 localStorage UUID）实现一人一票。
# 当前赛季是归档赛季时拒绝写入。
# ─────────────────────────────────────────────────────────────────


def _ensure_player_in_active_season(db: Session, player_id: int) -> tuple[Player, int]:
    """返回 (Player, season_id)。当前赛季归档时直接抛 400。"""
    season = get_active_season(db)
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="选手不存在")
    return p, season.id


@router.get("/{player_id}/social", response_model=TagVoteOut)
def get_player_social(
    player_id: int,
    _: AuthToken,
    db: Session = Depends(get_db),
    voter_token: Optional[str] = Query(None, description="可选：用于回填 voted_by_me/liked_by_me"),
):
    """获取选手在当前赛季的点赞数 + 各标签得票数（带当前游客已投状态）。"""
    season = get_active_season(db)
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="选手不存在")

    like_count = db.scalar(
        select(func.count(PlayerLike.id)).where(
            PlayerLike.season_id == season.id,
            PlayerLike.player_id == player_id,
        )
    ) or 0

    liked_by_me = False
    if voter_token:
        liked_by_me = bool(db.scalar(
            select(PlayerLike.id).where(
                PlayerLike.season_id == season.id,
                PlayerLike.player_id == player_id,
                PlayerLike.voter_token == voter_token,
            )
        ))

    # 标签：所有 enabled 的预定义标签 + 该选手在本赛季已被打过的标签
    tag_counts = db.execute(
        select(PlayerTag.tag_id, func.count(PlayerTag.id))
        .where(
            PlayerTag.season_id == season.id,
            PlayerTag.player_id == player_id,
        )
        .group_by(PlayerTag.tag_id)
    ).all()
    tag_counts_map = {int(tid): int(c) for tid, c in tag_counts}

    my_tag_ids: set[int] = set()
    if voter_token:
        rows = db.scalars(
            select(PlayerTag.tag_id).where(
                PlayerTag.season_id == season.id,
                PlayerTag.player_id == player_id,
                PlayerTag.voter_token == voter_token,
            )
        ).all()
        my_tag_ids = {int(t) for t in rows}

    # 拉所有 enabled 的 Tag：公共（player_id IS NULL）+ 该选手专属（player_id=player_id）
    from sqlalchemy import or_
    all_tags = db.scalars(
        select(Tag).where(
            Tag.is_enabled.is_(True),
            or_(Tag.player_id.is_(None), Tag.player_id == player_id),
        ).order_by(Tag.sort_order, Tag.id)
    ).all()
    rows_out: list[TagVoteRow] = []
    for t in all_tags:
        rows_out.append(TagVoteRow(
            tag_id=t.id,
            label=t.label,
            count=tag_counts_map.get(t.id, 0),
            voted_by_me=t.id in my_tag_ids,
        ))
    # 把已被投过但 disabled 的标签也带上（保留显示，避免数据消失）
    extra_disabled_ids = set(tag_counts_map.keys()) - {t.id for t in all_tags}
    if extra_disabled_ids:
        for t in db.scalars(select(Tag).where(Tag.id.in_(extra_disabled_ids))).all():
            rows_out.append(TagVoteRow(
                tag_id=t.id,
                label=t.label,
                count=tag_counts_map.get(t.id, 0),
                voted_by_me=t.id in my_tag_ids,
            ))

    return TagVoteOut(
        like_count=int(like_count),
        liked_by_me=liked_by_me,
        tags=rows_out,
    )


@router.post("/{player_id}/like", response_model=TagVoteOut)
def toggle_like(
    player_id: int,
    body: VoteBody,
    _: AuthToken,
    db: Session = Depends(get_db),
):
    """toggle：未点过则点上，已点过则取消。"""
    p, season_id = _ensure_player_in_active_season(db, player_id)
    existing = db.scalars(
        select(PlayerLike).where(
            PlayerLike.season_id == season_id,
            PlayerLike.player_id == player_id,
            PlayerLike.voter_token == body.voter_token,
        )
    ).first()
    if existing:
        db.delete(existing)
    else:
        db.add(PlayerLike(
            season_id=season_id,
            player_id=player_id,
            voter_token=body.voter_token,
            voter_nickname=(body.voter_nickname or "").strip() or None,
        ))
    db.commit()
    return get_player_social(player_id, _, db, voter_token=body.voter_token)


@router.post("/{player_id}/tags/{tag_id}", response_model=TagVoteOut)
def toggle_tag(
    player_id: int,
    tag_id: int,
    body: VoteBody,
    _: AuthToken,
    db: Session = Depends(get_db),
):
    """toggle 给某选手的某标签投票。"""
    p, season_id = _ensure_player_in_active_season(db, player_id)
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    if not tag.is_enabled:
        # 仍允许取消已投票，但不允许新投
        existing_disabled = db.scalars(
            select(PlayerTag).where(
                PlayerTag.season_id == season_id,
                PlayerTag.player_id == player_id,
                PlayerTag.tag_id == tag_id,
                PlayerTag.voter_token == body.voter_token,
            )
        ).first()
        if not existing_disabled:
            raise HTTPException(status_code=400, detail="该标签已被禁用")

    existing = db.scalars(
        select(PlayerTag).where(
            PlayerTag.season_id == season_id,
            PlayerTag.player_id == player_id,
            PlayerTag.tag_id == tag_id,
            PlayerTag.voter_token == body.voter_token,
        )
    ).first()
    if existing:
        db.delete(existing)
    else:
        db.add(PlayerTag(
            season_id=season_id,
            player_id=player_id,
            tag_id=tag_id,
            voter_token=body.voter_token,
            voter_nickname=(body.voter_nickname or "").strip() or None,
        ))
    db.commit()
    return get_player_social(player_id, _, db, voter_token=body.voter_token)
