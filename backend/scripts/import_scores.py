"""
用法（在 backend 目录下）:
  python scripts/import_scores.py path/to/initial_scores.csv

CSV 列: name,score （首行可为表头；重名则覆盖当前积分）
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Player  # noqa: E402


def main(path: Path) -> None:
    db = SessionLocal()
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "name" not in reader.fieldnames or "score" not in reader.fieldnames:
                raise SystemExit("CSV 需要包含 name 与 score 列")
            for row in reader:
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                score_s = (row.get("score") or "0").strip()
                try:
                    score = int(score_s)
                except ValueError:
                    raise SystemExit(f"无效积分: {name} -> {score_s}")
                existing = db.scalars(select(Player).where(Player.name == name)).first()
                if existing:
                    existing.current_score = score
                else:
                    db.add(Player(name=name, current_score=score, is_online=True))
        db.commit()
        print("导入完成")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(Path(sys.argv[1]).resolve())
