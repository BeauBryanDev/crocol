CREATE SCHEMA IF NOT EXISTS kg;

CREATE TABLE kg.entities (
    entity_id bigserial PRIMARY KEY,
    kind      text NOT NULL CHECK (kind IN (
                  'formation', 'member', 'group', 'field', 'well',
                  'organization', 'municipality', 'seismic_3d', 'fault',
                  'contract', 'contract_area', 'regulation', 'document',
                  'person', 'institution', 'topic', 'basin')),
    key       text NOT NULL,
    name      text NOT NULL,
    ref_table text,
    ref_id    text,
    props     jsonb NOT NULL DEFAULT '{}',
    UNIQUE (kind, key)
);
CREATE INDEX entities_ref_idx ON kg.entities (ref_table, ref_id);

CREATE TABLE kg.aliases (
    alias_key text   NOT NULL,
    alias     text   NOT NULL,
    entity_id bigint NOT NULL REFERENCES kg.entities ON DELETE CASCADE,
    PRIMARY KEY (alias_key, entity_id)
);
CREATE INDEX aliases_entity_idx ON kg.aliases (entity_id);
CREATE INDEX aliases_trgm_idx ON kg.aliases USING gin (alias_key gin_trgm_ops);

CREATE TABLE kg.edges (
    src      bigint NOT NULL REFERENCES kg.entities ON DELETE CASCADE,
    rel      text   NOT NULL,
    dst      bigint NOT NULL REFERENCES kg.entities ON DELETE CASCADE,
    weight   real   NOT NULL DEFAULT 1.0,
    source   text   NOT NULL CHECK (source IN
                 ('attribute', 'metadata', 'curated', 'derived')),
    evidence jsonb  NOT NULL DEFAULT '{}',
    PRIMARY KEY (src, rel, dst),
    CHECK (src <> dst)
);
CREATE INDEX edges_dst_idx ON kg.edges (dst, rel);

CREATE TABLE kg.mentions (
    chunk_id   text     NOT NULL REFERENCES rag.chunks ON DELETE CASCADE,
    entity_id  bigint   NOT NULL REFERENCES kg.entities ON DELETE CASCADE,
    hits       smallint NOT NULL CHECK (hits > 0),
    confidence real     NOT NULL CHECK (confidence > 0 AND confidence <= 1),
    rule       text     NOT NULL,
    PRIMARY KEY (chunk_id, entity_id)
);
CREATE INDEX mentions_entity_idx ON kg.mentions (entity_id, confidence);

ALTER TABLE ops.sync_state DROP CONSTRAINT sync_state_target_check;
ALTER TABLE ops.sync_state ADD CONSTRAINT sync_state_target_check
    CHECK (target IN ('rag', 'chroma', 'kg') OR target LIKE 'spatial\_%');

REVOKE ALL ON SCHEMA kg FROM PUBLIC;
