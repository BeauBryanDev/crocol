-- Well database questions (Stage 11). Inside a SQL function a column name
-- wins over a parameter of the same name, so every filter parameter is
-- written qualified by its function name.

CREATE OR REPLACE FUNCTION geo.best_operator(query text) RETURNS integer
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH q AS (SELECT core.name_key(query) AS k)
    SELECT id FROM (
        SELECT o.org_id AS id, 1.0::real AS score
        FROM core.organizations o, q WHERE o.name_key = q.k
        UNION ALL
        SELECT a.org_id, 0.99::real
        FROM core.organization_aliases a, q WHERE a.alias_key = q.k
        UNION ALL
        SELECT o.org_id, similarity(o.name_key, q.k)
        FROM core.organizations o, q
        WHERE similarity(o.name_key, q.k) >= 0.4
    ) s
    ORDER BY score DESC, id
    LIMIT 1
$$;

-- Wells matching every given filter; a filter that resolves to nothing
-- matches no well.
CREATE OR REPLACE FUNCTION geo.well_set(
        municipality text, field text, department text, operator text,
        statuses text[], trajectory text, purpose text)
    RETURNS SETOF integer
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH t AS MATERIALIZED (
        SELECT geo.best_municipality(well_set.municipality) AS mid,
               geo.best_field(well_set.field) AS fid,
               geo.best_operator(well_set.operator) AS oid
    )
    SELECT w.well_id
    FROM core.wells w, t
    WHERE (well_set.municipality IS NULL OR w.municipality_id = t.mid)
      AND (well_set.field IS NULL OR w.field_id = t.fid)
      AND (well_set.operator IS NULL OR w.operator_id = t.oid)
      AND (well_set.department IS NULL
           OR core.name_key(w.department)
              = core.name_key(well_set.department))
      AND (well_set.statuses IS NULL
           OR w.status = ANY (well_set.statuses))
      AND (well_set.trajectory IS NULL
           OR w.trajectory = well_set.trajectory)
      AND (well_set.purpose IS NULL OR w.purpose = well_set.purpose)
$$;

-- What each filter resolved to, for the evidence passage.
CREATE OR REPLACE FUNCTION geo.well_filter_label(
        municipality text, field text, department text, operator text,
        statuses text[], trajectory text, purpose text)
    RETURNS text
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH r AS (
        SELECT (SELECT m.name || ' (' || m.department || ')'
                FROM core.municipalities m
                WHERE m.municipality_id = geo.best_municipality(
                    well_filter_label.municipality)) AS municipality_name,
               (SELECT f.name FROM core.fields f
                WHERE f.field_id = geo.best_field(
                    well_filter_label.field)) AS field_name,
               (SELECT o.canonical_name FROM core.organizations o
                WHERE o.org_id = geo.best_operator(
                    well_filter_label.operator)) AS operator_name
    )
    SELECT coalesce(nullif(concat_ws('; ',
        'municipio "' || well_filter_label.municipality || '" = '
            || coalesce(r.municipality_name, 'SIN COINCIDENCIA'),
        'campo "' || well_filter_label.field || '" = '
            || coalesce(r.field_name, 'SIN COINCIDENCIA'),
        'operador "' || well_filter_label.operator || '" = '
            || coalesce(r.operator_name, 'SIN COINCIDENCIA'),
        'departamento = ' || upper(well_filter_label.department),
        'estado = ' || array_to_string(well_filter_label.statuses, ', '),
        'trayectoria = ' || well_filter_label.trajectory,
        'propósito = ' || well_filter_label.purpose
    ), ''), 'todos los pozos del VMM')
    FROM r
$$;

