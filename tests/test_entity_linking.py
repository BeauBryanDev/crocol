import pytest

from crocol.domains.services.citations import (
    cited_labels,
    corpus_text,
    normalize_labels,
    replace_labels,
    without_suggestions,
)
from crocol.domains.services.entity_linking import (
    Candidate,
    Match,
    cued_kinds,
    decide,
    fault_aliases,
    is_cue_form,
    joined_in,
    longest_matches,
    next_to_marker,
    normalize,
    normalize_with_map,
    organization_short_names,
    token_form,
    unit_aliases,
    well_aliases,
)

TEXTS = [
    "La Formación La Luna (Turoniano) y el pozo Casabe-1352.",
    "ECOPETROL S.A., Bogotá – 2019; Simití/Tablazo ¿qué?",
    "  Ñandú çà  Ünïcode—dash 3D-2008 ",
    "",
]


@pytest.mark.parametrize("text", TEXTS)
def test_fast_normalize_equals_mapped(text: str) -> None:
    mapped, origin = normalize_with_map(text)
    assert normalize(text).strip() == mapped.strip()
    assert len(origin) == len(mapped)


def test_normalize_pads_tokens() -> None:
    assert normalize("Formación La-Luna, 1X") == " FORMACION LA LUNA 1X "
    assert token_form("La Cira-Infantas") == " LA CIRA INFANTAS "


def test_organization_short_names() -> None:
    assert organization_short_names("LEWIS ENERGY COLOMBIA INC") == [
        "LEWIS ENERGY"]
    assert organization_short_names("ECOPETROL S.A.") == ["ECOPETROL"]
    assert organization_short_names("OCCIDENTAL DE COLOMBIA, LLC") == []
    assert organization_short_names("S.A.S.") == []


def test_alias_builders() -> None:
    assert fault_aliases("Falla de La Sierra") == [
        "Falla de La Sierra", "Falla La Sierra", "La Sierra Fault"]
    assert well_aliases("ANH PAILITAS-1-X") == [
        "ANH PAILITAS-1-X", "ANH PAILITAS-1X"]
    assert well_aliases("CASABE-1352") == ["CASABE-1352"]
    forms = unit_aliases("Galembo", "member", [])
    assert "Miembro Galembo" in forms and "Galembo Member" in forms


def test_cue_forms_and_cue_words() -> None:
    assert is_cue_form(token_form("Formación La Luna"), "formation")
    assert is_cue_form(token_form("Falla de Cimitarra"), "fault")
    assert not is_cue_form(token_form("La Luna"), "formation")
    text = normalize("en el campo Colorado se perforó")
    start = text.index(" COLORADO ") + 1
    assert cued_kinds(text, start, start + len("COLORADO")) == {"field"}


def test_longest_match_wins() -> None:
    short = Match(1, 8, ())
    long = Match(1, 13, ())
    other = Match(20, 25, ())
    assert longest_matches([short, other, long]) == [long, other]


def test_markers_and_citations_block_places() -> None:
    text = normalize("la lutita La Cira shale y Morales et al. 1958")
    cira = text.index(" LA CIRA ") + 1
    assert next_to_marker(text, cira, cira + len("LA CIRA"))
    morales = text.index(" MORALES ") + 1
    assert next_to_marker(text, morales, morales + len("MORALES"))


def test_joined_well_names() -> None:
    assert joined_in("POZO CASABE-1352 Y", "CASABE 1352")
    assert not joined_in("MAGDALENA). ## 1. LOCALIZACION", "MAGDALENA 1")


FORMATION = Candidate(1, "formation")
FIELD = Candidate(2, "field")
STRICT = Candidate(3, "formation", strict=True)
WELL = Candidate(4, "well")
ORG = Candidate(5, "organization")
TOWN = Candidate(6, "municipality")


def links(match: Match, cues: set[str] = frozenset(),
          prior: set[int] = frozenset()) -> list[tuple[int, str]]:
    return [(link.entity_id, link.rule)
            for link in decide(match, set(cues), set(prior))]


def test_cue_decides_kind() -> None:
    match = Match(0, 5, (FORMATION, FIELD))
    assert links(match, {"field"}) == [(2, "cue")]
    assert links(match, {"formation"}) == [(1, "cue")]


def test_unit_cues_cover_members_and_groups() -> None:
    member = Candidate(7, "member")
    assert links(Match(0, 5, (member,)), {"formation"}) == [(7, "cue")]


def test_strict_names_need_a_cue() -> None:
    assert links(Match(0, 5, (STRICT,))) == []
    assert links(Match(0, 5, (STRICT,)), {"formation"}) == [(3, "cue")]


def test_ambiguous_names_need_document_evidence() -> None:
    match = Match(0, 5, (FORMATION, FIELD))
    assert links(match) == []
    assert links(match, prior={1}) == [(1, "document_prior")]


def test_strict_kind_still_makes_a_name_ambiguous() -> None:
    assert links(Match(0, 5, (STRICT, TOWN))) == []


def test_lowercase_single_words_are_common_nouns() -> None:
    assert links(Match(0, 4, (ORG,), lowercase=True)) == []
    assert links(Match(0, 4, (ORG,))) == [(5, "unique_name")]


def test_wells_link_only_when_written_joined() -> None:
    assert links(Match(0, 9, (WELL,))) == [(4, "well_name")]
    assert links(Match(0, 9, (WELL,), joined=False)) == []


def test_markers_block_place_kinds_only() -> None:
    assert links(Match(0, 5, (TOWN,), marker=True)) == []
    assert links(Match(0, 5, (FIELD,), marker=True), prior={2}) == []


def test_fields_without_cue_need_document_evidence() -> None:
    assert links(Match(0, 5, (FIELD,))) == []
    assert links(Match(0, 5, (FIELD,)), prior={2}) == [(2, "document_prior")]


def test_kg_label_is_a_citation_label() -> None:
    text = "La Luna es generadora [C1]. La refinería abrió en 1922 [KG]."
    assert cited_labels(text) == ["C1", "KG"]
    assert normalize_labels(["kg", "C2", "BACKGROUND"]) == ["KG", "C2"]
    rendered = replace_labels(text, {"C1": "(Autor, 2016)",
                                     "KG": "(Crocol-KG-2026)"})
    assert rendered.endswith("abrió en 1922 (Crocol-KG-2026).")


def test_corpus_text_drops_general_knowledge_sentences() -> None:
    text = "Dato del corpus [C1]. Dato general [KG]. Sin cita."
    assert corpus_text(text) == "Dato del corpus [C1]. Sin cita."


def test_label_after_the_full_stop_stays_with_its_sentence() -> None:
    text = "Dato del corpus [C1].\nCapacidad de 150.000 barriles. [KG]"
    assert corpus_text(text) == "Dato del corpus [C1]."


def test_suggested_work_is_not_checked_as_claims() -> None:
    text = ("La Luna es generadora [C1].\n\n## Investigación sugerida\n"
            "- Analizar 30 muestras de núcleo del Miembro Galembo.")
    assert without_suggestions(text) == "La Luna es generadora [C1]."
    assert corpus_text(text) == "La Luna es generadora [C1]."
    english = "Fact [C2].\n## Suggested further work\n- Log 3 wells."
    assert corpus_text(english) == "Fact [C2]."
    assert without_suggestions("No section here [C1].") == (
        "No section here [C1].")

