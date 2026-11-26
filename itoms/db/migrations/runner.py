"""Checksum-verified SQL migration runner with a MySQL advisory lock."""
from __future__ import annotations
import hashlib
from pathlib import Path
from itoms.db.connection import get_connection
MIGRATION_DIR = Path(__file__).parent / "versions"
LOCK_NAME = "itoms_schema_migrations"

def apply_migrations() -> list[str]:
    """Apply pending SQL migrations; refuse silently changed applied migrations."""
    conn = get_connection()
    applied_now: list[str] = []
    cur = conn.cursor()
    locked = False
    try:
        cur.execute("SELECT GET_LOCK(%s, 30)", (LOCK_NAME,))
        locked = cur.fetchone()[0] == 1
        if not locked:
            raise RuntimeError("Could not acquire database migration lock.")
        cur.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_name VARCHAR(255) PRIMARY KEY, checksum CHAR(64) NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("SHOW COLUMNS FROM schema_migrations LIKE 'checksum'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE schema_migrations ADD COLUMN checksum CHAR(64) NULL")
        conn.commit()
        cur.execute("SELECT migration_name, checksum FROM schema_migrations")
        applied = {row[0]: row[1] for row in cur.fetchall()}
        for path in sorted(MIGRATION_DIR.glob("*.sql")):
            sql_text = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()
            if path.name in applied:
                existing = applied[path.name]
                if existing and existing != checksum:
                    raise RuntimeError(f"Applied migration modified: {path.name}")
                if not existing:
                    cur.execute("UPDATE schema_migrations SET checksum=%s WHERE migration_name=%s", (checksum, path.name))
                    conn.commit()
                continue
            statements = [s.strip() for s in sql_text.split(";") if s.strip()]
            try:
                for statement in statements:
                    cur.execute(statement)
                cur.execute("INSERT INTO schema_migrations (migration_name, checksum) VALUES (%s, %s)", (path.name, checksum))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            applied_now.append(path.name)
        return applied_now
    finally:
        if locked:
            try:
                cur.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
                cur.fetchone()
            except Exception:
                pass
        cur.close()
        conn.close()
