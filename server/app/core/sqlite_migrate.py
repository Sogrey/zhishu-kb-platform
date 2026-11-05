"""SQLite 轻量加列（POC 免 Alembic）。"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ensure_sqlite_columns(engine: Engine) -> None:
    specs = {
        "documents": [
            ("workspace_id", "INTEGER NOT NULL DEFAULT 1"),
            ("valid_from", "DATETIME"),
            ("valid_to", "DATETIME"),
            ("superseded_by", "INTEGER"),
            ("doc_embedding", "JSON"),
        ],
        "chunks": [
            ("workspace_id", "INTEGER NOT NULL DEFAULT 1"),
            ("classification", "INTEGER NOT NULL DEFAULT 2"),
        ],
        "conversations": [
            ("workspace_id", "INTEGER NOT NULL DEFAULT 1"),
            ("user_id", "INTEGER"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in specs.items():
            exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": table},
            ).fetchone()
            if not exists:
                continue
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            have = {r[1] for r in rows}
            for name, ddl in cols:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    logger.info("sqlite added column %s.%s", table, name)
