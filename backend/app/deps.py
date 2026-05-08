from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_utils import verify_access_token
from app.database import get_db
from app.daily_reset import maybe_reset_daily_online
from app.matchday import get_tz


def require_auth(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或令牌无效")
    token = authorization.split(" ", 1)[1].strip()
    if not verify_access_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或令牌无效")
    maybe_reset_daily_online(db, datetime.now(get_tz()))
    return token


AuthToken = Annotated[str, Depends(require_auth)]
