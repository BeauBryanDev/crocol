import argparse
import sys
from pathlib import Path

import psycopg

from config.settings import get_settings

DESCRIPTION = (
    "Apply pending SQL migrations in db/migrations (NNNN_name.sql), "
    "each in its own transaction, then the re-runnable db/functions/*.sql. "
    "Usage: magdalena/bin/python db/migrate.py [--dry-run]"
)
MIGRATIONS = Path(__file__).resolve().parent / "migrations"
FUNCTIONS = Path(__file__).resolve().parent / "functions"
PATTERN = "[0-9][0-9][0-9][0-9]_*.sql"
BOOTSTRAP = """
CREATE SCHEMA IF NOT EXISTS ops;
CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""
RECORD = "INSERT INTO ops.schema_migrations (version) VALUES (%s)"


def pending(conn: psycopg.Connection) -> list[Path]:
    rows = conn.execute("SELECT version FROM ops.schema_migrations")
    applied = {row[0] for row in rows}
    files = sorted(MIGRATIONS.glob(PATTERN))
    return [path for path in files if path.stem not in applied]


def apply(conn: psycopg.Connection, path: Path) -> None:
    with conn.transaction():
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute(RECORD, (path.stem,))


def apply_functions(conn: psycopg.Connection, dry_run: bool) -> None:
    """Re-runnable CREATE OR REPLACE files, applied after every migration."""
    for path in sorted(FUNCTIONS.glob("*.sql")):
        if dry_run:
            print(f"functions: {path.name}")
            continue
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
        print(f"functions applied: {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dsn = get_settings().pg_dsn
    if dsn is None:
        sys.exit("PG_DSN is not set in .env")

    with psycopg.connect(dsn.get_secret_value()) as conn:
        with conn.transaction():
            conn.execute(BOOTSTRAP)

        todo = pending(conn)
        if not todo:
            print("no pending migrations")

        for path in todo:
            if args.dry_run:
                print(f"pending: {path.name}")
                continue
            apply(conn, path)
            print(f"applied: {path.name}")

        apply_functions(conn, args.dry_run)


if __name__ == "__main__":
    main()
