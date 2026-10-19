import csv
import random
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

import ahocorasick
import psycopg

from crocol.domains.services.entity_linking import (
    LINKED_KINDS,
    STOP_FORMS,
    Candidate,
    Link,
    Match,
    area_code,
    cased,
    cued_kinds,
    decide,
    fold,
    is_cue_form,
    joined_in,
    longest_matches,
    next_to_marker,
    normalize,
    normalize_with_map,
    token_form,
)

ALIASES = """
SELECT a.alias, e.entity_id, e.kind, e.name,
       coalesce((e.props ->> 'strict')::boolean, false)
FROM kg.aliases a JOIN kg.entities e USING (entity_id)
WHERE e.kind = ANY(%s)
"""
CHUNKS = """
SELECT c.chunk_id, c.doc_id, c.text, d.citation, c.page_start
FROM rag.chunks c JOIN rag.documents d USING (doc_id)
ORDER BY c.doc_id, c.seq
"""
DOCUMENT_UNITS = """
SELECT d.key, e.dst
FROM kg.edges e JOIN kg.entities d ON d.entity_id = e.src
WHERE e.rel = 'DESCRIBES'
"""
MIN_FORM_CHARS = 3
REVIEW_PER_KIND = 100
SNIPPET_CHARS = 90


@dataclass(frozen=True)
class ChunkText:
    chunk_id: str
    doc_id: str
    text: str
    citation: str
    page: int


@dataclass
class Gazetteer:
    automaton: ahocorasick.Automaton
    names: dict[int, tuple[str, str]]
    forms: int


def build_gazetteer(conn: psycopg.Connection) -> Gazetteer:
    """One automaton over the padded token form of every linkable alias."""
    by_form: dict[str, dict[int, Candidate]] = defaultdict(dict)
    names = {}
    for alias, entity_id, kind, name, strict in conn.execute(
            ALIASES, (list(LINKED_KINDS),)):
        form = token_form(alias)
        if len(form.strip()) < MIN_FORM_CHARS or form.strip().isdigit():
            continue
        if form in STOP_FORMS and kind != "contract_area":
            continue
        cued = is_cue_form(form, kind)
        if kind == "contract_area" and area_code(form):
            cued = True
        current = by_form[form].get(entity_id)
        if current is None or (cued and not current.cued):
            by_form[form][entity_id] = Candidate(entity_id, kind, strict, cued)
        names[entity_id] = (kind, name)

    automaton = ahocorasick.Automaton()
    for form, candidates in by_form.items():
        automaton.add_word(form, (len(form), tuple(candidates.values())))
    automaton.make_automaton()
    return Gazetteer(automaton, names, len(by_form))


def find_matches(gazetteer: Gazetteer, text: str) -> list[Match]:
    """Whole-token matches; the padding spaces are not part of the span."""
    found = []
    for end, (length, candidates) in gazetteer.automaton.iter(text):
        start = end - length + 1
        found.append(Match(start + 1, end, candidates))
    return longest_matches(found)


def read_chunks(conn: psycopg.Connection, sample: int) -> list[ChunkText]:

    chunks = [ChunkText(*row) for row in conn.execute(CHUNKS)]
    if sample:
        chunks = random.Random(7).sample(chunks, min(sample, len(chunks)))
        chunks.sort(key=lambda c: c.doc_id)
    return chunks


def document_priors(conn: psycopg.Connection) -> dict[str, set[int]]:

    priors: dict[str, set[int]] = defaultdict(set)
    for doc_id, entity_id in conn.execute(DOCUMENT_UNITS):
        priors[doc_id].add(entity_id)
    return priors


def with_context(match: Match, text: str, case_text: str | None,
                 folded: str) -> Match:
    """Flags decide() needs: lowercase word, marker nearby, joined name."""
    single = " " not in text[match.start:match.end]
    lowercase = bool(single and case_text
                     and case_text[match.start:match.end].islower())
    joined = True
    if any(c.kind == "well" for c in match.candidates):
        joined = joined_in(folded, text[match.start:match.end])
    return replace(match, lowercase=lowercase,
                   marker=next_to_marker(text, match.start, match.end),
                   joined=joined)