CREATE OR REPLACE FUNCTION geo.well_stats(
        municipality text, field text, department text, operator text,
        statuses text[], trajectory text, purpose text,
        group_dim text DEFAULT NULL)
    RETURNS TABLE (grp text, wells bigint, producing bigint,
                   with_depth bigint, without_depth bigint,
                   unreliable_depth bigint,
                   mean_depth_ft numeric, mean_depth_m numeric,
                   max_depth_ft numeric, max_depth_m numeric,
                   mean_fault_km numeric, min_fault_km numeric,
                   matched text, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH s AS MATERIALIZED (
        SELECT * FROM geo.well_set(
            well_stats.municipality, well_stats.field, well_stats.department,
            well_stats.operator, well_stats.statuses, well_stats.trajectory,
            well_stats.purpose) AS well_id
    ),
    picked AS (
        SELECT CASE well_stats.group_dim
                   WHEN 'field' THEN coalesce(f.name, '(sin campo)')
                   WHEN 'municipality' THEN coalesce(
                       mu.name || ' (' || mu.department || ')',
                       '(sin municipio)')
                   WHEN 'operator' THEN coalesce(o.canonical_name,
                                                 '(sin dato)')
                   WHEN 'field_operator' THEN
                       coalesce(f.name, '(sin campo)') || ' | '
                       || coalesce(o.canonical_name, '(sin dato)')
                   WHEN 'status' THEN coalesce(w.status, '(sin dato)')
                   WHEN 'trajectory' THEN coalesce(w.trajectory,
                                                   '(sin dato)')
                   WHEN 'purpose' THEN coalesce(w.purpose, '(sin dato)')
                   ELSE 'TODOS'
               END AS grp,
               w.status AS well_status, m.depth_ft, m.depth_m,
               m.depth_reliable, m.nearest_fault_km
        FROM s
        JOIN core.wells w USING (well_id)
        LEFT JOIN core.well_metrics m USING (well_id)
        LEFT JOIN core.fields f ON f.field_id = w.field_id
        LEFT JOIN core.municipalities mu
               ON mu.municipality_id = w.municipality_id
        LEFT JOIN core.organizations o ON o.org_id = w.operator_id
    )
    SELECT picked.grp, count(*),
           count(*) FILTER (WHERE well_status = 'PRODUCTOR'),
           count(depth_ft),
           count(*) - count(depth_ft),
           count(*) FILTER (WHERE NOT depth_reliable),
           round(avg(depth_ft) FILTER (WHERE depth_reliable)::numeric),
           round(avg(depth_m) FILTER (WHERE depth_reliable), 1),
           round(max(depth_ft) FILTER (WHERE depth_reliable)::numeric),
           max(depth_m) FILTER (WHERE depth_reliable),
           round(avg(nearest_fault_km), 2),
           min(nearest_fault_km),
           geo.well_filter_label(
               well_stats.municipality, well_stats.field,
               well_stats.department, well_stats.operator,
               well_stats.statuses, well_stats.trajectory,
               well_stats.purpose),
           geo.source()
    FROM picked
    GROUP BY picked.grp
    ORDER BY 2 DESC, 1
    LIMIT 200
$$;

CREATE OR REPLACE FUNCTION geo.well_list(
        municipality text, field text, department text, operator text,
        statuses text[], trajectory text, purpose text,
        order_by text DEFAULT 'name', max_fault_km real DEFAULT NULL,
        n integer DEFAULT 20)
    RETURNS TABLE (well_name text, field_name text, municipality_name text,
                   well_status text, well_trajectory text,
                   operator_name text, depth_ft double precision,
                   depth_m numeric, depth_reliable boolean,
                   nearest_fault text, fault_km numeric, matched text,
                   source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH s AS MATERIALIZED (
        SELECT * FROM geo.well_set(
            well_list.municipality, well_list.field, well_list.department,
            well_list.operator, well_list.statuses, well_list.trajectory,
            well_list.purpose) AS well_id
    )
    SELECT w.well_name, f.name, mu.name, w.status, w.trajectory,
           o.canonical_name, m.depth_ft, m.depth_m, m.depth_reliable,
           coalesce(m.nearest_fault_name, '(falla sin nombre)'),
           m.nearest_fault_km,
           geo.well_filter_label(
               well_list.municipality, well_list.field,
               well_list.department, well_list.operator,
               well_list.statuses, well_list.trajectory,
               well_list.purpose),
           geo.source()
    FROM s
    JOIN core.wells w USING (well_id)
    LEFT JOIN core.well_metrics m USING (well_id)
    LEFT JOIN core.fields f ON f.field_id = w.field_id
    LEFT JOIN core.municipalities mu
           ON mu.municipality_id = w.municipality_id
    LEFT JOIN core.organizations o ON o.org_id = w.operator_id
    WHERE (well_list.order_by <> 'depth' OR m.depth_reliable)
      AND (well_list.max_fault_km IS NULL
           OR m.nearest_fault_km <= least(well_list.max_fault_km, 20))
    ORDER BY CASE WHEN well_list.order_by = 'depth' THEN -m.depth_ft END,
             CASE WHEN well_list.order_by = 'fault'
                  THEN m.nearest_fault_km END,
             w.well_name
    LIMIT least(greatest(well_list.n, 1),
                CASE WHEN well_list.order_by = 'depth' THEN 20 ELSE 50 END)
$$;

-- Surface and 3-D distance between two wells. The open pay interval is
-- assumed 500 ft above the measured depth, vertically below the wellhead
-- (owner 2026-10-20; there are no deviation surveys).
CREATE OR REPLACE FUNCTION geo.well_distance(well_a text, well_b text)
    RETURNS TABLE (well_a_name text, field_a text, well_b_name text,
                   field_b text, surface_km numeric,
                   depth_a_ft double precision, depth_a_m numeric,
                   depth_b_ft double precision, depth_b_m numeric,
                   pay_a_ft double precision, pay_b_ft double precision,
                   distance_3d_m numeric, distance_3d_ft numeric,
                   note text, source text)
    LANGUAGE sql STABLE
    SET search_path = core, geo, public
AS $$
    WITH pair AS MATERIALIZED (
        SELECT 1 AS side, geo.best_well(well_distance.well_a) AS well_id
        UNION ALL
        SELECT 2, geo.best_well(well_distance.well_b)
    ),
    p AS MATERIALIZED (
        SELECT pair.side, w.well_name, f.name AS field, w.geom_ctm12 AS g,
               m.depth_ft, m.depth_m, m.depth_reliable
        FROM pair
        JOIN core.wells w USING (well_id)
        LEFT JOIN core.fields f ON f.field_id = w.field_id
        LEFT JOIN core.well_metrics m USING (well_id)
    ),
    d AS (
        SELECT a.well_name AS a_name, a.field AS a_field,
               a.depth_ft AS a_ft, a.depth_m AS a_m,
               b.well_name AS b_name, b.field AS b_field,
               b.depth_ft AS b_ft, b.depth_m AS b_m,
               coalesce(a.depth_reliable AND b.depth_reliable, false) AS ok,
               ST_Distance(a.g, b.g) AS surface_m,
               ((a.depth_ft - 500) - (b.depth_ft - 500)) * 0.3048 AS dz_m
        FROM p a JOIN p b ON a.side = 1 AND b.side = 2
    )
    SELECT a_name, a_field, b_name, b_field,
           round((surface_m / 1000)::numeric, 3),
           a_ft, a_m, b_ft, b_m,
           CASE WHEN ok THEN a_ft - 500 END,
           CASE WHEN ok THEN b_ft - 500 END,
           CASE WHEN ok
                THEN round(sqrt(surface_m ^ 2 + dz_m ^ 2)::numeric, 1) END,
           CASE WHEN ok
                THEN round((sqrt(surface_m ^ 2 + dz_m ^ 2) / 0.3048)
                           ::numeric, 1) END,
           CASE WHEN ok
                THEN 'distancia 3-D entre los intervalos productores '
                     'supuestos (profundidad medida - 500 ft, en la '
                     'vertical del cabezal)'
                ELSE 'solo distancia en superficie: falta la profundidad '
                     'o no es confiable en al menos un pozo' END,
           geo.source()
    FROM d
$$;
