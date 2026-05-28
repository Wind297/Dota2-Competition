from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.datetime_norm import assume_shanghai_if_naive, assume_utc_if_naive
from app.deps import AuthToken
from app.matchday import get_matchday_start, get_tz
from app.models import Match, MatchPlayer, MatchStatus, Player
from app.schemas import MatchCreate, MatchOut, MatchPatch, MatchPlayerBrief, MatchResult

router = APIRouter(prefix="/api/matches", tags=["matches"])


# ─────────────────────────────────────────────────────────────────────────────
# 积分核心：每个 MatchPlayer.score_delta 是该场对该选手的净积分影响。
#   - 胜者默认 +1
#   - 被扣分负方 -1
#   - 其他 0
# 所有积分调整都使用 _set_match_player_delta(mp, target)：差额同步到 player.current_score。
# 这样无论修正多少次，账目永远清晰，且可追溯。
# ─────────────────────────────────────────────────────────────────────────────


def _set_match_player_delta(mp: MatchPlayer, target_delta: int) -> None:
    """把某选手在本场比赛产生的积分影响调整为 target_delta，差额同步到 current_score。"""
    diff = target_delta - mp.score_delta
    if diff != 0:
        mp.player.current_score = max(0, mp.player.current_score + diff)
    mp.score_delta = target_delta


def _clear_match_player_delta(mp: MatchPlayer) -> None:
    """删除/移除选手前调用：把该选手在本场的积分影响归零（撤销曾经的加减分）。"""
    _set_match_player_delta(mp, 0)


def _compute_sequence_no(db: Session, m: Match) -> int:
    """若手工指定了 sequence_no 则用之；否则按比赛日内 created_at 升序计算第几场。"""
    if m.sequence_no is not None:
        return m.sequence_no
    earlier_count = db.scalar(
        select(func.count(Match.id)).where(
            Match.matchday_start == m.matchday_start,
            Match.created_at < m.created_at,
            Match.id != m.id,
        )
    ) or 0
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
        matchday_start=assume_shanghai_if_naive(m.matchday_start),
        actual_time=assume_utc_if_naive(m.actual_time),
        sequence_no=_compute_sequence_no(db, m),
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
    ids = body.player_ids
    if len(set(ids)) != 10:
        raise HTTPException(status_code=400, detail="必须选择 10 名互不相同的选手")

    players = db.scalars(select(Player).where(Player.id.in_(ids))).all()
    if len(players) != 10:
        raise HTTPException(status_code=400, detail="存在无效的选手 ID")

    now = datetime.now(get_tz())
    md = get_matchday_start(now)

    busy = db.scalars(
        select(MatchPlayer.player_id)
        .join(Match)
        .where(
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

    match = Match(matchday_start=md, status=MatchStatus.confirmed)
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

    名单变更：被移除的选手会先撤销其在本场产生的所有积分影响（含扣分）；新加入的
    选手 is_winner=None / score_delta=0。
    """
    m = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")

    if body.matchday_start is not None:
        m.matchday_start = body.matchday_start

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

        old_rows = list(m.players)
        old_id_to_row = {mp.player_id: mp for mp in old_rows}
        old_ids = set(old_id_to_row.keys())
        new_id_set = set(new_ids)

        # 移除被踢出的选手：先撤销他们在本场的全部积分影响（无论是 +1 胜分还是 -1 扣分）
        for pid in old_ids - new_id_set:
            mp = old_id_to_row[pid]
            _clear_match_player_delta(mp)
            db.delete(mp)

        # 名单变更后冲突检查
        if m.status == MatchStatus.confirmed:
            added_ids = list(new_id_set - old_ids)
            if added_ids:
                busy = db.scalars(
                    select(MatchPlayer.player_id)
                    .join(Match)
                    .where(
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

        # 新增选手
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


def _apply_result(rows: list[MatchPlayer], win_set: set[int], deduct_set: set[int]) -> None:
    """统一应用结果（胜者 + 扣分名单）。差额同步到选手 current_score，幂等。

    每位选手的目标 delta：
      - 胜者：+1
      - 被扣分负方：-1
      - 其他：0
    """
    for mp in rows:
        is_winner = mp.player_id in win_set
        is_deducted = mp.player_id in deduct_set
        target = (1 if is_winner else 0) + (-1 if is_deducted else 0)
        mp.is_winner = is_winner
        mp.is_deducted = is_deducted
        _set_match_player_delta(mp, target)


@router.patch("/{match_id}/result", response_model=MatchOut)
def submit_or_update_result(match_id: int, body: MatchResult, _: AuthToken, db: Session = Depends(get_db)):
    m = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")

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
    # 胜者不应同时在扣分名单里
    overlap = win_set & deduct_set
    if overlap:
        raise HTTPException(
            status_code=400, detail=f"以下选手同时为胜者与扣分对象：{sorted(overlap)}"
        )

    if m.status not in (MatchStatus.confirmed, MatchStatus.completed):
        raise HTTPException(status_code=400, detail="比赛状态无效")

    _apply_result(rows, win_set, deduct_set)
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

    # 删除前撤销该场对所有选手的积分影响
    for mp in m.players:
        _clear_match_player_delta(mp)

    db.delete(m)
    db.commit()
    return {"ok": True, "id": match_id}
