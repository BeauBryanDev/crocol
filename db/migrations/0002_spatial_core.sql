INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, proj4text)
SELECT 9377, 'EPSG', 9377,
       '+proj=tmerc +lat_0=4 +lon_0=-73 +k=0.9992 +x_0=5000000 '
       '+y_0=2000000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'
WHERE NOT EXISTS (SELECT 1 FROM spatial_ref_sys WHERE srid = 9377);

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS geo;

CREATE FUNCTION core.name_key(value text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
    RETURN regexp_replace(
        upper(public.unaccent('public.unaccent'::regdictionary, value)),
        '[^A-Z0-9]+', '', 'g');

CREATE TABLE raw.wells (
    fid       integer PRIMARY KEY,
    props     jsonb NOT NULL,
    geom      geometry(Geometry, 4326) NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE raw.seismic_2d (LIKE raw.wells INCLUDING ALL);
CREATE TABLE raw.seismic_3d (LIKE raw.wells INCLUDING ALL);
CREATE TABLE raw.faults     (LIKE raw.wells INCLUDING ALL);

CREATE TABLE core.basins (
    basin_id smallint PRIMARY KEY,
    name     text NOT NULL UNIQUE,
    code     text NOT NULL UNIQUE
);
INSERT INTO core.basins VALUES (1, 'VALLE MEDIO DEL MAGDALENA', 'VMM');

CREATE TABLE core.vmm_footprint (
    footprint_id smallint PRIMARY KEY DEFAULT 1 CHECK (footprint_id = 1),
    method       text NOT NULL,
    buffer_km    real NOT NULL,
    built_at     timestamptz NOT NULL DEFAULT now(),
    geom         geometry(MultiPolygon, 4326) NOT NULL,
    geom_ctm12   geometry(MultiPolygon, 9377)
                 GENERATED ALWAYS AS (ST_Transform(geom, 9377)) STORED
);

CREATE TABLE core.organizations (
    org_id         serial PRIMARY KEY,
    canonical_name text NOT NULL UNIQUE,
    name_key       text GENERATED ALWAYS AS (core.name_key(canonical_name))
                   STORED UNIQUE,
    roles          text[] NOT NULL DEFAULT '{}'
);
CREATE TABLE core.organization_aliases (
    alias_key text PRIMARY KEY,
    alias     text NOT NULL,
    org_id    integer NOT NULL REFERENCES core.organizations ON DELETE CASCADE
);

CREATE TABLE core.municipalities (
    municipality_id serial PRIMARY KEY,
    name            text NOT NULL,
    department      text NOT NULL,
    dane_code       integer UNIQUE,
    name_key        text GENERATED ALWAYS AS (core.name_key(name)) STORED,
    reviewed        boolean NOT NULL DEFAULT false,
    UNIQUE (name_key, department)
);
CREATE TABLE core.municipality_aliases (
    alias_key       text PRIMARY KEY,
    alias           text NOT NULL,
    municipality_id integer NOT NULL
                    REFERENCES core.municipalities ON DELETE CASCADE
);

CREATE TABLE core.fields (
    field_id serial PRIMARY KEY,
    name     text NOT NULL UNIQUE,
    name_key text GENERATED ALWAYS AS (core.name_key(name)) STORED UNIQUE
);

CREATE TABLE core.wells (
    well_id          integer PRIMARY KEY,
    uwi              text NOT NULL,
    uwi_duplicate    boolean NOT NULL DEFAULT false,
    well_name        text NOT NULL,
    name_key         text GENERATED ALWAYS AS (core.name_key(well_name))
                     STORED,
    department       text,
    municipality_raw text,
    municipality_id  integer REFERENCES core.municipalities,
    field_id         integer REFERENCES core.fields,
    contract_name    text,
    lahee_class      text,
    status           text,
    trajectory       text,
    purpose          text,
    operator_id      integer REFERENCES core.organizations,
    company_id       integer REFERENCES core.organizations,
    z_value_raw      double precision,
    geom             geometry(Point, 4326) NOT NULL,
    geom_ctm12       geometry(Point, 9377)
                     GENERATED ALWAYS AS (ST_Transform(geom, 9377)) STORED
);

CREATE TABLE core.seismic_lines (
    line_id            integer PRIMARY KEY,
    survey_name        text NOT NULL,
    survey_key         text GENERATED ALWAYS AS (core.name_key(survey_name))
                       STORED,
    line_name          text NOT NULL,
    segment            text,
    contractor_id      integer REFERENCES core.organizations,
    operator_id        integer REFERENCES core.organizations,
    spread_type        text,
    acq_date           date,
    acq_year           smallint,
    acq_date_precision text CHECK (acq_date_precision IN ('day', 'year', 'name')),
    original_datum     text,
    sp_first           text,
    sp_last            text,
    contract_name      text,
    length_km          double precision NOT NULL,
    geom               geometry(MultiLineString, 4326) NOT NULL,
    geom_ctm12         geometry(MultiLineString, 9377)
                       GENERATED ALWAYS AS (ST_Transform(geom, 9377)) STORED,
    geom_display       geometry(MultiLineString, 4326)
);

CREATE TABLE core.seismic_3d (
    survey_id       integer PRIMARY KEY,
    name            text NOT NULL,
    name_key        text GENERATED ALWAYS AS (core.name_key(name)) STORED,
    contract_name   text,
    operator_id     integer REFERENCES core.organizations,
    contractor_id   integer REFERENCES core.organizations,
    acq_date        date,
    acq_year        smallint,
    acq_year_source text CHECK (acq_year_source IN ('date', 'name')),
    area_km2        double precision NOT NULL,
    geom            geometry(MultiPolygon, 4326) NOT NULL,
    geom_ctm12      geometry(MultiPolygon, 9377)
                    GENERATED ALWAYS AS (ST_Transform(geom, 9377)) STORED
);

CREATE TABLE core.faults (
    fault_id   integer PRIMARY KEY,
    name       text,
    name_key   text GENERATED ALWAYS AS (core.name_key(name)) STORED,
    fault_type text,
    length_km  double precision NOT NULL,
    geom       geometry(MultiLineString, 4326) NOT NULL,
    geom_ctm12 geometry(MultiLineString, 9377)
               GENERATED ALWAYS AS (ST_Transform(geom, 9377)) STORED
);

CREATE INDEX wells_geom_idx ON core.wells USING gist (geom);
CREATE INDEX wells_ctm12_idx ON core.wells USING gist (geom_ctm12);
CREATE INDEX wells_key_idx ON core.wells (name_key);
CREATE INDEX wells_key_trgm_idx ON core.wells USING gin (name_key gin_trgm_ops);
CREATE INDEX wells_field_idx ON core.wells (field_id, status);
CREATE INDEX wells_municipality_idx ON core.wells (municipality_id, status);
CREATE INDEX lines_geom_idx ON core.seismic_lines USING gist (geom);
CREATE INDEX lines_ctm12_idx ON core.seismic_lines USING gist (geom_ctm12);
CREATE INDEX lines_survey_idx ON core.seismic_lines (survey_key, acq_year);
CREATE INDEX s3d_ctm12_idx ON core.seismic_3d USING gist (geom_ctm12);
CREATE INDEX faults_ctm12_idx ON core.faults USING gist (geom_ctm12);
CREATE INDEX faults_key_idx ON core.faults (name_key);
CREATE INDEX fields_key_trgm_idx ON core.fields USING gin (name_key gin_trgm_ops);
CREATE INDEX munis_key_trgm_idx ON core.municipalities
    USING gin (name_key gin_trgm_ops);

ALTER TABLE ops.sync_state DROP CONSTRAINT sync_state_target_check;
ALTER TABLE ops.sync_state ADD CONSTRAINT sync_state_target_check
    CHECK (target IN ('rag', 'chroma') OR target LIKE 'spatial\_%');

REVOKE ALL ON SCHEMA raw, core, geo FROM PUBLIC;
