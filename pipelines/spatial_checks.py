import psycopg
from psycopg.types.json import Jsonb

from spatial_sources import FAULTS, SEISMIC_2D, SEISMIC_3D, WELLS
from spatial_sql import FOOTPRINT_KM

FOOTPRINT_CELL_M = 5000
FOOTPRINT_CELLS = """
WITH extent AS (
    SELECT ST_SetSRID(ST_Extent(g)::geometry, 9377) AS box
    FROM (SELECT geom_ctm12 AS g FROM core.wells
          UNION ALL SELECT geom_ctm12 FROM core.seismic_lines) s
)
SELECT c.geom
FROM extent, ST_SquareGrid(%(cell)s, extent.box) AS c
WHERE EXISTS (SELECT 1 FROM core.wells w
              WHERE ST_Intersects(w.geom_ctm12, c.geom))
   OR EXISTS (SELECT 1 FROM core.seismic_lines l
              WHERE ST_Intersects(l.geom_ctm12, c.geom))
"""
COUNT_FOOTPRINT_CELLS = f"SELECT count(*) FROM ({FOOTPRINT_CELLS}) cells"
INSERT_FOOTPRINT = f"""
INSERT INTO core.vmm_footprint (method, buffer_km, geom)
SELECT '5 km grid cells with VMM wells or 2D lines, widened by '
       || %(km)s || ' km',
       %(km)s,
       ST_Multi(ST_Transform(ST_SimplifyPreserveTopology(
           ST_Buffer(ST_Union(cells.geom), %(km)s * 1000, 'quad_segs=4'),
           %(simplify)s), 4326))
FROM ({FOOTPRINT_CELLS}) cells
"""

STAGE_FAULTS = """
CREATE TEMP TABLE stage_faults ON COMMIT DROP AS
SELECT fid, props, geom, ST_Transform(geom, 9377) AS geom_ctm12
FROM (SELECT fid, props,
             ST_SetSRID(ST_GeomFromGeoJSON(geojson), 4326) AS geom
      FROM stage_features
      WHERE geojson IS NOT NULL) s
"""
NEAR_VMM_DATA = """
EXISTS (SELECT 1 FROM core.wells w
        WHERE ST_DWithin(w.geom_ctm12, f.geom_ctm12, %(meters)s))
OR EXISTS (SELECT 1 FROM core.seismic_lines l
           WHERE ST_DWithin(l.geom_ctm12, f.geom_ctm12, %(meters)s))
"""
COUNT_FAULTS_NEAR = (
    f"SELECT count(*) FROM stage_faults f WHERE {NEAR_VMM_DATA}")
FAULTS_TO_RAW = f"""
INSERT INTO raw.faults (fid, props, geom)
SELECT f.fid, f.props, f.geom
FROM stage_faults f
WHERE {NEAR_VMM_DATA}
"""
INSERT_FAULTS = """
INSERT INTO core.faults (fault_id, name, fault_type, length_km, geom)
SELECT r.fid,
       core.clean_text(r.props->>'NombreFall'),
       core.clean_text(r.props->>'Tipo'),
       ST_Length(g.geom::geography) / 1000,
       g.geom
FROM raw.faults r
CROSS JOIN LATERAL (
    SELECT ST_Multi(ST_Force2D(r.geom))::geometry(MultiLineString, 4326)
           AS geom
) g
"""

UPSERT_SYNC = """
INSERT INTO ops.sync_state
    (target, pipeline_version, item_count, checksum, synced_at, details)
VALUES (%s, 'spatial-v1', %s, %s, now(), %s)
ON CONFLICT (target) DO UPDATE SET
    pipeline_version = EXCLUDED.pipeline_version,
    item_count = EXCLUDED.item_count,
    checksum = EXCLUDED.checksum,
    synced_at = now(),
    details = EXCLUDED.details
"""

CHECKS = {
    "wells": "SELECT count(*) FROM core.wells",
    "seismic_lines": "SELECT count(*) FROM core.seismic_lines",
    "seismic_3d": "SELECT count(*) FROM core.seismic_3d",
    "faults": "SELECT count(*) FROM core.faults",
    "named_faults": "SELECT count(*) FROM core.faults WHERE name IS NOT NULL",
    "fields": "SELECT count(*) FROM core.fields",
    "municipalities": "SELECT count(*) FROM core.municipalities",
    "organizations": "SELECT count(*) FROM core.organizations",
    "wells_without_municipality":
        "SELECT count(*) FROM core.wells WHERE municipality_id IS NULL",
    "wells_outside_footprint":
        "SELECT count(*) FROM core.wells w JOIN core.vmm_footprint f "
        "ON NOT ST_Intersects(w.geom, f.geom)",
    "invalid_geometries":
        "SELECT (SELECT count(*) FROM core.seismic_lines "
        "WHERE NOT ST_IsValid(geom)) + (SELECT count(*) FROM core.seismic_3d "
        "WHERE NOT ST_IsValid(geom)) + (SELECT count(*) FROM core.faults "
        "WHERE NOT ST_IsValid(geom))",
    "well_metrics": "SELECT count(*) FROM core.well_metrics",
    "wells_with_depth":
        "SELECT count(*) FROM core.well_metrics WHERE depth_ft IS NOT NULL",
    "wells_unreliable_depth":
        "SELECT count(*) FROM core.well_metrics WHERE NOT depth_reliable",
    "footprint_km2":
        "SELECT (SELECT round((ST_Area(geom::geography) / 1e6)::numeric) "
        "FROM core.vmm_footprint)",
}


def record_sync(conn: psycopg.Connection, counts: dict,
                hashes: dict[str, str]) -> None:

    targets = {
        "spatial_wells": ("wells", WELLS),
        "spatial_seismic2d": ("seismic_lines", SEISMIC_2D),
        "spatial_seismic3d": ("seismic_3d", SEISMIC_3D),
        "spatial_faults": ("faults", FAULTS),
    }
    with conn.transaction():
        for target, (check, path) in targets.items():
            details = {"file": path.name, "footprint_km": FOOTPRINT_KM}
            conn.execute(UPSERT_SYNC, (target, counts[check],
                                       hashes.get(path.name, "skipped"),
                                       Jsonb(details)))
