VMM = "VALLE MEDIO DEL MAGDALENA"
FOOTPRINT_KM = 10
FOOTPRINT_SIMPLIFY_M = 500
DISPLAY_TOLERANCE_DEG = 0.0005

STAGE_TABLE = """
CREATE TEMP TABLE stage_features (
    fid     integer PRIMARY KEY,
    props   jsonb NOT NULL,
    geojson text
) ON COMMIT DROP
"""
STAGE_COPY = "COPY stage_features (fid, props, geojson) FROM STDIN"
STAGE_TO_RAW = """
INSERT INTO raw.{table} (fid, props, geom)
SELECT fid, props, ST_SetSRID(ST_GeomFromGeoJSON(geojson), 4326)
FROM stage_features
WHERE geojson IS NOT NULL
"""

TRUNCATE_FACTS = """
TRUNCATE core.wells, core.seismic_lines, core.seismic_3d,
         core.municipality_aliases, core.municipalities, core.fields,
         core.organization_aliases, core.organizations
RESTART IDENTITY CASCADE
"""
TRUNCATE_FAULTS = "TRUNCATE core.faults, raw.faults"
TRUNCATE_FOOTPRINT = "TRUNCATE core.vmm_footprint"

ORGANIZATION_NAMES = """
SELECT n, count(*) FROM (
    SELECT core.clean_text(props->>'OPERATOR_W') FROM raw.wells
    UNION ALL SELECT core.clean_text(props->>'COMPANY_CO') FROM raw.wells
    UNION ALL SELECT core.clean_text(props->>'COMPANY_NA') FROM raw.seismic_2d
    UNION ALL SELECT core.clean_text(props->>'OPERATOR_N') FROM raw.seismic_2d
    UNION ALL SELECT core.clean_text(props->>'COMPANY_OP') FROM raw.seismic_3d
    UNION ALL SELECT core.clean_text(props->>'COMP_SERVI') FROM raw.seismic_3d
) AS names(n)
WHERE n IS NOT NULL
GROUP BY n
"""
INSERT_ORGANIZATION = """
INSERT INTO core.organizations (canonical_name) VALUES (%s) RETURNING org_id
"""
INSERT_ORG_ALIAS = """
INSERT INTO core.organization_aliases (alias_key, alias, org_id)
VALUES (core.name_key(%s), %s, %s)
ON CONFLICT (alias_key) DO NOTHING
"""

MUNICIPALITY_PAIRS = """
SELECT core.clean_text(props->>'DEPARTAMEN'),
       core.clean_text(props->>'WELL_COU_1'),
       count(*)
FROM raw.wells
GROUP BY 1, 2
HAVING core.clean_text(props->>'WELL_COU_1') IS NOT NULL
"""
INSERT_MUNICIPALITY = """
INSERT INTO core.municipalities (name, department, reviewed)
VALUES (%s, %s, %s)
RETURNING municipality_id
"""
INSERT_MUNICIPALITY_ALIAS = """
INSERT INTO core.municipality_aliases (alias_key, alias, municipality_id)
VALUES (core.name_key(coalesce(%s, '')) || ':' || core.name_key(%s), %s, %s)
ON CONFLICT (alias_key) DO NOTHING
"""

INSERT_FIELDS = """
INSERT INTO core.fields (name)
SELECT mode() WITHIN GROUP (ORDER BY n)
FROM (SELECT core.clean_text(props->>'FIELD_ABRE') AS n FROM raw.wells) s
WHERE n IS NOT NULL
GROUP BY core.name_key(n)
"""

INSERT_WELLS = """
INSERT INTO core.wells (
    well_id, uwi, uwi_duplicate, well_name, department, municipality_raw,
    municipality_id, field_id, contract_name, lahee_class, status,
    trajectory, purpose, operator_id, company_id, z_value_raw, geom)
SELECT r.fid,
       btrim(r.props->>'UWI'),
       count(*) OVER (PARTITION BY btrim(r.props->>'UWI')) > 1,
       coalesce(core.clean_text(r.props->>'WELL_NAME'),
                btrim(r.props->>'UWI')),
       core.clean_text(r.props->>'DEPARTAMEN'),
       core.clean_text(r.props->>'WELL_COU_1'),
       ma.municipality_id,
       f.field_id,
       core.clean_text(r.props->>'CONTRATO'),
       CASE WHEN l.lahee ~ '^A2[ABC]$'
            THEN 'A2' || lower(right(l.lahee, 1)) ELSE l.lahee END,
       core.clean_text(r.props->>'WELL_STA_1'),
       CASE WHEN t.kind IN ('VERTICAL', 'DIRECCIONAL', 'HORIZONTAL',
                            'TIPO J', 'TIPO S') THEN t.kind END,
       CASE WHEN t.kind IN ('INYECTOR', 'ESTRATIGRAFICO',
                            'CAPTADOR DE AGUA', 'PRODUCTOR') THEN t.kind END,
       op.org_id,
       co.org_id,
       NULLIF(NULLIF(ST_Z(r.geom), -9999), 0),
       ST_Force2D(r.geom)::geometry(Point, 4326)
FROM raw.wells r
CROSS JOIN LATERAL (SELECT rtrim(core.clean_text(r.props->>'WELLTYPE'), '-')
                    AS kind) t
CROSS JOIN LATERAL (SELECT upper(core.clean_text(r.props->>'WELL_CLA_1'))
                    AS lahee) l
LEFT JOIN core.municipality_aliases ma
       ON ma.alias_key =
          core.name_key(coalesce(core.clean_text(r.props->>'DEPARTAMEN'), ''))
          || ':' || core.name_key(core.clean_text(r.props->>'WELL_COU_1'))
LEFT JOIN core.fields f
       ON f.name_key = core.name_key(core.clean_text(r.props->>'FIELD_ABRE'))
LEFT JOIN core.organization_aliases op
       ON op.alias_key = core.name_key(core.clean_text(r.props->>'OPERATOR_W'))
LEFT JOIN core.organization_aliases co
       ON co.alias_key = core.name_key(core.clean_text(r.props->>'COMPANY_CO'))
"""

