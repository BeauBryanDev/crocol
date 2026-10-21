import argparse
import sys
import time
from collections import Counter

import psycopg

from config.settings import ROOT, get_settings
from spatial_checks import (
    CHECKS,
    COUNT_FAULTS_NEAR,
    COUNT_FOOTPRINT_CELLS,
    FAULTS_TO_RAW,
    FOOTPRINT_CELL_M,
    INSERT_FAULTS,
    INSERT_FOOTPRINT,
    STAGE_FAULTS,
    record_sync,
)
from spatial_lookups import group_organizations, merge_review, write_review
from spatial_sources import (
    FAULTS,
    Feature,
    SEISMIC_2D,
    SEISMIC_3D,
    WELLS,
    copy_stage,
    load_raw,
    read_features,
    sha256_of,
    stream_2d,
)
from spatial_sql import (
    DEPTH_RELIABLE_FT,
    DISPLAY_TOLERANCE_DEG,
    FOOTPRINT_KM,
    FOOTPRINT_SIMPLIFY_M,
    FT_TO_M,
    INSERT_3D,
    INSERT_FIELDS,
    INSERT_LINES,
    INSERT_METRICS,
    INSERT_MUNICIPALITY,
    INSERT_MUNICIPALITY_ALIAS,
    INSERT_ORGANIZATION,
    INSERT_ORG_ALIAS,
    INSERT_WELLS,
    MUNICIPALITY_PAIRS,
    ORGANIZATION_NAMES,
    TRUNCATE_FACTS,
    TRUNCATE_FAULTS,
    TRUNCATE_FOOTPRINT,
    TRUNCATE_METRICS,
)

DESCRIPTION = (
    "Load the VMM spatial core (wells, 2D and 3D seismic, faults, lookups) "
    "into PostGIS. Only VMM features are stored. "
    "Usage: magdalena/bin/python pipelines/load_spatial.py "
    "[--step raw|facts|faults|metrics|footprint|all] [--sample N] [--dry-run]"
)
REVIEW = ROOT / "docs" / "municipalities_review.csv"


def load_organizations(conn: psycopg.Connection) -> int:

    names = Counter(dict(conn.execute(ORGANIZATION_NAMES).fetchall()))
    groups = group_organizations(names)
    for canonical, variants in sorted(groups.items()):
        org_id = conn.execute(INSERT_ORGANIZATION, (canonical,)).fetchone()[0]
        for variant in variants:
            conn.execute(INSERT_ORG_ALIAS, (variant, variant, org_id))
    return len(groups)


def load_municipalities(conn: psycopg.Connection) -> tuple[int, int]:

    pairs = Counter()
    for department, municipality, wells in conn.execute(MUNICIPALITY_PAIRS):
        pairs[(department or "", municipality)] += wells

    rows, changed = merge_review(pairs, REVIEW)
    if changed:
        write_review(rows, REVIEW)

    canonical: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["canonical_department"], row["canonical_municipality"])
        canonical.setdefault(key, []).append(row)

    for (department, municipality), members in sorted(canonical.items()):
        reviewed = all(member["reviewed"] for member in members)
        params = (municipality, department, reviewed)
        new_id = conn.execute(INSERT_MUNICIPALITY, params).fetchone()[0]
        for member in members:
            conn.execute(INSERT_MUNICIPALITY_ALIAS, (
                member["department"], member["municipality"],
                member["municipality"], new_id))

    reviewed_count = sum(1 for row in rows if row["reviewed"])
    return len(canonical), reviewed_count


def load_facts(conn: psycopg.Connection) -> dict:
    """Lookups, wells, 2D lines and 3D surveys from raw, in one transaction."""
    with conn.transaction():
        conn.execute(TRUNCATE_FACTS)
        organizations = load_organizations(conn)
        conn.execute(INSERT_FIELDS)
        municipalities, reviewed = load_municipalities(conn)
        conn.execute(INSERT_WELLS)
        conn.execute(INSERT_LINES, {"tolerance": DISPLAY_TOLERANCE_DEG})
        conn.execute(INSERT_3D)

    return {
        "organizations_grouped": organizations,
        "municipalities_canonical": municipalities,
        "municipality_rows_reviewed": reviewed,
    }


def stage_faults(conn: psycopg.Connection, faults: list[Feature]) -> None:

    copy_stage(conn, faults)
    conn.execute(STAGE_FAULTS)


