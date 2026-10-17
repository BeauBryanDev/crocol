CREATE OR REPLACE FUNCTION core.clean_text(value text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    RETURN NULLIF(NULLIF(NULLIF(NULLIF(NULLIF(
        btrim(regexp_replace(replace(value, chr(160), ' '), '\s+', ' ', 'g')),
        ''), 'PENDIENTE'), 'NO DEFINIDO'), 'NO DEFINIDA'), '0');

CREATE OR REPLACE FUNCTION core.safe_date(value text, pattern text)
    RETURNS date
    LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE
AS $$
BEGIN
    RETURN to_date(value, pattern);
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION core.year_from_name(value text) RETURNS integer
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    RETURN CASE
        WHEN value ~ '(19|20)\d{2}'
            THEN substring(value FROM '((?:19|20)\d{2})')::integer
        WHEN value ~ '-\d{2}\M'
            THEN substring(value FROM '-(\d{2})\M')::integer
                 + CASE WHEN substring(value FROM '-(\d{2})\M')::integer >= 30
                        THEN 1900 ELSE 2000 END
    END;

CREATE OR REPLACE FUNCTION core.plausible_year(value integer) RETURNS integer
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    RETURN CASE WHEN value BETWEEN 1920 AND 2030 THEN value END;