INSERT_LINES = """
INSERT INTO core.seismic_lines (
    line_id, survey_name, line_name, segment, contractor_id, operator_id,
    spread_type, acq_date, acq_year, acq_date_precision, original_datum,
    sp_first, sp_last, contract_name, length_km, geom, geom_display)
SELECT r.fid,
       coalesce(core.clean_text(r.props->>'SURVEY_NAM'), 'SIN NOMBRE'),
       coalesce(core.clean_text(r.props->>'LINE_NAME'), r.fid::text),
       core.clean_text(r.props->>'TRAMO_LINE'),
       con.org_id,
       op.org_id,
       core.clean_text(r.props->>'ARRANG_TYP'),
       d.acq_date,
       coalesce(core.plausible_year(extract(year FROM d.acq_date)::integer),
                n.name_year),
       CASE WHEN d.acq_date IS NOT NULL THEN d.precision
            WHEN n.name_year IS NOT NULL THEN 'name' END,
       core.clean_text(r.props->>'DATUM'),
       core.clean_text(r.props->>'PUNTO_INIC'),
       core.clean_text(r.props->>'PUNTO_FINA'),
       core.clean_text(r.props->>'CONTRATO'),
       ST_Length(g.geom::geography) / 1000,
       g.geom,
       ST_Multi(ST_SimplifyPreserveTopology(g.geom, %(tolerance)s))
FROM raw.seismic_2d r
CROSS JOIN LATERAL (SELECT btrim(r.props->>'ANO_ADQ') AS v) a
CROSS JOIN LATERAL (
    SELECT CASE
               WHEN a.v ~ '^\\d{4}-\\d{2}-\\d{2}$'
                   THEN core.safe_date(a.v, 'YYYY-MM-DD')
               WHEN a.v ~ '^\\d{2}/\\d{2}/\\d{4}$'
                   THEN core.safe_date(a.v, 'DD/MM/YYYY')
               WHEN a.v ~ '^\\d{4}$' THEN core.safe_date(a.v, 'YYYY')
           END AS acq_date,
           CASE WHEN a.v ~ '^\\d{4}$' THEN 'year' ELSE 'day' END AS precision
) d
CROSS JOIN LATERAL (
    SELECT core.plausible_year(core.year_from_name(r.props->>'SURVEY_NAM'))
           AS name_year
) n
CROSS JOIN LATERAL (
    SELECT ST_Multi(ST_Force2D(r.geom))::geometry(MultiLineString, 4326)
           AS geom
) g
LEFT JOIN core.organization_aliases con
       ON con.alias_key = core.name_key(core.clean_text(r.props->>'COMPANY_NA'))
LEFT JOIN core.organization_aliases op
       ON op.alias_key = core.name_key(core.clean_text(r.props->>'OPERATOR_N'))
"""

INSERT_3D = """
INSERT INTO core.seismic_3d (
    survey_id, name, contract_name, operator_id, contractor_id, acq_date,
    acq_year, acq_year_source, area_km2, geom)
SELECT r.fid,
       coalesce(core.clean_text(r.props->>'NOMBRE'), r.fid::text),
       core.clean_text(r.props->>'CONTRATO'),
       op.org_id,
       con.org_id,
       d.acq_date,
       coalesce(extract(year FROM d.acq_date)::integer, n.name_year),
       CASE WHEN d.acq_date IS NOT NULL THEN 'date'
            WHEN n.name_year IS NOT NULL THEN 'name' END,
       ST_Area(g.geom::geography) / 1e6,
       g.geom
FROM raw.seismic_3d r
CROSS JOIN LATERAL (
    SELECT NULLIF(core.safe_date(
               substring(r.props->>'FECHA_ADQU'
                         FROM '\\d{2} [A-Za-z]{3} \\d{4}'),
               'DD Mon YYYY'), DATE '1900-01-01') AS acq_date
) d
CROSS JOIN LATERAL (
    SELECT core.plausible_year(core.year_from_name(r.props->>'NOMBRE'))
           AS name_year
) n
CROSS JOIN LATERAL (
    SELECT ST_Multi(ST_CollectionExtract(
               ST_MakeValid(ST_Force2D(r.geom)), 3))
           ::geometry(MultiPolygon, 4326) AS geom
) g
LEFT JOIN core.organization_aliases op
       ON op.alias_key = core.name_key(core.clean_text(r.props->>'COMPANY_OP'))
LEFT JOIN core.organization_aliases con
       ON con.alias_key = core.name_key(core.clean_text(r.props->>'COMP_SERVI'))
"""
