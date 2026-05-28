from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MatchStatus(str, enum.Enum):
    confirmed = "confirmed"
    completed = "completed"


class SeasonStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[SeasonStatus] = mapped_column(
        Enum(SeasonStatus, native_enum=False),
        default=SeasonStatus.active,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    season_players: Mapped[list[SeasonPlayer]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )
    matches: Mapped[list[Match]] = relationship(back_populates="season")


class Player(Base):
    """跨赛季的选手身份。各赛季的积分、在线状态、是否参与都在 SeasonPlayer 里。"""
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # 历史字段，新代码不再使用（赛季性数据已挪到 SeasonPlayer）。
    # 保留为列以避免破坏老库；新建库会有这些列但都是默认值。
    current_score: Mapped[int] = mapped_column(Integer, default=0)
    is_online: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    match_entries: Mapped[list[MatchPlayer]] = relationship(back_populates="player")
    season_entries: Mapped[list[SeasonPlayer]] = relationship(back_populates="player")


class SeasonPlayer(Base):
    """选手在某个赛季的积分、在线、参与状态。"""
    __tablename__ = "season_players"
    __table_args__ = (UniqueConstraint("season_id", "player_id", name="uq_season_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    current_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        doc="选手是否参与本赛季（出现在本赛季选手池中）",
    )

    season: Mapped[Season] = relationship(back_populates="season_players")
    player: Mapped[Player] = relationship(back_populates="season_entries")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[int | None] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), index=True, nullable=True
    )
    matchday_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sequence_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, native_enum=False),
        default=MatchStatus.confirmed,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    season: Mapped[Season | None] = relationship(back_populates="matches")
    players: Mapped[list[MatchPlayer]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class MatchPlayer(Base):
    __tablename__ = "match_players"
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_match_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    is_winner: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_deducted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    match: Mapped[Match] = relationship(back_populates="players")
    player: Mapped[Player] = relationship(back_populates="match_entries")


class Tag(Base):
    """预定义的选手标签（绝活哥、责任神等）。管理员可启停。"""
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(64), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PlayerLike(Base):
    """游客对某选手在某赛季的点赞（按 voter_token 唯一）。"""
    __tablename__ = "player_likes"
    __table_args__ = (
        UniqueConstraint("season_id", "player_id", "voter_token", name="uq_player_like"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    voter_token: Mapped[str] = mapped_column(String(64), index=True)
    voter_nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PlayerTag(Base):
    """游客给某选手在某赛季打的标签投票。"""
    __tablename__ = "player_tags"
    __table_args__ = (
        UniqueConstraint(
            "season_id", "player_id", "tag_id", "voter_token", name="uq_player_tag_vote"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), index=True)
    voter_token: Mapped[str] = mapped_column(String(64), index=True)
    voter_nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SystemKV(Base):
    __tablename__ = "system_kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256))
