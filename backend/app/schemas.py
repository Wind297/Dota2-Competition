from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models import MatchStatus, SeasonStatus


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
    is_active: bool = True
    stats: PlayerStats

    model_config = {"from_attributes": True}


class PlayerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    current_score: int = Field(0, ge=0, description="录入时尚未入系统的累计胜场分，默认 0")


class PlayerPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    is_online: bool | None = None
    current_score: int | None = Field(None, ge=0)
    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if (
            self.name is None
            and self.is_online is None
            and self.current_score is None
            and self.is_active is None
        ):
            raise ValueError("至少需要提供 name / is_online / current_score / is_active 之一")
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
    is_deducted: bool = False
    score_delta: int = 0


class MatchOut(BaseModel):
    id: int
    season_id: int | None = None
    matchday_start: datetime
    actual_time: datetime | None
    sequence_no: int | None = None
    status: MatchStatus
    created_at: datetime
    players: list[MatchPlayerBrief] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MatchCreate(BaseModel):
    player_ids: list[int] = Field(..., min_length=10, max_length=10)


class MatchPatch(BaseModel):
    """编辑已存在的比赛：可改比赛日、场次号、上场名单。"""
    matchday_start: datetime | None = None
    sequence_no: int | None = Field(None, ge=1, le=999)
    player_ids: list[int] | None = Field(None, min_length=10, max_length=10)
    clear_sequence_no: bool = False  # 显式置空场次号

    @model_validator(mode="after")
    def at_least_one_field(self):
        if (
            self.matchday_start is None
            and self.sequence_no is None
            and self.player_ids is None
            and not self.clear_sequence_no
        ):
            raise ValueError("至少需要提供一个可修改字段")
        return self


class MatchResult(BaseModel):
    winner_player_ids: list[int] = Field(..., min_length=5, max_length=5)
    deducted_player_ids: list[int] = Field(default_factory=list, max_length=5)


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


# ── 赛季 ─────────────────────────────────────────────────────────
class SeasonOut(BaseModel):
    id: int
    name: str
    status: SeasonStatus
    started_at: datetime
    ended_at: datetime | None
    is_current: bool = False
    player_count: int = 0
    match_count: int = 0

    model_config = {"from_attributes": True}


class SeasonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    inherit_active_players: bool = Field(
        True,
        description="是否把上一赛季的活跃选手自动加入新赛季（默认 True，积分清零）",
    )


class SeasonRollover(BaseModel):
    """结束当前赛季并开启新赛季。"""
    new_season_name: str = Field(..., min_length=1, max_length=64)
    inherit_active_players: bool = True
