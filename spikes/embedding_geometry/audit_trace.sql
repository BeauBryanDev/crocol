-- Crocol trace audit.  In psql:
--   \set tid 'd82994ac-ffa9-454f-9929-23ce5ff1a02b'
--   \i spikes/embedding_geometry/audit_trace.sql   (psql started from the repo root)
\pset pager off
\x off

\echo '== 1. Run summary'
SELECT trace_id, created_at, mode, status, corpus_scope, chunk_policy,
       llm_calls, tokens_in, tokens_out, latency_ms, pipeline_version
FROM ops.query_log WHERE trace_id = :'tid';

\echo '== 2. Node timeline (what each step did)'
SELECT ord, e->>'node' AS node, e->>'status' AS status,
       (e->>'duration_ms')::int AS ms,
       left(((e->'summary') - 'chunk_ids')::text, 160) AS summary
FROM ops.query_log q,
     jsonb_array_elements(q.trace) WITH ORDINALITY AS t(e, ord)
WHERE q.trace_id = :'tid'
ORDER BY ord;

\echo '== 3. Final top-k (retrieved -> graded -> cited) with metadata'
\echo '   score = Cohere relevance 0..1 when rerank status=ok, else RRF fused score'
SELECT qc.stage, qc.rank, qc.chunk_id, round(qc.score::numeric, 4) AS score,
       c.chunk_type, d.collection, d.scope, d.doc_type, d.citation,
       c.page_start || '-' || c.page_end AS pages,
       left(c.heading_path, 60) AS heading, c.tokens
FROM ops.query_chunks qc
LEFT JOIN rag.chunks c USING (chunk_id)
LEFT JOIN rag.documents d USING (doc_id)
WHERE qc.trace_id = :'tid'
ORDER BY array_position(ARRAY['retrieved','graded','cited'], qc.stage), qc.rank;

\echo '== 4. Fused candidates BEFORE rerank (order = RRF order); kept = survived to top-k'
SELECT ord AS fused_rank, id AS chunk_id,
       EXISTS (SELECT 1 FROM ops.query_chunks k
               WHERE k.trace_id = :'tid' AND k.stage = 'retrieved'
                 AND k.chunk_id = id) AS kept,
       c.chunk_type, d.citation, left(c.heading_path, 60) AS heading
FROM ops.query_log q,
     jsonb_array_elements(q.trace) e,
     jsonb_array_elements_text(e->'summary'->'chunk_ids') WITH ORDINALITY AS f(id, ord)
LEFT JOIN rag.chunks c ON c.chunk_id = f.id
LEFT JOIN rag.documents d ON d.doc_id = c.doc_id
WHERE q.trace_id = :'tid' AND e->>'node' = 'fuse'
ORDER BY ord;

\echo '== 5. Documents contributing to the top-k'
SELECT d.citation, d.doc_type, d.scope, count(*) AS chunks,
       round(max(qc.score)::numeric, 4) AS best_score
FROM ops.query_chunks qc
JOIN rag.chunks c USING (chunk_id)
JOIN rag.documents d USING (doc_id)
WHERE qc.trace_id = :'tid' AND qc.stage = 'retrieved'
GROUP BY 1, 2, 3 ORDER BY best_score DESC NULLS LAST;
