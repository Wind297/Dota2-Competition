from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MatchStatus(str, enum.Enum):
    confirmed = "confirmed"
    completed = "completed"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
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


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    players: Mapped[list[MatchPlayer]] = relationship(back_populates="match", cascade="all, delete-orphan")


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


class SystemKV(Base):
    __tablename__ = "system_kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256))
