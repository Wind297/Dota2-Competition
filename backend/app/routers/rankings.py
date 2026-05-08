from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthToken
from app.models import Player
from app.schemas import RankingRow

router = APIRouter(prefix="/api/rankings", tags=["rankings"])


@router.get("", response_model=list[RankingRow])
def rankings(_: AuthToken, db: Session = Depends(get_db)):
    players = db.scalars(select(Player).order_by(Player.current_score.desc(), Player.name)).all()
    out: list[RankingRow] = []
    for i, p in enumerate(players, start=1):
        out.append(
            RankingRow(rank=i, player_id=p.id, name=p.name, current_score=p.current_score)
        )
    return out
