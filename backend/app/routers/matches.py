from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.datetime_norm import assume_shanghai_if_naive, assume_utc_if_naive
from app.deps import AuthToken
from app.matchday import get_matchday_start, get_tz
from app.models import Match, MatchPlayer, MatchStatus, Player, SeasonPlayer, SeasonStatus
from app.schemas import MatchCreate, MatchOut, MatchPatch, MatchPlayerBrief, MatchResult
from app.seasons import get_active_season, get_or_create_season_player

router = APIRouter(prefix="/api/matches", tags=["matches"])


# ─────────────────────────────────────────────────────────────────────────────
# 积分核心：每个 MatchPlayer.score_delta 是该场对该选手的净积分影响。
#   - 胜者默认 +1
#   - 被扣分负方 -1
#   - 其他 0
# 所有积分调整都通过 _set_match_player_delta(mp, season_id, target)：
#   差额同步到该选手在 *该比赛所属赛季* 的 SeasonPlayer.current_score。
# 这样无论修正多少次，账目永远清晰，且历史赛季的积分不会被影响。
# ─────────────────────────────────────────────────────────────────────────────


def _set_match_player_delta(
    db: Session, mp: MatchPlayer, season_id: int | None, target_delta: int, *, skip_score: bool = False,
) -> None:
    """把某选手在本场比赛产生的积分影响调整为 target_delta。
    skip_score=True（练习赛）时只更新 score_delta 字段，不改 SeasonPlayer.current_score。"""
    diff = target_delta - mp.score_delta
    if diff != 0 and season_id is not None and not skip_score:
        sp = get_or_create_season_player(db, season_id, mp.player_id)
        sp.current_score = max(0, sp.current_score + diff)
    mp.score_delta = target_delta


def _clear_match_player_delta(db: Session, mp: MatchPlayer, season_id: int | None, *, skip_score: bool = False) -> None:
    _set_match_player_delta(db, mp, season_id, 0, skip_score=skip_score)


def _ensure_active_season_match(m: Match, db: Session) -> None:
    """确保该比赛属于当前进行中的赛季（即可以编辑）。归档赛季的比赛禁止改动。"""
    if m.season_id is None:
        return
    season = db.get(__import__("app.models", fromlist=["Season"]).Season, m.season_id)
    if season is not None and season.status == SeasonStatus.archived:
        raise HTTPException(status_code=400, detail="该比赛属于已归档的历史赛季，不可编辑")


def _compute_sequence_no(db: Session, m: Match) -> int:
    """若手工指定了 sequence_no 则用之；否则按比赛日内 created_at 升序计算第几场。"""
    if m.sequence_no is not None:
        return m.sequence_no
    # 在赛季维度内计算同比赛日的场次（避免跨赛季干扰）
    base_q = select(func.count(Match.id)).where(
        Match.matchday_start == m.matchday_start,
        Match.created_at < m.created_at,
        Match.id != m.id,
    )
    if m.season_id is not None:
        base_q = base_q.where(Match.season_id == m.season_id)
    earlier_count = db.scalar(base_q) or 0
    return earlier_count + 1


def _match_to_out(m: Match, db: Session) -> MatchOut:
    briefs = [
        MatchPlayerBrief(
            player_id=mp.player_id,
            name=mp.player.name,
            is_winner=mp.is_winner,
            is_deducted=mp.is_deducted,
            score_delta=mp.score_delta,
        )
        for mp in sorted(m.players, key=lambda x: x.player_id)
    ]
    return MatchOut(
        id=m.id,
        season_id=m.season_id,
        matchday_start=assume_shanghai_if_naive(m.matchday_start),
        actual_time=assume_utc_if_naive(m.actual_time),
        sequence_no=_compute_sequence_no(db, m),
        is_practice=m.is_practice,
        status=m.status,
        created_at=assume_utc_if_naive(m.created_at),
        players=briefs,
    )


