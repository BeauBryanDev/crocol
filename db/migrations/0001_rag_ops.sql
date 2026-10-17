CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
DROP EXTENSION IF EXISTS postgis_tiger_geocoder CASCADE;
DROP SCHEMA IF EXISTS tiger_data CASCADE;
DROP SCHEMA IF EXISTS tiger CASCADE;

CREATE SCHEMA IF NOT EXISTS rag;
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE rag.documents (
    doc_id           text PRIMARY KEY CHECK (doc_id ~ '^[0-9a-f]{12}$'),
    source_path      text NOT NULL UNIQUE,
    collection       text NOT NULL CHECK (collection IN
                         ('VMM_Basin', 'ANH_Contracts', 'ANH_Regulatory', 'ANH_Reserves')),
    scope            text NOT NULL DEFAULT 'core' CHECK (scope IN ('core', 'peripheral', 'excluded')),
    doc_type         text NOT NULL,
    language         text NOT NULL,
    title            text NOT NULL,
    authors          text[] NOT NULL DEFAULT '{}',
    year             smallint CHECK (year BETWEEN 1800 AND 2100),
    institution      text,
    venue            text,
    doi              text,
    degree           text,
    topics           text[] NOT NULL DEFAULT '{}',
    formations       text[] NOT NULL DEFAULT '{}',
    extraction_flags text[] NOT NULL DEFAULT '{}',
    legal            jsonb NOT NULL DEFAULT '{}',
    citation         text NOT NULL,
    reference        text NOT NULL,
    markdown_path    text NOT NULL,
    sha256           text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    pages            integer,
    loaded_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX documents_collection_idx ON rag.documents (collection, scope, doc_type);
CREATE INDEX documents_formations_idx ON rag.documents USING gin (formations);
CREATE INDEX documents_topics_idx ON rag.documents USING gin (topics);
CREATE INDEX documents_authors_idx ON rag.documents USING gin (authors);

CREATE TABLE rag.chunks (
    chunk_id         text PRIMARY KEY CHECK (chunk_id ~ '^[0-9a-f]{16}$'),
    doc_id           text NOT NULL REFERENCES rag.documents ON DELETE CASCADE,
    seq              integer NOT NULL,
    chunk_type       text NOT NULL CHECK (chunk_type IN ('text', 'table', 'table_row')),
    heading_path     text NOT NULL DEFAULT '',
    page_start       integer NOT NULL,
    page_end         integer NOT NULL,
    table_id         text,
    article          text,
    clause           text,
    text             text NOT NULL,
    embed_text       text NOT NULL,
    lexical_text     text NOT NULL,
    tokens           integer NOT NULL,
    content_hash     text NOT NULL,
    pipeline_version text NOT NULL,
    indexed_at       timestamptz,
    tsv              tsvector GENERATED ALWAYS AS (to_tsvector('simple', lexical_text)) STORED,
    UNIQUE (doc_id, seq) DEFERRABLE INITIALLY DEFERRED,
    CHECK (page_end >= page_start)
);
CREATE INDEX chunks_type_idx ON rag.chunks (chunk_type);
CREATE INDEX chunks_table_idx ON rag.chunks (table_id) WHERE table_id IS NOT NULL;
CREATE INDEX chunks_tsv_idx ON rag.chunks USING gin (tsv);

CREATE TABLE rag.references_raw (
    doc_id text PRIMARY KEY REFERENCES rag.documents ON DELETE CASCADE,
    text   text NOT NULL
);

CREATE TABLE ops.query_log (
    trace_id         uuid PRIMARY KEY,
    created_at       timestamptz NOT NULL DEFAULT now(),
    language         text,
    mode             text NOT NULL CHECK (mode IN ('quick', 'research')),
    corpus_scope     text CHECK (corpus_scope IN ('core', 'all')),
    chunk_policy     text CHECK (chunk_policy IN ('prose_tables', 'numeric')),
    status           text NOT NULL CHECK (status IN ('answered', 'abstained', 'partial', 'error')),
    attempts         smallint NOT NULL DEFAULT 0,
    llm_calls        smallint NOT NULL DEFAULT 0,
    tokens_in        integer,
    tokens_out       integer,
    latency_ms       integer,
    cross_family     boolean,
    verification     jsonb,
    conflicts        jsonb NOT NULL DEFAULT '[]',
    trace            jsonb NOT NULL DEFAULT '[]',
    pipeline_version text NOT NULL,
    app_version      text
);
CREATE INDEX query_log_created_idx ON ops.query_log (created_at DESC);
CREATE INDEX query_log_status_idx ON ops.query_log (status, created_at DESC);

CREATE TABLE ops.query_chunks (
    trace_id uuid NOT NULL REFERENCES ops.query_log ON DELETE CASCADE,
    stage    text NOT NULL CHECK (stage IN ('retrieved', 'graded', 'cited')),
    chunk_id text NOT NULL,
    channel  text,
    rank     smallint,
    score    real,
    relevant boolean,
    PRIMARY KEY (trace_id, stage, chunk_id)
);
CREATE INDEX query_chunks_chunk_idx ON ops.query_chunks (chunk_id);

CREATE TABLE ops.sync_state (
    target           text PRIMARY KEY CHECK (target IN ('rag', 'chroma')),
    pipeline_version text NOT NULL,
    item_count       integer NOT NULL,
    checksum         text NOT NULL,
    synced_at        timestamptz NOT NULL DEFAULT now(),
    details          jsonb NOT NULL DEFAULT '{}'
);

REVOKE ALL ON SCHEMA rag, ops FROM PUBLIC;
