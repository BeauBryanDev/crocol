"""Phase 0 A/B test: which dense embedding model retrieves best on the VMM corpus?

Candidates (all at 1536 dimensions, cosine):
  openai:text-embedding-3-large   google:gemini-embedding-001   google:gemini-embedding-2

Method:
  - pool of crude chunks from markdown/ (stratified by collection)
  - gold chunks; Claude writes one natural question per gold chunk (no copied phrases;
    about a quarter asked in English about Spanish text)
  - retrieval is computed locally: cosine for dense, BM25 over lexical.normalize_lexical
    with Chroma's tokenizer, and RRF(k=60) for the dense + BM25 setup chosen in Phase 0
  - metrics: hit@1, hit@5, hit@10, MRR@10, overall and same-language vs cross-language

Embeddings and questions are cached in spikes/cache/ so re-runs cost nothing.

Usage:
    magdalena/bin/python spikes/ab_embeddings.py [--pool 600] [--questions 40]
"""

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from anthropic import Anthropic
from chromadb.utils.embedding_functions.schemas.bm25_tokenizer import (Bm25Tokenizer,
                                                                       get_english_stemmer)
from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "spikes"))
from chroma_spike import crude_chunks  # noqa: E402
from crocol.domains.services.lexical import STOPWORDS, normalize_lexical  # noqa: E402

DIMS = 1536
SEED = 11
QUESTION_MODEL = "claude-sonnet-5-5"
CACHE = ROOT / "spikes" / "cache"
MODELS = ["openai:text-embedding-3-large", "google:gemini-embedding-001", "google:gemini-embedding-2"]
GOLD_SHARE = {"VMM_Basin": 0.55, "ANH_Contracts": 0.2, "ANH_Regulatory": 0.2, "ANH_Reserves": 0.05}
RRF_K = 60
GEMINI_MAX_CHARS = 6000
BM25_WEIGHTS = (1.0, 0.5, 0.3)
BM25_K1, BM25_B = 1.2, 0.75

QUESTION_PROMPT = """You write evaluation questions for a retrieval system about the Middle Magdalena Valley \
(VMM) basin in Colombia: geology, petroleum contracts and regulation.

Read the passage and write ONE question that a geologist, engineer or analyst would naturally ask and \
that this passage answers specifically.

Rules:
- Write the question in {language}.
- Paraphrase: do not copy any run of more than three consecutive words from the passage.
- Do not mention the document title, file name, page, table number or "this passage".
- Make it specific enough that this passage, not just any VMM text, is the best answer.

Document title: {title}
Passage:
\"\"\"
{text}
\"\"\"

Reply with JSON only: {{"question": "..."}}"""


def stratified_pool(chunks, size, rng):
    by_collection = {}
    for chunk in chunks:
        by_collection.setdefault(chunk.get("collection", "?"), []).append(chunk)
    for items in by_collection.values():
        rng.shuffle(items)
    pool = []
    while len(pool) < size and any(by_collection.values()):
        for items in by_collection.values():
            if items and len(pool) < size:
                pool.append(items.pop())
    return pool


def pick_gold(pool, count, rng):
    candidates = [c for c in pool if len(c["text"]) >= 700 and c["chunk_type"] in ("text", "table")]
    gold = []
    for collection, share in GOLD_SHARE.items():
        items = [c for c in candidates if c.get("collection") == collection]
        rng.shuffle(items)
        gold.extend(items[:max(1, round(count * share))])
    return gold[:count]


def doc_language(text):
    words = Counter(w for w in text.lower().split())
    es = sum(words[w] for w in ("de", "la", "el", "los", "las", "que", "del", "en", "por"))
    en = sum(words[w] for w in ("the", "of", "and", "is", "in", "to", "for", "with"))
    return "es" if es >= en else "en"


