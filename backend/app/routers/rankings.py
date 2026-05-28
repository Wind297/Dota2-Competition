from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthToken
from app.models import Player, Season, SeasonPlayer
from app.schemas import RankingRow
from app.seasons import get_active_season

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
            RankingRow(rank=i, player_id=p.id, name=p.name, current_score=sp.current_score)
        )
    return out
