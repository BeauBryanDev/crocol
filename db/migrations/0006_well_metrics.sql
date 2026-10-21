-- Per-well values derived at load time by pipelines/load_spatial.py
-- (--step metrics; facts, faults and all rebuild it too).
-- depth_ft is ANH's Z attribute: measured depth from the wellhead, in feet,
-- not true vertical depth. Outside 100-25,000 ft it is marked unreliable.
-- nearest_fault_id has no foreign key so core.faults can be reloaded alone.
CREATE TABLE core.well_metrics (
    well_id            integer PRIMARY KEY
                       REFERENCES core.wells (well_id) ON DELETE CASCADE,
    depth_ft           double precision,
    depth_m            numeric(8, 1),
    depth_reliable     boolean,
    nearest_fault_id   integer,
    nearest_fault_name text,
    nearest_fault_type text,
    nearest_fault_km   numeric(8, 2),
    CHECK ((depth_ft IS NULL) = (depth_reliable IS NULL))
);

CREATE INDEX well_metrics_depth_idx ON core.well_metrics (depth_ft DESC)
    WHERE depth_reliable;
CREATE INDEX well_metrics_fault_idx ON core.well_metrics (nearest_fault_km);
