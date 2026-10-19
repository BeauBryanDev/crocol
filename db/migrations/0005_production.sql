CREATE SCHEMA IF NOT EXISTS prod;

-- ANH "Producción Fiscalizada" per field, contract, municipality and month,
-- in ANH's units: oil in BPDC (barrels per calendar day), gas in MPCPDC
-- (million cubic feet per calendar day); both are monthly averages.
-- ANH can list a field twice in a month (e.g. Pandereta gas): both rows are
-- real and the monthly totals include both, so rows are summed, not keyed.
CREATE TABLE core.oil_production (
    production_id  bigserial PRIMARY KEY,
    month_end      date        NOT NULL,
    field          text        NOT NULL,
    field_key      text        GENERATED ALWAYS AS (core.name_key(field)) STORED,
    contract       text        NOT NULL,
    municipality   text        NOT NULL,
    department     text        NOT NULL,
    operator       text        NOT NULL,
    value          double precision NOT NULL CHECK (value >= 0),
    unit           text        NOT NULL CHECK (unit = 'BPDC'),
    field_original text        NOT NULL,
    source_file    text        NOT NULL,
    CHECK (month_end = (date_trunc('month', month_end) + interval '1 month - 1 day')::date)
);

CREATE TABLE core.gas_production (LIKE core.oil_production INCLUDING ALL);
ALTER TABLE core.gas_production DROP CONSTRAINT IF EXISTS oil_production_unit_check;
ALTER TABLE core.gas_production DROP CONSTRAINT IF EXISTS gas_production_unit_check;
ALTER TABLE core.gas_production ADD CONSTRAINT gas_production_unit_check
    CHECK (unit = 'MPCPDC');

CREATE INDEX oil_production_field_idx ON core.oil_production (field_key, month_end);
CREATE INDEX gas_production_field_idx ON core.gas_production (field_key, month_end);
CREATE INDEX oil_production_key_trgm_idx ON core.oil_production
    USING gin (field_key gin_trgm_ops);
CREATE INDEX gas_production_key_trgm_idx ON core.gas_production
    USING gin (field_key gin_trgm_ops);

ALTER TABLE ops.sync_state DROP CONSTRAINT sync_state_target_check;
ALTER TABLE ops.sync_state ADD CONSTRAINT sync_state_target_check
    CHECK (target IN ('rag', 'chroma', 'kg')
           OR target LIKE 'spatial\_%' OR target LIKE 'production\_%');

REVOKE ALL ON SCHEMA prod FROM PUBLIC;
