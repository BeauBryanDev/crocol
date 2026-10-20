import pytest

from crocol.domains.services.citations import (
    cited_labels,
    normalize_labels,
    render_citation,
    replace_labels,
)
from crocol.domains.services.verification import (
    readings,
    unknown_labels,
    unsupported_numbers,
)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("1.234,5", {1234.5}),
        ("1,234.5", {1234.5}),
        ("3,5", {3.5}),
        ("2.064", {2064.0, 2.064}),
        ("1.234.567", {1234567.0}),
        ("475", {475.0}),
    ],
)
def test_readings_cover_spanish_and_english(token: str,
                                            expected: set[float]) -> None:
    assert readings(token) == expected


def test_numbers_match_across_separator_conventions() -> None:
    evidence = ["Porosidad de 1.234,5 mD y TOC de 7,72 %"]
    answer = "Permeability 1,234.5 mD and TOC 7.72 % [C1]."
    assert unsupported_numbers(answer, evidence) == []


def test_invented_number_is_reported() -> None:
    evidence = ["La Formación La Luna tiene 300 m de espesor."]
    answer = "La Luna tiene 350 m de espesor [C1]."
    assert unsupported_numbers(answer, evidence) == ["350"]


def test_labels_and_small_integers_are_ignored() -> None:
    answer = "Hay 3 miembros [C12] y 2 pozos [C3]."
    assert unsupported_numbers(answer, ["sin cifras"]) == []


def test_unknown_labels() -> None:
    assert unknown_labels("Dato [C1, C9].", ["C1", "C2"]) == ["C9"]


def test_render_citation_pages() -> None:
    assert render_citation("Rueda Acevedo, 2016", 41, 41) == (
        "(Rueda Acevedo, 2016, p. 41)")
    assert render_citation("Rueda Acevedo, 2016", 41, 43) == (
        "(Rueda Acevedo, 2016, pp. 41-43)")


def test_replace_labels_groups_and_drops_unknown() -> None:
    rendered = {
        "C1": "(A, 2010, p. 2)",
        "C3": "(B, 2012, p. 9)",
    }
    text = "Uno [C1, C3]. Dos [C7]."
    assert replace_labels(text, rendered) == (
        "Uno (A, 2010, p. 2; B, 2012, p. 9). Dos.")
    assert cited_labels(text) == ["C1", "C3", "C7"]


def test_normalize_labels_accepts_model_variants() -> None:
    assert normalize_labels(["[C2]", "c1", "C3, C4", "C2"]) == [
        "C2", "C1", "C3", "C4"]


def test_version_strings_found_verbatim_are_supported() -> None:
    evidence = ["modelo: MobileNetV2-UNet v2.0.0; umbral: 0.5"]
    assert unsupported_numbers("Modelo v2.0.0 con umbral 0.5.", evidence) == []
    assert unsupported_numbers("Modelo v3.1.0.", evidence) == ["3.1.0"]
