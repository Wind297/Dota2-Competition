from fastapi import APIRouter

from app.deps import AuthToken
from app.schemas import PresetFilter, PresetOut

router = APIRouter(prefix="/api/presets", tags=["presets"])


_PRESETS: list[PresetOut] = [
    PresetOut(id="high", label="高分场", filters=PresetFilter(tier="high", online_only=True)),
    PresetOut(
        id="mid",
        label="中分场",
        filters=PresetFilter(tier="mid", today_not_played=True, online_only=True),
    ),
    PresetOut(
        id="low",
        label="低分场",
        filters=PresetFilter(tier="low", today_not_played=True, online_only=True),
    ),
    PresetOut(id="fill", label="补位场", filters=PresetFilter(today_not_played=True, online_only=True)),
    PresetOut(
        id="bonus",
        label="红利场",
        filters=PresetFilter(
            today_played_lte_1=True, today_not_won=True, online_only=True
        ),
    ),
    PresetOut(
        id="extra",
        label="加赛场",
        filters=PresetFilter(today_played_eq_1=True, online_only=True),
    ),
    PresetOut(id="open", label="附加赛场", filters=PresetFilter(online_only=True)),
]


@router.get("", response_model=list[PresetOut])
def list_presets(_: AuthToken):
    return _PRESETS
