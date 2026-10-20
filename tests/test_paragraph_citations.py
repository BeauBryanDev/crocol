from crocol.domains.services.citations import corpus_text
from crocol.domains.services.paragraph_citations import cap_citations


def test_one_source_is_cited_once_at_the_end_of_the_paragraph() -> None:
    text = ("Mugrosa es fluvial [C1]. Tiene canales [C1]. "
            "Y llanuras de inundación [C1].")
    assert cap_citations(text) == (
        "Mugrosa es fluvial. Tiene canales. Y llanuras de inundación [C1].")


def test_two_sources_stay_together_at_the_end() -> None:
    text = "La Luna es generadora [C2]. Su TOC es alto [C1, C2]."
    assert cap_citations(text) == (
        "La Luna es generadora. Su TOC es alto [C2, C1].")


def test_more_than_two_sources_keep_the_two_most_used() -> None:
    text = "Uno [C3]. Dos [C1]. Tres [C1]. Cuatro [C2]. Cinco [C3]."
    assert cap_citations(text) == "Uno. Dos. Tres. Cuatro. Cinco [C3, C1]."


def test_each_paragraph_is_capped_on_its_own() -> None:
    text = "A [C1]. B [C1].\n\nC [C2]. D [C3]. E [C4]."
    assert cap_citations(text) == "A. B [C1].\n\nC. D. E [C2, C3]."


def test_paragraph_without_final_stop_gets_the_label_appended() -> None:
    assert cap_citations("Valor [C1] en psi") == "Valor en psi [C1]"


def test_headings_and_uncited_text_are_untouched() -> None:
    text = "## Recomendación\n\nSin citas aquí.\n\n## Límites"
    assert cap_citations(text) == text


def test_bullets_sharing_one_source_are_cited_once_on_the_last() -> None:
    text = ("## Guía\n- Tasa: 432.4 STB/d [C1].\n"
            "- Piso de pwf: 2008 psi [C1].\n- pb: 2000 psi [C1].")
    assert cap_citations(text) == (
        "## Guía\n- Tasa: 432.4 STB/d.\n- Piso de pwf: 2008 psi.\n"
        "- pb: 2000 psi [C1].")


def test_bullets_with_different_sources_keep_their_own_pairs() -> None:
    text = ("- TOC: 4 % [C1] frente a 2 % [C2].\n"
            "- Ro: 0.8 [C3] frente a 1.1 [C4] y 0.9 [C5].")
    assert cap_citations(text) == (
        "- TOC: 4 % frente a 2 % [C1, C2].\n"
        "- Ro: 0.8 frente a 1.1 y 0.9 [C3, C4].")


def test_tables_and_code_are_left_verbatim() -> None:
    table = "| a | b |\n|---|---|\n| 1 [C1] | 2 [C2] |"
    assert cap_citations(table) == table


def test_kg_paragraph_is_capped_but_kept_apart() -> None:
    text = "Dato del corpus [C1].\n\nHecho general uno [KG]. Dos [KG]."
    assert cap_citations(text) == (
        "Dato del corpus [C1].\n\nHecho general uno. Dos [KG].")


def test_corpus_text_skips_a_whole_general_knowledge_paragraph() -> None:
    text = ("Dato del corpus. Otro dato [C1].\n\n"
            "Hecho general sin etiqueta propia. Otro hecho general [KG].")
    assert corpus_text(text) == "Dato del corpus. Otro dato [C1]."
