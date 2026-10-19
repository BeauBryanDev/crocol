DROP FUNCTION IF EXISTS kg.resolve(text, text[], integer);
CREATE OR REPLACE FUNCTION kg.resolve(query text, kinds text[] DEFAULT NULL,
                                      max_rows integer DEFAULT 5)
    RETURNS TABLE (entity_id bigint, kind text, name text, score real,
                   mentions bigint, props jsonb)
    LANGUAGE sql STABLE
    SET search_path = kg, core, public
AS $$
    WITH q AS (SELECT core.name_key(query) AS k),
    hits AS (
        SELECT a.entity_id, 1.0::real AS score
        FROM kg.aliases a, q WHERE a.alias_key = q.k
        UNION ALL
        SELECT a.entity_id, similarity(a.alias_key, q.k)
        FROM kg.aliases a, q
        WHERE length(q.k) >= 3 AND a.alias_key % q.k
          AND similarity(a.alias_key, q.k) >= 0.5
    ), best AS (
        SELECT h.entity_id, max(h.score) AS score FROM hits h GROUP BY 1
    )
    SELECT e.entity_id, e.kind, e.name, b.score,
           (SELECT count(*) FROM kg.mentions m WHERE m.entity_id = e.entity_id),
           e.props
    FROM best b JOIN kg.entities e USING (entity_id)
    WHERE kinds IS NULL OR e.kind = ANY(kinds)
    ORDER BY b.score DESC, 5 DESC, e.entity_id
    LIMIT least(greatest(max_rows, 1), 20)
$$;

CREATE OR REPLACE FUNCTION kg.facts(entity bigint, max_rows integer DEFAULT 40)
    RETURNS TABLE (direction text, rel text, other_kind text, total bigint,
                   names text[], other_ids bigint[])
    LANGUAGE sql STABLE
    SET search_path = kg, public
AS $$
    WITH links AS (
        SELECT 'out' AS direction, e.rel, o.kind, o.name, o.entity_id, e.weight
        FROM kg.edges e JOIN kg.entities o ON o.entity_id = e.dst
        WHERE e.src = entity
        UNION ALL
        SELECT 'in', e.rel, o.kind, o.name, o.entity_id, e.weight
        FROM kg.edges e JOIN kg.entities o ON o.entity_id = e.src
        WHERE e.dst = entity
    ), ranked AS (
        SELECT l.*, row_number() OVER (PARTITION BY direction, rel, kind
                                       ORDER BY weight DESC, name) AS n,
               count(*) OVER (PARTITION BY direction, rel, kind) AS total
        FROM links l
    )
    SELECT direction, rel, kind, max(total),
           array_agg(name ORDER BY n), array_agg(entity_id ORDER BY n)
    FROM ranked WHERE n <= 8
    GROUP BY direction, rel, kind
    ORDER BY CASE rel WHEN 'CO_MENTIONED' THEN 1 ELSE 0 END,
             max(total) DESC, rel
    LIMIT least(greatest(max_rows, 1), 60)
$$;

CREATE OR REPLACE FUNCTION kg.entity_documents(entity bigint,
                                               max_rows integer DEFAULT 10)
    RETURNS TABLE (doc_id text, citation text, title text, collection text,
                   scope text, chunks bigint, described boolean)
    LANGUAGE sql STABLE
    SET search_path = kg, rag, public
AS $$
    WITH mentioned AS (
        SELECT c.doc_id, count(*) AS chunks
        FROM kg.mentions m JOIN rag.chunks c USING (chunk_id)
        WHERE m.entity_id = entity AND m.confidence >= 0.7
        GROUP BY c.doc_id
    ), described AS (
        SELECT d.key AS doc_id
        FROM kg.edges e JOIN kg.entities d ON d.entity_id = e.src
        WHERE e.dst = entity AND e.rel = 'DESCRIBES'
    )
    SELECT r.doc_id, r.citation, r.title, r.collection, r.scope,
           coalesce(m.chunks, 0), d.doc_id IS NOT NULL
    FROM rag.documents r
    LEFT JOIN mentioned m USING (doc_id)
    LEFT JOIN described d USING (doc_id)
    WHERE m.doc_id IS NOT NULL OR d.doc_id IS NOT NULL
    ORDER BY (d.doc_id IS NOT NULL) DESC, coalesce(m.chunks, 0) DESC, r.citation
    LIMIT least(greatest(max_rows, 1), 50)
