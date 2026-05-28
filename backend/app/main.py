from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.models import Match, MatchPlayer, Player, SystemKV  # noqa: F401
from app.routers import auth, matches, players, presets, rankings

app = FastAPI(title="Dota2 个人积分赛管理 API")

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


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    # 轻量迁移：为已存在的表补上新增列
    from sqlalchemy import text
    with engine.begin() as conn:
        # matches.sequence_no
        try:
            cols = conn.exec_driver_sql("PRAGMA table_info(matches)").fetchall()
            col_names = {c[1] for c in cols}
            if "sequence_no" not in col_names:
                conn.exec_driver_sql("ALTER TABLE matches ADD COLUMN sequence_no INTEGER")
        except Exception:
            try:
                conn.execute(text("ALTER TABLE matches ADD COLUMN sequence_no INTEGER"))
            except Exception:
                pass

        # match_players.is_deducted, score_delta
        try:
            cols = conn.exec_driver_sql("PRAGMA table_info(match_players)").fetchall()
            col_names = {c[1] for c in cols}
            need_backfill = False
            if "is_deducted" not in col_names:
                conn.exec_driver_sql(
                    "ALTER TABLE match_players ADD COLUMN is_deducted BOOLEAN NOT NULL DEFAULT 0"
                )
                need_backfill = True
            if "score_delta" not in col_names:
                conn.exec_driver_sql(
                    "ALTER TABLE match_players ADD COLUMN score_delta INTEGER NOT NULL DEFAULT 0"
                )
                need_backfill = True
            if need_backfill:
                # 历史数据：把胜者的 score_delta 标为 +1（当时一律是 +1 的逻辑）
                conn.exec_driver_sql(
                    "UPDATE match_players SET score_delta = 1 WHERE is_winner = 1 AND score_delta = 0"
                )
        except Exception:
            try:
                conn.execute(text(
                    "ALTER TABLE match_players ADD COLUMN is_deducted BOOLEAN NOT NULL DEFAULT FALSE"
                ))
            except Exception:
                pass
            try:
                conn.execute(text(
                    "ALTER TABLE match_players ADD COLUMN score_delta INTEGER NOT NULL DEFAULT 0"
                ))
            except Exception:
                pass
            try:
                conn.execute(text(
                    "UPDATE match_players SET score_delta = 1 WHERE is_winner = TRUE AND score_delta = 0"
                ))
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
