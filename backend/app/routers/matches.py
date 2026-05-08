from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.datetime_norm import assume_shanghai_if_naive, assume_utc_if_naive
from app.deps import AuthToken
from app.matchday import get_matchday_start, get_tz
from app.models import Match, MatchPlayer, MatchStatus, Player
from app.schemas import MatchCreate, MatchOut, MatchPlayerBrief, MatchResult

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _match_to_out(m: Match) -> MatchOut:
    briefs = [
        MatchPlayerBrief(player_id=mp.player_id, name=mp.player.name, is_winner=mp.is_winner)
        for mp in sorted(m.players, key=lambda x: x.player_id)
    ]
    return MatchOut(
        id=m.id,
        matchday_start=assume_shanghai_if_naive(m.matchday_start),
        actual_time=assume_utc_if_naive(m.actual_time),
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
    return [_match_to_out(m) for m in matches]


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: int, _: AuthToken, db: Session = Depends(get_db)):
    m = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return _match_to_out(m)


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
    return _match_to_out(m2)


def _apply_winners_and_scores(rows: list[MatchPlayer], win_set: set[int], *, completed: bool) -> None:
    """completed=False：首次提交；completed=True：仅更新胜负标记并按差额调整积分。"""
    if not completed:
        for mp in rows:
            mp.is_winner = mp.player_id in win_set
            if mp.is_winner:
                mp.player.current_score += 1
        return

    old_winners = {mp.player_id for mp in rows if mp.is_winner is True}
    for pid in old_winners - win_set:
        pl = next(mp.player for mp in rows if mp.player_id == pid)
        pl.current_score = max(0, pl.current_score - 1)
    for pid in win_set - old_winners:
        pl = next(mp.player for mp in rows if mp.player_id == pid)
        pl.current_score += 1
    for mp in rows:
        mp.is_winner = mp.player_id in win_set


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
    if len(set(winners)) != 5:
        raise HTTPException(status_code=400, detail="必须恰好指定 5 名获胜者（互不重复）")

    rows = list(m.players)
    participant_ids = {mp.player_id for mp in rows}
    if not set(winners).issubset(participant_ids):
        raise HTTPException(status_code=400, detail="获胜者必须是本场比赛上场选手")

    win_set = set(winners)

    if m.status == MatchStatus.confirmed:
        _apply_winners_and_scores(rows, win_set, completed=False)
        m.status = MatchStatus.completed
    elif m.status == MatchStatus.completed:
        _apply_winners_and_scores(rows, win_set, completed=True)
    else:
        raise HTTPException(status_code=400, detail="比赛状态无效")

    mid = m.id
    db.commit()
    m2 = db.scalars(
        select(Match)
        .where(Match.id == mid)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    assert m2 is not None
    return _match_to_out(m2)


@router.delete("/{match_id}")
def delete_match(match_id: int, _: AuthToken, db: Session = Depends(get_db)):
    m = db.scalars(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players).selectinload(MatchPlayer.player))
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")

    if m.status == MatchStatus.completed:
        for mp in m.players:
            if mp.is_winner is True:
                mp.player.current_score = max(0, mp.player.current_score - 1)

    db.delete(m)
    db.commit()
    return {"ok": True, "id": match_id}
