from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models import MatchStatus


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PlayerStats(BaseModel):
    matches_played: int = 0
    matches_won: int = 0


class PlayerOut(BaseModel):
    id: int
    name: str
    current_score: int
    is_online: bool
    stats: PlayerStats

    model_config = {"from_attributes": True}


class PlayerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    current_score: int = Field(0, ge=0, description="录入时尚未入系统的累计胜场分，默认 0")


class PlayerPatch(BaseModel):
    is_online: bool | None = None
    current_score: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.is_online is None and self.current_score is None:
            raise ValueError("至少需要提供 is_online 或 current_score 之一")
        return self


class PlayerBulkRow(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    current_score: int = Field(0, ge=0)


class PlayerBulkImportBody(BaseModel):
    items: list[PlayerBulkRow] = Field(..., min_length=1, max_length=2000)


class PlayerBulkImportResult(BaseModel):
    created: int
    updated: int
    total: int


class MatchPlayerBrief(BaseModel):
    player_id: int
    name: str
    is_winner: bool | None


class MatchOut(BaseModel):
    id: int
    matchday_start: datetime
    actual_time: datetime | None
    status: MatchStatus
    created_at: datetime
    players: list[MatchPlayerBrief] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MatchCreate(BaseModel):
    player_ids: list[int] = Field(..., min_length=10, max_length=10)


class MatchResult(BaseModel):
    winner_player_ids: list[int] = Field(..., min_length=5, max_length=5)


class RankingRow(BaseModel):
    rank: int
    player_id: int
    name: str
    current_score: int


class PresetFilter(BaseModel):
    tier: str | None = None
    today_not_played: bool | None = None
    today_not_won: bool | None = None
    today_played_lte_1: bool | None = None
    today_played_eq_1: bool | None = None
    online_only: bool | None = None


class PresetOut(BaseModel):
    id: str
    label: str
    filters: PresetFilter
