CREATE OR REPLACE FUNCTION geo.source() RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    RETURN 'ANH-Informacion-Petrolera-2026';

CREATE OR REPLACE FUNCTION geo.best_municipality(query text) RETURNS integer
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH q AS (SELECT core.name_key(query) AS k)
    SELECT id FROM (
        SELECT m.municipality_id AS id, 1.0::real AS score
        FROM core.municipalities m, q WHERE m.name_key = q.k
        UNION ALL
        SELECT a.municipality_id, 0.99::real
        FROM core.municipality_aliases a, q
        WHERE split_part(a.alias_key, ':', 2) = q.k
        UNION ALL
        SELECT m.municipality_id, similarity(m.name_key, q.k)
        FROM core.municipalities m, q
        WHERE similarity(m.name_key, q.k) >= 0.4
    ) s
    ORDER BY score DESC, id
    LIMIT 1
$$;

CREATE OR REPLACE FUNCTION geo.best_field(query text) RETURNS integer
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH q AS (SELECT core.name_key(query) AS k)
    SELECT f.field_id
    FROM core.fields f, q
    WHERE f.name_key = q.k OR similarity(f.name_key, q.k) >= 0.4
    ORDER BY (f.name_key = q.k) DESC, similarity(f.name_key, q.k) DESC,
             f.field_id
    LIMIT 1
$$;

CREATE OR REPLACE FUNCTION geo.best_well(query text) RETURNS integer
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH q AS (SELECT core.name_key(query) AS k)
    SELECT w.well_id
    FROM core.wells w, q
    WHERE w.name_key = q.k OR w.name_key % q.k
    ORDER BY (w.name_key = q.k) DESC, similarity(w.name_key, q.k) DESC,
             w.well_id
    LIMIT 1
$$;

CREATE OR REPLACE FUNCTION geo.fault_ids(query text) RETURNS SETOF integer
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH q AS (SELECT core.name_key(query) AS k),
    best AS (
        SELECT f.name_key
        FROM core.faults f, q
        WHERE f.name_key IS NOT NULL
          AND (f.name_key = q.k OR similarity(f.name_key, q.k) >= 0.4)
        ORDER BY (f.name_key = q.k) DESC, similarity(f.name_key, q.k) DESC
        LIMIT 1
    )
    SELECT f.fault_id FROM core.faults f JOIN best USING (name_key)
$$;

CREATE OR REPLACE FUNCTION geo.resolve_place(query text)
    RETURNS TABLE (kind text, entity_id integer, name text, score real)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH q AS (SELECT core.name_key(query) AS k)
    SELECT * FROM (
        SELECT 'municipality', m.municipality_id, m.name || ' (' ||
               m.department || ')', similarity(m.name_key, q.k)
        FROM core.municipalities m, q WHERE m.name_key % q.k
        UNION ALL
        SELECT 'field', f.field_id, f.name, similarity(f.name_key, q.k)
        FROM core.fields f, q WHERE f.name_key % q.k
        UNION ALL
        SELECT 'well', w.well_id, w.well_name, similarity(w.name_key, q.k)
        FROM core.wells w, q WHERE w.name_key % q.k
        UNION ALL
        SELECT 'seismic_3d', s.survey_id, s.name, similarity(s.name_key, q.k)
        FROM core.seismic_3d s, q WHERE s.name_key % q.k
        UNION ALL
        SELECT 'fault', min(f.fault_id), f.name,
               max(similarity(f.name_key, q.k))
        FROM core.faults f, q WHERE f.name_key % q.k
        GROUP BY f.name
    ) s (kind, entity_id, name, score)
    ORDER BY score DESC, kind, name
    LIMIT 10
$$;

