from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = BACKEND_DIR / "umojafunds.sqlite3"
BACKUP_DIR = BACKEND_DIR / "backups"


def main() -> None:
    if not DATABASE_PATH.exists():
        raise SystemExit(f"Database not found: {DATABASE_PATH}")

    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"umojafunds-{timestamp}.sqlite3"
    shutil.copy2(DATABASE_PATH, backup_path)
    print(backup_path)


if __name__ == "__main__":
    main()
