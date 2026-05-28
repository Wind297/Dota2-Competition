from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_utils import create_access_token
from app.config import settings
from app.database import get_db
from app.daily_reset import maybe_reset_daily_online
from app.matchday import get_tz
from app.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    if body.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密码错误")
    maybe_reset_daily_online(db, datetime.now(get_tz()))
    token = create_access_token()
    return LoginResponse(access_token=token)


@router.get("/guest-token", response_model=LoginResponse)
def guest_token():
    """游客只读 token，无需密码，前端负责限制写操作。"""
    token = create_access_token()
    return LoginResponse(access_token=token)