def chunk_matches(gazetteer: Gazetteer, chunks: list[ChunkText]
                  ) -> dict[str, list[tuple[Match, set[str]]]]:

    out = {}
    for chunk in chunks:
        text = normalize(chunk.text)
        case_text = cased(chunk.text)
        if len(case_text) != len(text):
            case_text = None
        folded = fold(chunk.text).upper()
        found = []
        for match in find_matches(gazetteer, text):
            match = with_context(match, text, case_text, folded)
            found.append((match, cued_kinds(text, match.start, match.end)))
        out[chunk.chunk_id] = found
    return out


def cued_entities(matches: list[tuple[Match, set[str]]]) -> set[int]:

    found = set()
    for match, cues in matches:
        for candidate in match.candidates:
            if candidate.cued or candidate.kind in cues:
                found.add(candidate.entity_id)
    return found


@dataclass
class Linked:
    rows: list[tuple]
    review: list[dict]
    by_rule: dict[str, int]


def link_chunks(gazetteer: Gazetteer, chunks: list[ChunkText],
                priors: dict[str, set[int]]) -> Linked:
    """Two passes per document: cued entities first, then every match."""
    matches = chunk_matches(gazetteer, chunks)
    by_doc: dict[str, list[ChunkText]] = defaultdict(list)
    for chunk in chunks:
        by_doc[chunk.doc_id].append(chunk)

    rows, samples = [], defaultdict(list)
    by_rule: dict[str, int] = defaultdict(int)
    for doc_id, members in by_doc.items():
        prior = set(priors.get(doc_id, set()))
        for chunk in members:
            prior |= cued_entities(matches[chunk.chunk_id])

        for chunk in members:
            best: dict[int, tuple[Link, int]] = {}
            spans: dict[int, Match] = {}
            for match, cues in matches[chunk.chunk_id]:
                for link in decide(match, cues, prior):
                    hits = best.get(link.entity_id, (link, 0))[1] + 1
                    kept = best.get(link.entity_id, (link, 0))[0]
                    if link.confidence > kept.confidence:
                        kept = link
                    best[link.entity_id] = (kept, hits)
                    spans.setdefault(link.entity_id, match)
            for entity_id, (link, hits) in best.items():
                rows.append((chunk.chunk_id, entity_id, min(hits, 32767),
                             link.confidence, link.rule))
                by_rule[link.rule] += 1
                kind = gazetteer.names[entity_id][0]
                samples[kind].append((chunk, entity_id, link, spans[entity_id]))

    review = review_sample(gazetteer, samples)
    return Linked(rows, review, dict(by_rule))


def snippet(chunk: ChunkText, match: Match) -> str:
    """Original text around a match, mapped back from token offsets."""
    _, origin = normalize_with_map(chunk.text)
    start = origin[min(match.start, len(origin) - 1)]
    end = origin[min(match.end, len(origin) - 1)]
    left = max(0, start - SNIPPET_CHARS)
    right = min(len(chunk.text), end + SNIPPET_CHARS)
    text = (chunk.text[left:start] + "[[" + chunk.text[start:end] + "]]"
            + chunk.text[end:right])
    return " ".join(text.split())


def review_sample(gazetteer: Gazetteer, samples: dict) -> list[dict]:

    rng = random.Random(11)
    review = []
    for kind in sorted(samples):
        picked = samples[kind]
        if len(picked) > REVIEW_PER_KIND:
            picked = rng.sample(picked, REVIEW_PER_KIND)
        for chunk, entity_id, link, match in picked:
            review.append({
                "kind": kind,
                "entity": gazetteer.names[entity_id][1],
                "rule": link.rule,
                "confidence": link.confidence,
                "citation": chunk.citation,
                "page": chunk.page,
                "chunk_id": chunk.chunk_id,
                "snippet": snippet(chunk, match),
                "correct": "",
            })
    return review


def write_review(path: Path, review: list[dict]) -> None:

    if not review:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review[0]))
        writer.writeheader()
        writer.writerows(review)
