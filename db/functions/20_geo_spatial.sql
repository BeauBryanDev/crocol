CREATE OR REPLACE FUNCTION geo.area_of(
        kind text, name text, buffer_km real DEFAULT 2)
    RETURNS geometry
    LANGUAGE plpgsql STABLE
    SET search_path = core, geo, public
AS $$
DECLARE
    target integer;
    meters double precision := least(greatest(buffer_km, 0), 20) * 1000;
BEGIN
    IF kind = 'well' THEN
        target := geo.best_well(name);
        RETURN (SELECT ST_Buffer(geom_ctm12, meters)
                FROM core.wells WHERE well_id = target);
    ELSIF kind = 'field' THEN
        target := geo.best_field(name);
        RETURN (SELECT ST_Buffer(ST_ConvexHull(ST_Collect(geom_ctm12)),
                                 meters)
                FROM core.wells WHERE field_id = target);
    ELSIF kind = 'municipality' THEN
        target := geo.best_municipality(name);
        RETURN (SELECT ST_Buffer(ST_ConvexHull(ST_Collect(geom_ctm12)),
                                 meters)
                FROM core.wells WHERE municipality_id = target);
    END IF;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION geo.seismic_coverage(
        kind text, name text, buffer_km real DEFAULT 2)
    RETURNS TABLE (layer text, decade integer, survey text, items bigint,
                   length_km numeric, area_km2 numeric, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH area AS MATERIALIZED (
        SELECT geo.area_of(kind, name, buffer_km) AS g
    )
    SELECT * FROM (
        SELECT '2D', (l.acq_year / 10) * 10, l.survey_name, count(*),
               round((sum(ST_Length(ST_Intersection(l.geom_ctm12, a.g)))
                      / 1000)::numeric, 1),
               NULL::numeric, geo.source()
        FROM core.seismic_lines l, area a
        WHERE a.g IS NOT NULL AND ST_Intersects(l.geom_ctm12, a.g)
        GROUP BY 2, 3
        UNION ALL
        SELECT '3D', (s.acq_year / 10) * 10, s.name, 1, NULL::numeric,
               round((ST_Area(ST_Intersection(s.geom_ctm12, a.g))
                      / 1e6)::numeric, 1),
               geo.source()
        FROM core.seismic_3d s, area a
        WHERE a.g IS NOT NULL AND ST_Intersects(s.geom_ctm12, a.g)
    ) c (layer, decade, survey, items, length_km, area_km2, source)
    ORDER BY layer, decade NULLS LAST, survey
    LIMIT 500
$$;

CREATE OR REPLACE FUNCTION geo.nearest_lines(well text, n integer DEFAULT 5)
    RETURNS TABLE (line_id integer, survey text, line_name text,
                   acq_year smallint, distance_km numeric, well_name text,
                   source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH w AS MATERIALIZED (
        SELECT well_name, geom_ctm12 AS g
        FROM core.wells WHERE well_id = geo.best_well(well)
    )
    SELECT l.line_id, l.survey_name, l.line_name, l.acq_year,
           round((ST_Distance(l.geom_ctm12, w.g) / 1000)::numeric, 2),
           w.well_name, geo.source()
    FROM core.seismic_lines l, w
    ORDER BY l.geom_ctm12 <-> (SELECT g FROM w)
    LIMIT least(greatest(n, 1), 50)
$$;

CREATE OR REPLACE FUNCTION geo.faults_near(
        kind text, name text, km real DEFAULT 5)
    RETURNS TABLE (fault_id integer, fault_name text, fault_type text,
                   distance_km numeric, length_km numeric, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH area AS MATERIALIZED (SELECT geo.area_of(kind, name, 0) AS g)
    SELECT f.fault_id, f.name, f.fault_type,
           round((ST_Distance(f.geom_ctm12, a.g) / 1000)::numeric, 2),
           round(f.length_km::numeric, 2), geo.source()
    FROM core.faults f, area a
    WHERE a.g IS NOT NULL
      AND ST_DWithin(f.geom_ctm12, a.g, least(greatest(km, 0), 50) * 1000)
    ORDER BY 4, f.name NULLS LAST
    LIMIT 500
$$;

CREATE OR REPLACE FUNCTION geo.wells_near_fault(
        fault text, km real DEFAULT 2, statuses text[] DEFAULT NULL,
        max_rows integer DEFAULT 100)
    RETURNS TABLE (well_id integer, well_name text, field text, status text,
                   distance_km numeric, fault_name text, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH f AS MATERIALIZED (
        SELECT ST_Union(geom_ctm12) AS g, min(name) AS name
        FROM core.faults
        WHERE fault_id IN (SELECT geo.fault_ids(fault))
    )
    SELECT w.well_id, w.well_name, fl.name, w.status,
           round((ST_Distance(w.geom_ctm12, f.g) / 1000)::numeric, 2),
           f.name, geo.source()
    FROM core.wells w
    CROSS JOIN f
    LEFT JOIN core.fields fl ON fl.field_id = w.field_id
    WHERE f.g IS NOT NULL
      AND ST_DWithin(w.geom_ctm12, f.g, least(greatest(km, 0), 20) * 1000)
      AND (statuses IS NULL OR w.status = ANY (statuses))
    ORDER BY 5, w.well_name
    LIMIT least(greatest(max_rows, 1), 500)
$$;

CREATE OR REPLACE FUNCTION geo.locate(query text)
    RETURNS TABLE (kind text, name text, geojson text, source text)
    LANGUAGE plpgsql STABLE
    SET search_path = core, geo, public
AS $$
DECLARE
    hit record;
    shape geometry;
BEGIN
    SELECT * INTO hit FROM geo.resolve_place(query) LIMIT 1;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    IF hit.kind = 'well' THEN
        SELECT geom INTO shape FROM core.wells WHERE well_id = hit.entity_id;
    ELSIF hit.kind = 'field' THEN
        SELECT ST_ConvexHull(ST_Collect(geom)) INTO shape
        FROM core.wells WHERE field_id = hit.entity_id;
    ELSIF hit.kind = 'municipality' THEN
        SELECT ST_ConvexHull(ST_Collect(geom)) INTO shape
        FROM core.wells WHERE municipality_id = hit.entity_id;
    ELSIF hit.kind = 'seismic_3d' THEN
        SELECT geom INTO shape FROM core.seismic_3d
        WHERE survey_id = hit.entity_id;
    ELSIF hit.kind = 'fault' THEN
        SELECT ST_Union(geom) INTO shape FROM core.faults
        WHERE fault_id IN (SELECT geo.fault_ids(hit.name));
    END IF;

    kind := hit.kind;
    name := hit.name;
    geojson := ST_AsGeoJSON(ST_SimplifyPreserveTopology(shape, 0.001), 5);
    source := geo.source();
    RETURN NEXT;
END;
$$;
