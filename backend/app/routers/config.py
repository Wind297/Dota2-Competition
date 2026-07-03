from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config_helpers import get_deduct_threshold, set_deduct_threshold
from app.database import get_db
from app.deps import AuthToken
from app.schemas import ConfigOut, ConfigPatch

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigOut)
def get_config(_: AuthToken, db: Session = Depends(get_db)):
    return ConfigOut(deduct_threshold=get_deduct_threshold(db))


@router.patch("", response_model=ConfigOut)
def patch_config(body: ConfigPatch, _: AuthToken, db: Session = Depends(get_db)):
    set_deduct_threshold(db, body.deduct_threshold)
    db.commit()
    return ConfigOut(deduct_threshold=body.deduct_threshold)