def generate_questions(gold, rng):
    path = CACHE / "ab_questions.json"
    cached = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    plan = []
    for chunk in gold:
        lang = doc_language(chunk["text"])
        cross = lang == "es" and rng.random() < 0.3
        plan.append((chunk, "English" if (lang == "en" or cross) else "Spanish", cross))

    def ask(item):
        chunk, language, cross = item
        key = f"{chunk['id']}|{language}"
        if key in cached:
            return key, cached[key]
        prompt = QUESTION_PROMPT.format(language=language, title=chunk.get("title", ""),
                                        text=chunk["text"][:6000])
        for attempt in range(5):
            try:
                reply = client.messages.create(model=QUESTION_MODEL, max_tokens=300,
                                               messages=[{"role": "user", "content": prompt}])
                text = reply.content[0].text.strip()
                question = json.loads(text[text.find("{"):text.rfind("}") + 1])["question"]
                return key, {"question": question, "chunk_id": chunk["id"], "language": language,
                             "cross_lingual": cross}
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, value in pool.map(ask, plan):
            cached[key] = value
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
    keys = {f"{chunk['id']}|{language}" for chunk, language, _ in plan}
    return [v for k, v in cached.items() if k in keys]


def cache_path(model, kind, texts):
    digest = hashlib.sha1("\n\x00".join(texts).encode("utf-8")).hexdigest()[:12]
    return CACHE / f"{model.replace(':', '_')}_{kind}_{digest}.npy"


def embed(model, texts, kind):
    path = cache_path(model, kind, texts)
    if path.exists():
        return np.load(path)
    provider, name = model.split(":", 1)
    vectors = []
    if provider == "openai":
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        for start in range(0, len(texts), 64):
            batch = [t[:24000] for t in texts[start:start + 64]]
            vectors.extend(retry(lambda: [d.embedding for d in client.embeddings.create(
                model=name, input=batch, dimensions=DIMS).data]))
    else:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        task = "RETRIEVAL_DOCUMENT" if kind == "docs" else "RETRIEVAL_QUERY"
        config = types.EmbedContentConfig(task_type=task, output_dimensionality=DIMS)
        step = 1 if name == "gemini-embedding-2" else 50
        for start in range(0, len(texts), step):
            batch = [t[:GEMINI_MAX_CHARS] for t in texts[start:start + step]]
            vectors.extend(retry(lambda: [e.values for e in client.models.embed_content(
                model=name, contents=batch, config=config).embeddings]))
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(path, matrix)
    return matrix


def retry(fn, attempts=6):
    for attempt in range(attempts):
        try:
            return fn()
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(min(30, 2 ** attempt))


class Bm25:
    def __init__(self, texts):
        tokenizer = Bm25Tokenizer(get_english_stemmer(), STOPWORDS, 40)
        self.tokenize = lambda text: tokenizer.tokenize(normalize_lexical(text))
        self.docs = [Counter(self.tokenize(t)) for t in texts]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / len(self.lengths)
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query):
        terms = self.tokenize(query)
        out = np.zeros(len(self.docs), dtype=np.float32)
        for i, (doc, length) in enumerate(zip(self.docs, self.lengths)):
            s = 0.0
            for term in terms:
                tf = doc.get(term, 0)
                if tf:
                    s += self.idf[term] * tf * (BM25_K1 + 1) / (
                        tf + BM25_K1 * (1 - BM25_B + BM25_B * length / self.avg))
            out[i] = s
        return out


def rrf(rankings, weights=None, top=100):
    fused = {}
    for ranking, weight in zip(rankings, weights or [1.0] * len(rankings)):
        for position, index in enumerate(ranking[:top]):
            fused[index] = fused.get(index, 0.0) + weight / (RRF_K + position + 1)
    return [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])]


def metrics(ranks):
    n = len(ranks)
    return {
        "hit@1": round(sum(r == 1 for r in ranks) / n, 3),
        "hit@5": round(sum(0 < r <= 5 for r in ranks) / n, 3),
        "hit@10": round(sum(0 < r <= 10 for r in ranks) / n, 3),
        "mrr@10": round(sum(1 / r for r in ranks if 0 < r <= 10) / n, 3),
        "n": n,
    }


