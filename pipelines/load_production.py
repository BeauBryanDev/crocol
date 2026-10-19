import argparse
import csv
import hashlib
import sys
import time
from collections import defaultdict
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from config.settings import ROOT, get_settings

DESCRIPTION = (
    "Seed core.oil_production and core.gas_production from the ANH "
    "'Producción Fiscalizada' CSVs built by "
    "ColBasins/Extract_Oils_and_Gas_Production2025_2026.ipynb. Reloaded from "
    "scratch in one transaction. Usage: magdalena/bin/python "
    "pipelines/load_production.py [--dry-run]"
)
SOURCES = {
    "oil": (ROOT / "ColBasins" / "produccion_crudo_campo_mensual.csv",
            "produccion_crudo", "BPDC", "core.oil_production"),
    "gas": (ROOT / "ColBasins" / "produccion_gas_campo_mensual.csv",
            "produccion_gas", "MPCPDC", "core.gas_production"),
}
COLUMNS = ("month_end", "field", "contract", "municipality", "department",
           "operator", "value", "unit", "field_original", "source_file")
TOLERANCE = 1e-6
MONTHLY_TOTALS = "SELECT month_end::text, sum(value) FROM {} GROUP BY 1"
SYNC_STATE = """
INSERT INTO ops.sync_state
    (target, pipeline_version, item_count, checksum, synced_at, details)
VALUES (%s, 'production-v1', %s, %s, now(), %s)
ON CONFLICT (target) DO UPDATE SET
    pipeline_version = EXCLUDED.pipeline_version,
    item_count = EXCLUDED.item_count,
    checksum = EXCLUDED.checksum,
    synced_at = now(),
    details = EXCLUDED.details
"""


def read_rows(path: Path, value_col: str, unit: str) -> list[tuple]:

    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            if record["unidad"] != unit:
                raise ValueError(f"{path.name}: unexpected unit {record['unidad']}")
            rows.append((record["fecha"], record["campo"], record["contrato"],
                         record["municipio"], record["departamento"],
                         record["operadora"], float(record[value_col]), unit,
                         record["campo_original"], path.name))
    return rows


def monthly_totals(rows: list[tuple]) -> dict[str, float]:

    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[row[0]] += row[6]
    return dict(totals)


def load(conn: psycopg.Connection, table: str, rows: list[tuple]) -> None:

    conn.execute(f"TRUNCATE {table} RESTART IDENTITY")
    with conn.cursor().copy(
            f"COPY {table} ({', '.join(COLUMNS)}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def verify(conn: psycopg.Connection, table: str, rows: list[tuple]) -> dict:

    count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    if count != len(rows):
        raise RuntimeError(f"{table}: {count} rows loaded, {len(rows)} expected")
    expected = monthly_totals(rows)
    loaded = dict(conn.execute(MONTHLY_TOTALS.format(table)).fetchall())
    worst = max(abs(loaded[m] - total) for m, total in expected.items())
    if worst > TOLERANCE * max(expected.values()):
        raise RuntimeError(f"{table}: monthly totals differ by {worst}")
    fields = conn.execute(f"SELECT count(DISTINCT field_key) FROM {table}").fetchone()[0]
    return {"rows": count, "fields": fields, "months": len(expected),
            "max_total_diff": worst}


def run(dry_run: bool) -> None:

    started = time.perf_counter()
    data = {}
    for name, (path, value_col, unit, table) in SOURCES.items():
        if not path.exists():
            sys.exit(f"missing {path}; run the ColBasins notebook first")
        rows = read_rows(path, value_col, unit)
        data[name] = (path, table, rows)
        totals = monthly_totals(rows)
        print(f"{name}: {len(rows)} rows, {len(totals)} months, "
              f"first month total {totals[min(totals)]:.1f} {unit}")
    if dry_run:
        return

    dsn = get_settings().pg_dsn
    if dsn is None:
        sys.exit("PG_DSN is not set in .env")
    with psycopg.connect(dsn.get_secret_value()) as conn, conn.transaction():
        for name, (path, table, rows) in data.items():
            load(conn, table, rows)
            notes = verify(conn, table, rows)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            conn.execute(SYNC_STATE, (f"production_{name}", notes["rows"], digest,
                                      Jsonb({**notes, "file": path.name})))
            print(f"  {table}: {notes}")
    print(f"done in {time.perf_counter() - started:.1f} s")


def main() -> None:

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--dry-run", action="store_true",
                        help="read and check the CSVs, no database writes")
    run(parser.parse_args().dry_run)


if __name__ == "__main__":
    main()
