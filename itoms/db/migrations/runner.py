"""Checksum-verified SQL migration runner with a MySQL advisory lock."""
from __future__ import annotations
import hashlib
from pathlib import Path
from itoms.db.connection import get_connection
MIGRATION_DIR = Path(__file__).parent / "versions"
LOCK_NAME = "itoms_schema_migrations"


def split_sql_statements(sql_text: str) -> list[str]:
    """Split migration SQL without treating semicolons in comments or strings as delimiters."""
    statements: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    index = 0
    length = len(sql_text)
    while index < length:
        char = sql_text[index]
        next_char = sql_text[index + 1] if index + 1 < length else ""
        if quote:
            buffer.append(char)
            if char == "\\" and quote in {"'", '"'} and next_char:
                buffer.append(next_char)
                index += 2
                continue
            if char == quote:
                if next_char == quote:
                    buffer.append(next_char)
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            buffer.append(char)
            index += 1
            continue
        if char == "-" and next_char == "-" and (
            index + 2 == length or sql_text[index + 2].isspace()
        ):
            index += 2
            while index < length and sql_text[index] not in "\r\n":
                index += 1
            if index < length:
                buffer.append("\n")
                index += 1
            continue
        if char == "#":
            while index < length and sql_text[index] not in "\r\n":
                index += 1
            if index < length:
                buffer.append("\n")
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < length and sql_text[index:index + 2] != "*/":
                index += 1
            index = min(index + 2, length)
            continue
        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer.clear()
            index += 1
            continue
        buffer.append(char)
        index += 1
    statement = "".join(buffer).strip()
    if statement:
        statements.append(statement)
    return statements

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
            statements = split_sql_statements(sql_text)
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
