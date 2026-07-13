from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthToken
from app.models import Match, MatchPlayer, MatchStatus, Player, Season, SeasonPlayer, SeasonStatus
from app.schemas import RankingRow
from app.seasons import get_active_season
from app.stats import load_top_tags_for_season

router = APIRouter(prefix="/api/rankings", tags=["rankings"])


@router.get("", response_model=list[RankingRow])
def rankings(
    _: AuthToken,
    db: Session = Depends(get_db),
    season_id: int | None = Query(None, description="按赛季过滤，缺省=当前赛季"),
):
    if season_id is None:
        season = get_active_season(db)
        season_id = season.id
    else:
        if db.get(Season, season_id) is None:
            raise HTTPException(status_code=404, detail="赛季不存在")

    # 上赛季名次
    prev_season = db.scalars(
        select(Season).where(
            Season.status == SeasonStatus.archived,
            Season.id < season_id,
        ).order_by(Season.id.desc())
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

    top_tags_map = load_top_tags_for_season(db, season_id, top_n=3)

    # 板命赢家计数：板命局 + 已完赛 + 该选手是胜者
    banming_wins_rows = db.execute(
        select(
            MatchPlayer.player_id,
            func.count(MatchPlayer.id).label("wins"),
        )
        .join(Match)
        .where(
            Match.season_id == season_id,
            Match.is_banming.is_(True),
            Match.status == MatchStatus.completed,
            MatchPlayer.is_winner.is_(True),
        )
        .group_by(MatchPlayer.player_id)
    ).all()
    banming_wins_map = {int(pid): int(w) for pid, w in banming_wins_rows}

    rows = db.execute(
        select(SeasonPlayer, Player)
        .join(Player, Player.id == SeasonPlayer.player_id)
        .where(
            SeasonPlayer.season_id == season_id,
            SeasonPlayer.is_active.is_(True),
        )
        .order_by(SeasonPlayer.current_score.desc(), Player.name)
    ).all()

    out: list[RankingRow] = []
    for i, (sp, p) in enumerate(rows, start=1):
        out.append(
            RankingRow(
                rank=i,
                player_id=p.id,
                name=p.name,
                current_score=sp.current_score,
                prev_season_rank=prev_rank_map.get(p.id),
                top_tags=top_tags_map.get(p.id, []),
                banming_wins=banming_wins_map.get(p.id, 0),
            )
        )
    return out
