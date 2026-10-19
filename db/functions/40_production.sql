CREATE OR REPLACE FUNCTION prod.source() RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    RETURN 'ANH-Produccion-Fiscalizada-2026';

DROP FUNCTION IF EXISTS prod.resolve_field(text, integer);
DROP FUNCTION IF EXISTS prod.field_series(text);
DROP FUNCTION IF EXISTS prod.field_profile(text);

-- A name can be a field (LA CIRA) or a contract that groups fields
-- (LA CIRA INFANTAS = LA CIRA + INFANTAS): both resolve to field keys.
CREATE OR REPLACE FUNCTION prod.resolve_field(query text, max_rows integer DEFAULT 5)
    RETURNS TABLE (kind text, name text, field_keys text[], score real,
                   has_oil boolean, has_gas boolean)
    LANGUAGE sql STABLE
    SET search_path = core, prod, public
AS $$
    WITH q AS (SELECT core.name_key(query) AS k),
    rows AS (
        SELECT field, field_key, core.name_key(contract) AS contract_key,
               contract, true AS oil, false AS gas
        FROM core.oil_production
        GROUP BY field, field_key, contract
        UNION ALL
        SELECT field, field_key, core.name_key(contract), contract, false, true
        FROM core.gas_production
        GROUP BY field, field_key, contract
    ), fields AS (
        SELECT 'field'::text AS kind, min(field) AS name,
               ARRAY[field_key] AS keys, field_key AS k,
               bool_or(oil) AS oil, bool_or(gas) AS gas
        FROM rows GROUP BY field_key
    ), contracts AS (
        SELECT 'contract'::text, min(contract), array_agg(DISTINCT field_key),
               contract_key, bool_or(oil), bool_or(gas)
        FROM rows GROUP BY contract_key
        HAVING count(DISTINCT field_key) > 1
    ), candidates AS (
        SELECT f.*, CASE
                   WHEN f.k = q.k THEN 1.0
                   WHEN f.k LIKE q.k || '%' THEN 0.9
                   WHEN length(f.k) >= 5 AND q.k LIKE f.k || '%' THEN 0.8
                   ELSE similarity(f.k, q.k)
               END::real AS score
        FROM fields f, q
        UNION ALL
        SELECT c.*, CASE WHEN c.contract_key = q.k THEN 0.95
                         ELSE similarity(c.contract_key, q.k) * 0.9 END::real
        FROM contracts c, q
    )
    SELECT kind, name, keys, score, oil, gas
    FROM candidates, q
    WHERE length(q.k) >= 3 AND score >= 0.45
    ORDER BY score DESC, kind DESC, length(name), name
    LIMIT least(greatest(max_rows, 1), 20)
$$;

CREATE OR REPLACE FUNCTION prod.field_series(keys text[])
    RETURNS TABLE (month_end date, oil_bpdc double precision,
                   gas_mpcpdc double precision)
    LANGUAGE sql STABLE
    SET search_path = core, prod, public
AS $$
    WITH oil AS (
        SELECT month_end, sum(value) AS v FROM core.oil_production
        WHERE field_key = ANY(keys) GROUP BY month_end
    ), gas AS (
        SELECT month_end, sum(value) AS v FROM core.gas_production
        WHERE field_key = ANY(keys) GROUP BY month_end
    )
    SELECT coalesce(o.month_end, g.month_end), o.v, g.v
    FROM oil o FULL JOIN gas g USING (month_end)
    ORDER BY 1
$$;

CREATE OR REPLACE FUNCTION prod.field_profile(keys text[])
    RETURNS TABLE (fields text[], departments text[], municipalities text[],
                   operators text[], contracts text[])
    LANGUAGE sql STABLE
    SET search_path = core, prod, public
AS $$
    WITH rows AS (
        SELECT field, department, municipality, operator, contract
        FROM core.oil_production WHERE field_key = ANY(keys)
        UNION
        SELECT field, department, municipality, operator, contract
        FROM core.gas_production WHERE field_key = ANY(keys)
    )
    SELECT array_agg(DISTINCT field ORDER BY field),
           array_agg(DISTINCT department ORDER BY department),
           array_agg(DISTINCT municipality ORDER BY municipality),
           array_agg(DISTINCT operator ORDER BY operator),
           array_agg(DISTINCT contract ORDER BY contract)
    FROM rows
    HAVING count(*) > 0
$$;