def sample_faults(conn: psycopg.Connection, faults: list[Feature],
                  size: int) -> dict:
    """Count faults near VMM data on a sample; nothing is saved."""
    with conn.transaction(force_rollback=True):
        stage_faults(conn, faults[:size])
        near = conn.execute(COUNT_FAULTS_NEAR,
                            {"meters": FOOTPRINT_KM * 1000}).fetchone()[0]
    return {"sample": size, "near_vmm_data": near}


def load_faults(conn: psycopg.Connection, faults: list[Feature]) -> dict:

    with conn.transaction():
        conn.execute(TRUNCATE_FAULTS)
        stage_faults(conn, faults)
        conn.execute(FAULTS_TO_RAW, {"meters": FOOTPRINT_KM * 1000})
        conn.execute(INSERT_FAULTS)
    return {}


def count_footprint_cells(conn: psycopg.Connection) -> dict:

    cells = conn.execute(COUNT_FOOTPRINT_CELLS,
                         {"cell": FOOTPRINT_CELL_M}).fetchone()[0]
    return {"footprint_cells": cells}


def load_footprint(conn: psycopg.Connection) -> dict:

    with conn.transaction():
        conn.execute(TRUNCATE_FOOTPRINT)
        conn.execute(INSERT_FOOTPRINT, {
            "cell": FOOTPRINT_CELL_M,
            "km": FOOTPRINT_KM,
            "simplify": FOOTPRINT_SIMPLIFY_M,
        })
    return {}


def load_metrics(conn: psycopg.Connection) -> dict:
    """Per-well depth (both units, reliability) and nearest fault."""
    low, high = DEPTH_RELIABLE_FT
    with conn.transaction():
        conn.execute(TRUNCATE_METRICS)
        conn.execute(INSERT_METRICS, {"ft_to_m": FT_TO_M, "min_ft": low,
                                      "max_ft": high})
    return {}


def read_sources(step: str) -> dict[str, list[Feature]]:

    sources: dict[str, list[Feature]] = {}
    if step in ("raw", "all"):
        sources["wells"] = read_features(WELLS, "GEOLOGIC_P")
        sources["seismic_2d"] = list(stream_2d(SEISMIC_2D))
        sources["seismic_3d"] = read_features(SEISMIC_3D, "CUENCA_GEO")
    if step in ("faults", "all"):
        sources["faults"] = read_features(FAULTS, None)
    return sources


def run_step(conn: psycopg.Connection, args: argparse.Namespace,
             sources: dict[str, list[Feature]]) -> dict:

    notes: dict = {}
    if args.step in ("raw", "all"):
        for table in ("wells", "seismic_2d", "seismic_3d"):
            load_raw(conn, table, sources[table])
    if args.step in ("facts", "all"):
        notes.update(load_facts(conn))
    if args.step == "faults" and args.sample:
        return sample_faults(conn, sources["faults"], args.sample)
    if args.step in ("faults", "all"):
        notes.update(load_faults(conn, sources["faults"]))
    if args.step in ("facts", "faults", "metrics", "all"):
        notes.update(load_metrics(conn))
    if args.step == "footprint" and args.sample:
        return count_footprint_cells(conn)
    if args.step in ("footprint", "all"):
        notes.update(load_footprint(conn))
    return notes


def run(args: argparse.Namespace) -> None:

    started = time.perf_counter()
    sources = read_sources(args.step)
    sizes = {name: len(features) for name, features in sources.items()}
    print(f"read {sizes} ({time.perf_counter() - started:.1f} s)")
    if args.dry_run:
        return

    dsn = get_settings().pg_dsn
    if dsn is None:
        sys.exit("PG_DSN is not set in .env")
    with psycopg.connect(dsn.get_secret_value()) as conn:
        notes = run_step(conn, args, sources)
        if not args.sample:
            counts = {}
            for name, query in CHECKS.items():
                counts[name] = conn.execute(query).fetchone()[0]
            notes = {**counts, **notes}
            if args.step == "all":
                hashes = {}
                for path in (WELLS, SEISMIC_2D, SEISMIC_3D, FAULTS):
                    hashes[path.name] = sha256_of(path)
                record_sync(conn, counts, hashes)

    print(f"step {args.step} done in {time.perf_counter() - started:.1f} s")
    for name, value in notes.items():
        print(f"  {name:<28} {value}")


def main() -> None:

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--dry-run", action="store_true",
                        help="read and filter the files, no database writes")
    parser.add_argument("--step", default="all",
                        choices=["raw", "facts", "faults", "metrics",
                                 "footprint", "all"])
    parser.add_argument("--sample", type=int, default=0,
                        help="faults or footprint: measure only, save nothing")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
