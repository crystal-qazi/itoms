"""Small SQL-file migration runner with a tracking table.

Migration files must be numbered, e.g. 001_initial.sql. They are applied in
lexicographic order and recorded only after successful execution.
"""
from __future__ import annotations

from pathlib import Path

from itoms.db.connection import get_connection

MIGRATION_DIR = Path(__file__).parent / "versions"


def apply_migrations() -> list[str]:
    """Apply pending migrations and return names applied in this invocation."""
    conn = get_connection()
    applied_now: list[str] = []
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (migration_name VARCHAR(255) PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()
        cur.execute("SELECT migration_name FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}
        for path in sorted(MIGRATION_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            sql_text = path.read_text(encoding="utf-8")
            statements = [s.strip() for s in sql_text.split(";") if s.strip()]
            try:
                for statement in statements:
                    cur.execute(statement)
                cur.execute("INSERT INTO schema_migrations (migration_name) VALUES (%s)", (path.name,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            applied_now.append(path.name)
        cur.close()
        return applied_now
    finally:
        conn.close()
