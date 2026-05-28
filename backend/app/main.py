from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.models import (  # noqa: F401
    Match, MatchPlayer, Player, PlayerLike, PlayerTag, Season, SeasonPlayer, SystemKV, Tag,
)
from app.routers import auth, matches, players, presets, rankings, seasons, tags

app = FastAPI(title="Dota2 武汉点神杯 · 个人积分赛 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(rankings.router)
app.include_router(presets.router)
app.include_router(seasons.router)
app.include_router(tags.router)


def _has_column(conn, table: str, col: str) -> bool:
    try:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return col in {r[1] for r in rows}
    except Exception:
        return True  # 非 SQLite，让后续 ALTER 自己处理


def _safe_alter(conn, sql: str) -> None:
    """容错执行 ALTER 语句（列已存在等情况忽略）。"""
    from sqlalchemy import text
    try:
        conn.exec_driver_sql(sql)
    except Exception:
        try:
            conn.execute(text(sql))
        except Exception:
            pass


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        # ── 列迁移（兼容旧库）─────────────────────────────────
        if not _has_column(conn, "matches", "sequence_no"):
            _safe_alter(conn, "ALTER TABLE matches ADD COLUMN sequence_no INTEGER")
        if not _has_column(conn, "matches", "season_id"):
            _safe_alter(conn, "ALTER TABLE matches ADD COLUMN season_id INTEGER")

        if not _has_column(conn, "match_players", "is_deducted"):
            _safe_alter(conn, "ALTER TABLE match_players ADD COLUMN is_deducted BOOLEAN NOT NULL DEFAULT 0")
        if not _has_column(conn, "match_players", "score_delta"):
            _safe_alter(conn, "ALTER TABLE match_players ADD COLUMN score_delta INTEGER NOT NULL DEFAULT 0")
            # 旧数据胜者补 +1
            try:
                conn.exec_driver_sql(
                    "UPDATE match_players SET score_delta = 1 WHERE is_winner = 1 AND score_delta = 0"
                )
            except Exception:
                pass

        # ── 赛季初始化 ────────────────────────────────────────
        # 检查是否已有任何赛季；若无，则创建「第 1 赛季」并把现有数据划归该赛季
        try:
            season_count = conn.exec_driver_sql("SELECT COUNT(*) FROM seasons").fetchone()[0]
        except Exception:
            season_count = 0

        if season_count == 0:
            # 数据是否真的存在
            try:
                player_total = conn.exec_driver_sql("SELECT COUNT(*) FROM players").fetchone()[0]
            except Exception:
                player_total = 0

            # 创建第 1 赛季
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
            try:
                conn.exec_driver_sql(
                    "INSERT INTO seasons (name, status, started_at) VALUES (?, ?, ?)",
                    ("第 1 赛季", "active", now_iso),
                )
            except Exception:
                # 部分数据库不支持 ? 占位时退化
                from sqlalchemy import text
                conn.execute(
                    text("INSERT INTO seasons (name, status, started_at) VALUES (:n, :s, :t)"),
                    {"n": "第 1 赛季", "s": "active", "t": now_iso},
                )

            new_season_id = conn.exec_driver_sql(
                "SELECT id FROM seasons WHERE name = ?", ("第 1 赛季",)
            ).fetchone()
            new_season_id = new_season_id[0] if new_season_id else None

            if new_season_id is not None and player_total > 0:
                # 把现有 players 数据迁移到 SeasonPlayer
                try:
                    conn.exec_driver_sql(
                        "INSERT INTO season_players (season_id, player_id, current_score, is_online, is_active) "
                        "SELECT ?, id, COALESCE(current_score, 0), COALESCE(is_online, 1), 1 FROM players",
                        (new_season_id,),
                    )
                except Exception:
                    pass
                # 历史比赛归到第 1 赛季
                try:
                    conn.exec_driver_sql(
                        "UPDATE matches SET season_id = ? WHERE season_id IS NULL",
                        (new_season_id,),
                    )
                except Exception:
                    pass

        # ── 种子标签：每次启动都补缺（已存在的不动） ─────────
        seed_labels = [
            "绝活哥", "责任神", "该溜子", "神来之笔", "背锅侠",
            "节奏大师", "哈是老六", "挨打第一名", "AME", "侦察兵",
            "Solo神", "当爹又当妈",
        ]
        try:
            existing_rows = conn.exec_driver_sql("SELECT label FROM tags").fetchall()
            existing_labels = {r[0] for r in existing_rows}
        except Exception:
            existing_labels = set()

        from datetime import datetime as _dt, timezone as _tz
        _now_iso = _dt.now(_tz.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        for i, label in enumerate(seed_labels):
            if label in existing_labels:
                continue
            try:
                conn.exec_driver_sql(
                    "INSERT INTO tags (label, sort_order, is_enabled, created_at) "
                    "VALUES (?, ?, 1, ?)",
                    (label, i, _now_iso),
                )
            except Exception:
                pass


@app.get("/api/health")
def health():
    return {"ok": True}


_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


if _STATIC_DIR.is_dir():
    assets = _STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = _STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_STATIC_DIR / "index.html")
