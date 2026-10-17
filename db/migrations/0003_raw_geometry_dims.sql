ALTER TABLE raw.wells ALTER COLUMN geom TYPE geometry USING geom;
ALTER TABLE raw.seismic_2d ALTER COLUMN geom TYPE geometry USING geom;
ALTER TABLE raw.seismic_3d ALTER COLUMN geom TYPE geometry USING geom;
ALTER TABLE raw.faults ALTER COLUMN geom TYPE geometry USING geom;

ALTER TABLE raw.wells
    ADD CONSTRAINT wells_geom_srid CHECK (ST_SRID(geom) = 4326);
ALTER TABLE raw.seismic_2d
    ADD CONSTRAINT seismic_2d_geom_srid CHECK (ST_SRID(geom) = 4326);
ALTER TABLE raw.seismic_3d
    ADD CONSTRAINT seismic_3d_geom_srid CHECK (ST_SRID(geom) = 4326);
ALTER TABLE raw.faults
    ADD CONSTRAINT faults_geom_srid CHECK (ST_SRID(geom) = 4326);