$$;

CREATE OR REPLACE FUNCTION kg.neighbors(ids bigint[], depth integer DEFAULT 1,
                                        rels text[] DEFAULT NULL,
                                        max_rows integer DEFAULT 200)
    RETURNS TABLE (entity_id bigint, kind text, name text, hops integer,
                   via text[])
    LANGUAGE sql STABLE
    SET search_path = kg, public
AS $$
    WITH RECURSIVE walk (entity_id, hops, via) AS (
        SELECT unnest(ids), 0, ARRAY[]::text[]
        UNION ALL
        SELECT CASE WHEN e.src = w.entity_id THEN e.dst ELSE e.src END,
               w.hops + 1, w.via || e.rel
        FROM walk w
        JOIN kg.edges e ON e.src = w.entity_id OR e.dst = w.entity_id
        WHERE w.hops < least(greatest(depth, 1), 2)
          AND (rels IS NULL OR e.rel = ANY(rels))
    ) CYCLE entity_id SET is_cycle USING visited
    SELECT * FROM (
        SELECT DISTINCT ON (n.entity_id) n.entity_id, n.kind, n.name,
               w.hops, w.via
        FROM walk w JOIN kg.entities n USING (entity_id)
        WHERE NOT w.is_cycle AND w.hops > 0 AND NOT n.entity_id = ANY(ids)
        ORDER BY n.entity_id, w.hops
    ) s
    ORDER BY s.hops, s.kind, s.name
    LIMIT least(greatest(max_rows, 1), 500)
$$;

CREATE OR REPLACE FUNCTION kg.evidence_chunks(ids bigint[],
                                              max_rows integer DEFAULT 30,
                                              collections text[] DEFAULT NULL,
                                              peripheral boolean DEFAULT false)
    RETURNS TABLE (chunk_id text, entities_hit bigint, score real)
    LANGUAGE sql STABLE
    SET search_path = kg, rag, public
AS $$
    SELECT m.chunk_id, count(DISTINCT m.entity_id),
           sum(m.confidence * least(m.hits, 5))::real
    FROM kg.mentions m
    JOIN rag.chunks c USING (chunk_id)
    JOIN rag.documents d USING (doc_id)
    WHERE m.entity_id = ANY(ids)
      AND m.confidence >= 0.7
      AND (collections IS NULL OR d.collection = ANY(collections))
      AND (peripheral OR d.scope = 'core')
      AND c.chunk_type <> 'table_row'
    GROUP BY m.chunk_id
    ORDER BY 2 DESC, 3 DESC, m.chunk_id
    LIMIT least(greatest(max_rows, 1), 50)
$$;

CREATE OR REPLACE FUNCTION kg.path(a bigint, b bigint, max_depth integer DEFAULT 3)
    RETURNS TABLE (step integer, entity_id bigint, kind text, name text,
                   rel text)
    LANGUAGE sql STABLE
    SET search_path = kg, public
AS $$
    WITH RECURSIVE walk (entity_id, hops, nodes, rels) AS (
        SELECT a, 0, ARRAY[a], ARRAY[]::text[]
        UNION ALL
        SELECT nxt.entity_id, w.hops + 1, w.nodes || nxt.entity_id,
               w.rels || nxt.rel
        FROM walk w
        CROSS JOIN LATERAL (
            SELECT CASE WHEN e.src = w.entity_id THEN e.dst ELSE e.src END
                   AS entity_id, e.rel
            FROM kg.edges e
            WHERE (e.src = w.entity_id OR e.dst = w.entity_id)
              AND e.rel <> 'CO_MENTIONED'
            LIMIT 400
        ) nxt
        WHERE w.hops < least(greatest(max_depth, 1), 3)
          AND w.entity_id <> b
          AND NOT nxt.entity_id = ANY(w.nodes)
    ), found AS (
        SELECT nodes, rels FROM walk WHERE entity_id = b
        ORDER BY hops LIMIT 1
    )
    SELECT s.step::integer, s.entity_id, e.kind, e.name,
           CASE WHEN s.step > 1 THEN f.rels[s.step - 1] END
    FROM found f
    CROSS JOIN LATERAL unnest(f.nodes) WITH ORDINALITY AS s(entity_id, step)
    JOIN kg.entities e ON e.entity_id = s.entity_id
    ORDER BY s.step
$$;
