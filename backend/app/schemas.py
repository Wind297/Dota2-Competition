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


class TopTagItem(BaseModel):
    tag_id: int
    label: str
    count: int


class PlayerOut(BaseModel):
    id: int
    name: str
    current_score: int
    is_online: bool
    is_active: bool = True
    stats: PlayerStats
    like_count: int = 0
    total_played: int = 0
    total_won: int = 0
    win_rate: float = 0.0
    top_tags: list[TopTagItem] = Field(default_factory=list)
    prev_season_rank: int | None = None  # 上赛季决赛名次（1/2/3 or null）

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
    is_practice: bool = False
    status: MatchStatus
    created_at: datetime
    players: list[MatchPlayerBrief] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MatchCreate(BaseModel):
    player_ids: list[int] = Field(..., min_length=10, max_length=10)
    is_practice: bool = False


class MatchPatch(BaseModel):
    """编辑已存在的比赛：可改比赛日、场次号、上场名单、练习赛标记。"""
    matchday_start: datetime | None = None
    sequence_no: int | None = Field(None, ge=1, le=999)
    player_ids: list[int] | None = Field(None, min_length=10, max_length=10)
    clear_sequence_no: bool = False
    is_practice: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if (
            self.matchday_start is None
            and self.sequence_no is None
            and self.player_ids is None
            and not self.clear_sequence_no
            and self.is_practice is None
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
    prev_season_rank: int | None = None


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


class FinalRankEntry(BaseModel):
    """录入一位选手的决赛名次。"""
    player_id: int
    rank: int = Field(..., ge=1, le=3)  # 1=冠军, 2=亚军, 3=季军


class FinalRankBatchBody(BaseModel):
    """批量录入决赛名次（最多 15 人：冠亚季各 5）。"""
    entries: list[FinalRankEntry] = Field(..., min_length=1, max_length=15)


# ── 标签 / 互动 ─────────────────────────────────────────────────
class TagOut(BaseModel):
    id: int
    label: str
    sort_order: int = 0
    is_enabled: bool = True
    player_id: int | None = None

    model_config = {"from_attributes": True}


class TagCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)
    sort_order: int = 0
    is_enabled: bool = True
    player_id: int | None = None  # null=公共标签，有值=仅该选手


class TagPatch(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=64)
    sort_order: int | None = None
    is_enabled: bool | None = None


class VoteBody(BaseModel):
    """游客互动请求（点赞/打标签都用此结构）。"""
    voter_token: str = Field(..., min_length=4, max_length=64)
    voter_nickname: str | None = Field(None, max_length=64)


class TagVoteOut(BaseModel):
    """选手社交聚合数据：本赛季的点赞数、各标签得票数、当前游客投了哪些。"""
    like_count: int = 0
    liked_by_me: bool = False
    tags: list["TagVoteRow"] = Field(default_factory=list)


class TagVoteRow(BaseModel):
    tag_id: int
    label: str
    count: int = 0
    voted_by_me: bool = False


TagVoteOut.model_rebuild()