@router.get("", response_model=list[MatchOut])
def list_matches(
    _: AuthToken,
    db: Session = Depends(get_db),
    status: MatchStatus | None = Query(None),
    matchday: str | None = Query(None, description="matchday_start 的 ISO8601 字符串，精确匹配"),
    season_id: int | None = Query(None, description="按赛季过滤，缺省=当前赛季"),
    all_seasons: bool = Query(False, description="若为 true 则返回所有赛季的比赛"),
):
    q = (
        select(Match)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
        .order_by(Match.created_at.desc())
    )
    if status is not None:
        q = q.where(Match.status == status)
    if matchday:
        try:
            md = datetime.fromisoformat(matchday)
        except ValueError:
            raise HTTPException(status_code=400, detail="matchday 格式无效")
        q = q.where(Match.matchday_start == md)
    if not all_seasons:
        if season_id is not None:
            q = q.where(Match.season_id == season_id)
        else:
            season = get_active_season(db)
            q = q.where(Match.season_id == season.id)

    matches = db.scalars(q).all()
    return [_match_to_out(m, db) for m in matches]


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: int, _: AuthToken, db: Session = Depends(get_db)):
    m = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return _match_to_out(m, db)


@router.post("", response_model=MatchOut)
def create_match(body: MatchCreate, _: AuthToken, db: Session = Depends(get_db)):
    season = get_active_season(db)
    ids = body.player_ids
    if len(set(ids)) != 10:
        raise HTTPException(status_code=400, detail="必须选择 10 名互不相同的选手")

    players = db.scalars(select(Player).where(Player.id.in_(ids))).all()
    if len(players) != 10:
        raise HTTPException(status_code=400, detail="存在无效的选手 ID")

    # 校验每个选手都参与了当前赛季
    sps = db.scalars(
        select(SeasonPlayer).where(
            SeasonPlayer.season_id == season.id,
            SeasonPlayer.player_id.in_(ids),
            SeasonPlayer.is_active.is_(True),
        )
    ).all()
    if len(sps) != 10:
        active_set = {sp.player_id for sp in sps}
        missing = [p.name for p in players if p.id not in active_set]
        raise HTTPException(
            status_code=400,
            detail=f"以下选手未参与当前赛季：{missing}",
        )

    now = datetime.now(get_tz())
    md = get_matchday_start(now)

    busy = db.scalars(
        select(MatchPlayer.player_id)
        .join(Match)
        .where(
            Match.season_id == season.id,
            Match.status == MatchStatus.confirmed,
            Match.matchday_start == md,
            MatchPlayer.player_id.in_(ids),
        )
    ).all()
    if busy:
        raise HTTPException(
            status_code=400,
            detail=f"以下选手在本比赛日已有未完成的已确认比赛：{sorted(set(busy))}",
        )

    match = Match(season_id=season.id, matchday_start=md, status=MatchStatus.confirmed, is_practice=body.is_practice)
    db.add(match)
    db.flush()
    id_set = {p.id for p in players}
    for pid in ids:
        if pid not in id_set:
            raise HTTPException(status_code=400, detail="存在无效的选手 ID")
        db.add(MatchPlayer(match_id=match.id, player_id=pid, is_winner=None))
    db.commit()
    m2 = db.scalars(
        select(Match)
        .where(Match.id == match.id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    assert m2 is not None
    return _match_to_out(m2, db)


@router.patch("/{match_id}", response_model=MatchOut)
def patch_match(match_id: int, body: MatchPatch, _: AuthToken, db: Session = Depends(get_db)):
    """编辑已录入的比赛：比赛日 / 场次号 / 上场名单。
    归档赛季的比赛不可编辑。
    """
    m = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")

    _ensure_active_season_match(m, db)

    if body.matchday_start is not None:
        m.matchday_start = body.matchday_start

    if body.is_practice is not None:
        m.is_practice = body.is_practice

    if body.clear_sequence_no:
        m.sequence_no = None
    elif body.sequence_no is not None:
        m.sequence_no = body.sequence_no

    if body.player_ids is not None:
        new_ids = body.player_ids
        if len(set(new_ids)) != 10:
            raise HTTPException(status_code=400, detail="必须选择 10 名互不相同的选手")

        existing_players = db.scalars(select(Player).where(Player.id.in_(new_ids))).all()
        if len(existing_players) != 10:
            raise HTTPException(status_code=400, detail="存在无效的选手 ID")

        # 新加入的选手必须在当前赛季 active
        if m.season_id is not None:
            sps = db.scalars(
                select(SeasonPlayer).where(
                    SeasonPlayer.season_id == m.season_id,
                    SeasonPlayer.player_id.in_(new_ids),
                    SeasonPlayer.is_active.is_(True),
                )
            ).all()
            if len(sps) != 10:
                active_set = {sp.player_id for sp in sps}
                missing = [p.name for p in existing_players if p.id not in active_set]
                raise HTTPException(
                    status_code=400,
                    detail=f"以下选手未参与当前赛季：{missing}",
                )

        old_rows = list(m.players)
        old_id_to_row = {mp.player_id: mp for mp in old_rows}
        old_ids = set(old_id_to_row.keys())
        new_id_set = set(new_ids)

        # 移除：撤销积分影响后删除
        for pid in old_ids - new_id_set:
            mp = old_id_to_row[pid]
            _clear_match_player_delta(db, mp, m.season_id, skip_score=m.is_practice)
            db.delete(mp)

        # 名单变更冲突检查
        if m.status == MatchStatus.confirmed:
            added_ids = list(new_id_set - old_ids)
            if added_ids:
                busy = db.scalars(
                    select(MatchPlayer.player_id)
                    .join(Match)
                    .where(
                        Match.season_id == m.season_id,
                        Match.status == MatchStatus.confirmed,
                        Match.matchday_start == m.matchday_start,
                        Match.id != m.id,
                        MatchPlayer.player_id.in_(added_ids),
                    )
                ).all()
                if busy:
                    raise HTTPException(
                        status_code=400,
                        detail=f"以下新加入选手在本比赛日已有未完成的已确认比赛：{sorted(set(busy))}",
                    )

        # 新增
        for pid in new_ids:
            if pid not in old_id_to_row:
                db.add(MatchPlayer(match_id=m.id, player_id=pid, is_winner=None))

    db.commit()
    m2 = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    assert m2 is not None
    return _match_to_out(m2, db)


def _apply_result(
    db: Session,
    rows: list[MatchPlayer],
    season_id: int | None,
    win_set: set[int],
    deduct_set: set[int],
    *,
    skip_score: bool = False,
) -> None:
    """统一应用结果（胜者 + 扣分名单）。差额同步到选手 current_score，幂等。
    skip_score=True（练习赛）时仅记录胜负标记，不改积分。"""
    for mp in rows:
        is_winner = mp.player_id in win_set
        is_deducted = mp.player_id in deduct_set
        target = (1 if is_winner else 0) + (-1 if is_deducted else 0)
        mp.is_winner = is_winner
        mp.is_deducted = is_deducted
        _set_match_player_delta(db, mp, season_id, target, skip_score=skip_score)


@router.patch("/{match_id}/result", response_model=MatchOut)
def submit_or_update_result(match_id: int, body: MatchResult, _: AuthToken, db: Session = Depends(get_db)):
    m = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")

    _ensure_active_season_match(m, db)

    winners = body.winner_player_ids
    deducted = body.deducted_player_ids or []
    if len(set(winners)) != 5:
        raise HTTPException(status_code=400, detail="必须恰好指定 5 名获胜者（互不重复）")
    if len(set(deducted)) != len(deducted):
        raise HTTPException(status_code=400, detail="扣分名单存在重复")

    rows = list(m.players)
    participant_ids = {mp.player_id for mp in rows}
    if not set(winners).issubset(participant_ids):
        raise HTTPException(status_code=400, detail="获胜者必须是本场比赛上场选手")
    if not set(deducted).issubset(participant_ids):
        raise HTTPException(status_code=400, detail="扣分选手必须是本场比赛上场选手")

    win_set = set(winners)
    deduct_set = set(deducted)
    overlap = win_set & deduct_set
    if overlap:
        raise HTTPException(
            status_code=400, detail=f"以下选手同时为胜者与扣分对象：{sorted(overlap)}"
        )

    if m.status not in (MatchStatus.confirmed, MatchStatus.completed):
        raise HTTPException(status_code=400, detail="比赛状态无效")

    _apply_result(db, rows, m.season_id, win_set, deduct_set, skip_score=m.is_practice)
    m.status = MatchStatus.completed

    db.commit()
    m2 = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    assert m2 is not None
    return _match_to_out(m2, db)


@router.delete("/{match_id}")
def delete_match(match_id: int, _: AuthToken, db: Session = Depends(get_db)):
    m = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")

    _ensure_active_season_match(m, db)

    # 删除前撤销积分影响
    for mp in m.players:
        _clear_match_player_delta(db, mp, m.season_id, skip_score=m.is_practice)

    db.delete(m)
    db.commit()
    return {"ok": True, "id": match_id}