def rank_of(ranking, target):
    for position, index in enumerate(ranking[:10]):
        if index == target:
            return position + 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pool", type=int, default=600)
    parser.add_argument("--questions", type=int, default=40)
    parser.add_argument("--report", type=Path, default=ROOT / "spikes" / "ab_embeddings_report.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    rng = random.Random(SEED)

    chunks = []
    for md in sorted((ROOT / "markdown").glob("*.md")):
        chunks.extend(crude_chunks(md))
    pool = stratified_pool(chunks, args.pool, rng)
    for index, chunk in enumerate(pool):
        chunk["id"] = f"ab-{index:04d}"
    gold = pick_gold(pool, args.questions, rng)
    print(f"pool {len(pool)} chunks, {Counter(c.get('collection') for c in pool)}")
    print(f"gold {len(gold)} chunks, {Counter(c.get('collection') for c in gold)}")

    questions = generate_questions(gold, rng)
    cross = sum(q["cross_lingual"] for q in questions)
    print(f"questions {len(questions)} ({cross} cross-lingual), e.g.:")
    for q in questions[:4]:
        print(f"  - [{q['language'][:2]}] {q['question']}")

    index_of = {c["id"]: i for i, c in enumerate(pool)}
    targets = [index_of[q["chunk_id"]] for q in questions]
    q_texts = [q["question"] for q in questions]
    doc_texts = [c["text"] for c in pool]
    bm25 = Bm25(doc_texts)
    bm25_rankings = [list(np.argsort(-bm25.scores(q))) for q in q_texts]

    report = {"pool": len(pool), "questions": len(questions), "cross_lingual": cross, "results": {}}
    report["results"]["bm25_only"] = metrics([rank_of(r, t) for r, t in zip(bm25_rankings, targets)])
    for model in MODELS:
        start = time.perf_counter()
        try:
            docs = embed(model, doc_texts, "docs")
            queries = embed(model, q_texts, "queries")
        except Exception as exc:
            print(f"{model}: ERROR {type(exc).__name__}: {str(exc)[:200]}")
            report["results"][model] = {"error": str(exc)[:300]}
            continue
        seconds = time.perf_counter() - start
        dense_rankings = [list(np.argsort(-(docs @ q))) for q in queries]
        entry = {"embed_seconds": round(seconds, 1)}
        variants = [("dense", dense_rankings)]
        for weight in BM25_WEIGHTS:
            variants.append((f"dense+bm25@{weight}",
                             [rrf([d, b], [1.0, weight]) for d, b in zip(dense_rankings, bm25_rankings)]))
        for label, rankings in variants:
            ranks = [rank_of(r, t) for r, t in zip(rankings, targets)]
            entry[label] = metrics(ranks)
            entry[f"{label}_same_lang"] = metrics([r for r, q in zip(ranks, questions) if not q["cross_lingual"]])
            if cross:
                entry[f"{label}_cross_lang"] = metrics([r for r, q in zip(ranks, questions) if q["cross_lingual"]])
        report["results"][model] = entry

    print("\nresults (hit@1 / hit@5 / hit@10 / MRR@10)")
    b = report["results"]["bm25_only"]
    print(f"  {'bm25 only':42} {b['hit@1']:.2f} / {b['hit@5']:.2f} / {b['hit@10']:.2f} / {b['mrr@10']:.2f}")
    for model in MODELS:
        entry = report["results"].get(model, {})
        if "error" in entry:
            continue
        labels = ["dense"] + [f"dense+bm25@{w}" for w in BM25_WEIGHTS]
        for label in labels + [f"{x}_cross_lang" for x in labels]:
            if label in entry:
                m = entry[label]
                print(f"  {model + ' ' + label:42} {m['hit@1']:.2f} / {m['hit@5']:.2f} / "
                      f"{m['hit@10']:.2f} / {m['mrr@10']:.2f}  (n={m['n']})")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()