CREATE OR REPLACE FUNCTION geo.fields_in_municipality(
        municipality text, statuses text[] DEFAULT NULL)
    RETURNS TABLE (field text, wells bigint, producing bigint,
                   municipality_name text, department text, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH target AS MATERIALIZED (
        SELECT geo.best_municipality(municipality) AS id
    )
    SELECT coalesce(f.name, '(sin campo)'), count(*),
           count(*) FILTER (WHERE w.status = 'PRODUCTOR'),
           m.name, m.department, geo.source()
    FROM core.wells w
    JOIN target t ON w.municipality_id = t.id
    JOIN core.municipalities m ON m.municipality_id = w.municipality_id
    LEFT JOIN core.fields f ON f.field_id = w.field_id
    WHERE statuses IS NULL OR w.status = ANY (statuses)
    GROUP BY 1, m.name, m.department
    ORDER BY 2 DESC, 1
    LIMIT 500
$$;

CREATE OR REPLACE FUNCTION geo.wells_in_municipality(
        municipality text, statuses text[] DEFAULT NULL,
        max_rows integer DEFAULT 100)
    RETURNS TABLE (well_id integer, well_name text, field text, status text,
                   trajectory text, operator text, lon double precision,
                   lat double precision, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH target AS MATERIALIZED (
        SELECT geo.best_municipality(municipality) AS id
    )
    SELECT w.well_id, w.well_name, f.name, w.status, w.trajectory,
           o.canonical_name, ST_X(w.geom), ST_Y(w.geom), geo.source()
    FROM core.wells w
    JOIN target t ON w.municipality_id = t.id
    LEFT JOIN core.fields f ON f.field_id = w.field_id
    LEFT JOIN core.organizations o ON o.org_id = w.operator_id
    WHERE statuses IS NULL OR w.status = ANY (statuses)
    ORDER BY w.well_name
    LIMIT least(greatest(max_rows, 1), 500)
$$;

CREATE OR REPLACE FUNCTION geo.field_summary(field text)
    RETURNS TABLE (dimension text, value text, wells bigint, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH target AS MATERIALIZED (SELECT geo.best_field(field) AS id),
    w AS MATERIALIZED (
        SELECT w.* FROM core.wells w JOIN target t ON w.field_id = t.id
    )
    SELECT * FROM (
        SELECT 'field', f.name, (SELECT count(*) FROM w), geo.source()
        FROM core.fields f JOIN target t ON f.field_id = t.id
        UNION ALL
        SELECT 'status', coalesce(status, '(sin dato)'), count(*),
               geo.source() FROM w GROUP BY 2
        UNION ALL
        SELECT 'trajectory', coalesce(trajectory, '(sin dato)'), count(*),
               geo.source() FROM w GROUP BY 2
        UNION ALL
        SELECT 'purpose', purpose, count(*), geo.source()
        FROM w WHERE purpose IS NOT NULL GROUP BY 2
        UNION ALL
        SELECT 'operator', coalesce(o.canonical_name, '(sin dato)'),
               count(*), geo.source()
        FROM w LEFT JOIN core.organizations o ON o.org_id = w.operator_id
        GROUP BY 2
        UNION ALL
        SELECT 'municipality', m.name || ' (' || m.department || ')',
               count(*), geo.source()
        FROM w JOIN core.municipalities m USING (municipality_id) GROUP BY 2
        UNION ALL
        SELECT 'contract', contract_name, count(*), geo.source()
        FROM w WHERE contract_name IS NOT NULL GROUP BY 2
        UNION ALL
        SELECT 'bbox', ST_AsText(ST_Envelope(ST_Collect(geom))), count(*),
               geo.source() FROM w HAVING count(*) > 0
    ) s (dimension, value, wells, source)
    ORDER BY array_position(ARRAY['field', 'status', 'trajectory', 'purpose',
             'operator', 'municipality', 'contract', 'bbox'], dimension),
             wells DESC
    LIMIT 500
$$;

CREATE OR REPLACE FUNCTION geo.wells_near_point(
        lon double precision, lat double precision, km real DEFAULT 5,
        statuses text[] DEFAULT NULL, max_rows integer DEFAULT 100)
    RETURNS TABLE (well_id integer, well_name text, field text, status text,
                   distance_km numeric, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH p AS MATERIALIZED (
        SELECT ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 9377)
               AS g
    )
    SELECT w.well_id, w.well_name, f.name, w.status,
           round((ST_Distance(w.geom_ctm12, p.g) / 1000)::numeric, 2),
           geo.source()
    FROM core.wells w
    CROSS JOIN p
    LEFT JOIN core.fields f ON f.field_id = w.field_id
    WHERE ST_DWithin(w.geom_ctm12, p.g, least(km, 50) * 1000)
      AND (statuses IS NULL OR w.status = ANY (statuses))
    ORDER BY 5, w.well_name
    LIMIT least(greatest(max_rows, 1), 500)
$$;
