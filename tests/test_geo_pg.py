import json

import psycopg
import pytest

from config.settings import get_settings

pytestmark = pytest.mark.integration
OPTIONS = "-c default_transaction_read_only=on -c statement_timeout=5s"
SOURCE = "ANH-Informacion-Petrolera-2026"


def connect() -> psycopg.Connection | None:

    dsn = get_settings().pg_dsn
    if dsn is None:
        return None
    try:
        return psycopg.connect(dsn.get_secret_value(), options=OPTIONS,
                               autocommit=True, connect_timeout=2)
    except psycopg.OperationalError:
        return None


@pytest.fixture(scope="module")
def conn() -> psycopg.Connection:

    connection = connect()
    if connection is None:
        pytest.skip("vmm-postgis is not reachable")
    loaded = connection.execute(
        "SELECT to_regclass('core.wells') IS NOT NULL").fetchone()[0]
    if not loaded:
        pytest.skip("spatial core is not loaded")
    yield connection
    connection.close()


def rows(conn: psycopg.Connection, sql: str, *args: object) -> list[tuple]:

    return conn.execute(sql, args).fetchall()


def test_municipality_counts_match_the_source(
        conn: psycopg.Connection) -> None:
    total = rows(conn, "SELECT sum(wells) FROM "
                       "geo.fields_in_municipality(%s)", "barrancabermeja")
    assert total[0][0] == 3687


def test_names_resolve_without_accents(conn: psycopg.Connection) -> None:
    hit = rows(conn, "SELECT kind, name FROM geo.resolve_place(%s)", "yondo")
    assert hit[0] == ("municipality", "YONDÓ (ANTIOQUIA)")


def test_every_result_carries_the_source(conn: psycopg.Connection) -> None:
    sources = rows(conn, "SELECT DISTINCT source FROM "
                         "geo.field_summary(%s)", "Casabe")
    assert sources == [(SOURCE,)]


def test_wells_near_point_are_sorted_and_bounded(
        conn: psycopg.Connection) -> None:
    found = rows(conn, "SELECT distance_km FROM "
                       "geo.wells_near_point(%s, %s, 2)", -73.85, 7.07)
    distances = [row[0] for row in found]
    assert distances and distances == sorted(distances)
    assert max(distances) <= 2


def test_seismic_coverage_reports_2d_and_3d(conn: psycopg.Connection) -> None:
    layers = rows(conn, "SELECT DISTINCT layer FROM geo.seismic_coverage("
                        "'municipality', %s, 2)", "Barrancabermeja")
    assert {row[0] for row in layers} == {"2D", "3D"}


def test_nearest_lines_and_faults(conn: psycopg.Connection) -> None:
    lines = rows(conn, "SELECT distance_km FROM geo.nearest_lines(%s, 3)",
                 "CASABE-1")
    assert len(lines) == 3 and lines[0][0] < 1
    faults = rows(conn, "SELECT fault_name FROM geo.faults_near("
                        "'field', %s, 5)", "La Cira")
    assert "Falla de Infantas" in {row[0] for row in faults}
    wells = rows(conn, "SELECT well_name FROM geo.wells_near_fault(%s, 2)",
                 "falla de cimitarra")
    assert wells


def test_locate_returns_valid_geojson(conn: psycopg.Connection) -> None:
    found = rows(conn, "SELECT kind, geojson FROM geo.locate(%s)", "Casabe")
    assert found[0][0] == "field"
    assert json.loads(found[0][1])["type"] in {"Polygon", "Point"}


def test_unknown_place_returns_nothing(conn: psycopg.Connection) -> None:
    assert rows(conn, "SELECT * FROM geo.fields_in_municipality(%s)",
                "Ciudad Inexistente XYZ") == []


def test_api_session_cannot_write(conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        conn.execute("UPDATE core.wells SET status = status WHERE false")
