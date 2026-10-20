import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))

from spatial_lookups import (  # noqa: E402
    clean_text,
    group_organizations,
    merge_review,
    org_key,
    propose,
    write_review,
)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("  TEXAS\xa0PETROLEUM   COMPANY ", "TEXAS PETROLEUM COMPANY"),
        ("PENDIENTE", None),
        (" ", None),
        ("0", None),
    ],
)
def test_clean_text(raw: str, clean: str | None) -> None:
    assert clean_text(raw) == clean


@pytest.mark.parametrize(
    "variants",
    [
        ["WESTERN", "WESTERN GEOPHYSICAL", "WESTERN GEOPHYSICAL COMPANY"],
        ["GAPS", "GAPS LTDA."],
        ["G.S.I.", "GSI"],
        ["GEOESPECTRO", "GEOESPECTRO S.A.S."],
        ["CGL - COMPANIA GEOFISICA LATINOAMERICANA S.A",
         "CGL COMPAÑIA GEOFISICA LATINOAMERICANA S.A.S"],
        ["GEOFISICA SISTEMAS Y SOLUCIONES",
         "GEOFISICA SISTEMAS Y SOLUCIONES, GSS S.A.",
         "GSS GEOFISICA SISTEMAS Y SOLUCIONES S.A."],
        ["ECOPETROL", "ECOPETROL S.A."],
    ],
)
def test_known_variants_share_one_organization(variants: list[str]) -> None:
    assert len({org_key(name) for name in variants}) == 1


def test_different_companies_stay_apart() -> None:
    assert org_key("WESTERN ATLAS INTERNATIONAL") != org_key("WESTERN")
    assert org_key("GEOKINETICS") != org_key("GEOSOURCE")


def test_group_organizations_picks_most_frequent_variant() -> None:
    names = Counter({"GAPS": 82, "GAPS LTDA.": 112, "C.G.G.": 3})
    groups = group_organizations(names)
    assert groups["GAPS LTDA."] == ["GAPS", "GAPS LTDA."]
    assert groups["C.G.G."] == ["C.G.G."]


def test_municipality_proposals_merge_accents_and_parentheses() -> None:
    pairs = Counter({
        ("BOYACA", "PUERTO BOYACA"): 2500,
        ("BOYACÁ", "PUERTO BOYACÁ"): 6,
        ("ANTIOQUIA", "YONDO (CASABE)"): 1623,
        ("ANTIOQUIA", "YONDÓ"): 10,
    })
    proposals = propose(pairs)
    assert proposals[("BOYACA", "PUERTO BOYACA")] == ("BOYACÁ",
                                                     "PUERTO BOYACÁ")
    assert proposals[("ANTIOQUIA", "YONDO (CASABE)")] == ("ANTIOQUIA",
                                                         "YONDÓ")


def test_review_file_keeps_owner_edits(tmp_path: Path) -> None:
    path = tmp_path / "review.csv"
    pairs = Counter({("SANTANDER", "BARRANCABERMEJA"): 3687})
    rows, changed = merge_review(pairs, path)
    assert changed and rows[0]["reviewed"] is False

    rows[0]["canonical_municipality"] = "Barrancabermeja"
    rows[0]["reviewed"] = True
    write_review(rows, path)

    pairs[("SANTANDER", "PUERTO WILCHES")] = 120
    rows, changed = merge_review(pairs, path)
    by_name = {row["municipality"]: row for row in rows}
    assert changed
    assert by_name["BARRANCABERMEJA"]["reviewed"] is True
    assert by_name["BARRANCABERMEJA"]["canonical_municipality"] == (
        "Barrancabermeja")
    assert by_name["PUERTO WILCHES"]["reviewed"] is False
