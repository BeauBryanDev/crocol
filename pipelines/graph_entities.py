from dataclasses import dataclass, field

import psycopg
import yaml

from config.settings import ROOT
from crocol.domains.services.entity_linking import (
    alias_variants,
    fault_aliases,
    normalize,
    organization_short_names,
    unit_aliases,
    well_aliases,
)

FORMATIONS = ROOT / "kg" / "formations.yaml"
STOP_ALIASES = ROOT / "kg" / "stop_aliases.yaml"
GOVERNING_REGULATION = "Acuerdo No. 02 de 2017"
VMM_BASIN = "Valle Medio del Magdalena"
WELL_MIN_LETTERS = 3

WELLS = """
SELECT w.well_id, w.well_name, w.uwi, w.status, w.field_id,
       w.municipality_id, w.operator_id, w.contract_name, f.name
FROM core.wells w LEFT JOIN core.fields f USING (field_id)
ORDER BY w.well_id
"""
FIELDS = "SELECT field_id, name FROM core.fields ORDER BY field_id"
MUNICIPALITIES = """
SELECT municipality_id, name, department, dane_code
FROM core.municipalities ORDER BY municipality_id
"""
MUNICIPALITY_ALIASES = "SELECT municipality_id, alias FROM core.municipality_aliases"
ORGANIZATIONS = "SELECT org_id, canonical_name, roles FROM core.organizations"
ORGANIZATION_ALIASES = "SELECT org_id, alias FROM core.organization_aliases"
SURVEYS = """
SELECT survey_id, name, acq_year, operator_id, contract_name
FROM core.seismic_3d ORDER BY survey_id
"""
FAULTS = """
SELECT name, min(fault_id), count(*), min(fault_type),
       round(sum(length_km)::numeric, 1)
FROM core.faults WHERE name IS NOT NULL GROUP BY name ORDER BY name
"""
DOCUMENTS = """
SELECT doc_id, title, citation, authors, institution, topics, formations,
       legal, doc_type, collection, scope, year
FROM rag.documents WHERE scope <> 'excluded' ORDER BY doc_id
"""


@dataclass
class EntityRow:
    kind: str
    key: str
    name: str
    ref_table: str | None = None
    ref_id: str | None = None
    props: dict = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)


@dataclass
class EdgeRow:
    src: tuple[str, str]
    rel: str
    dst: tuple[str, str]
    source: str
    evidence: dict = field(default_factory=dict)


@dataclass
class GraphDraft:
    entities: dict[tuple[str, str], EntityRow] = field(default_factory=dict)
    edges: list[EdgeRow] = field(default_factory=list)

    def add(self, row: EntityRow) -> tuple[str, str]:

        ident = (row.kind, row.key)
        known = self.entities.get(ident)
        if known is None:
            self.entities[ident] = row
        else:
            known.aliases.extend(a for a in row.aliases
                                 if a not in known.aliases)
        return ident

    def link(self, src: tuple[str, str], rel: str, dst: tuple[str, str],
             source: str, evidence: dict | None = None) -> None:

        if src != dst:
            self.edges.append(EdgeRow(src, rel, dst, source, evidence or {}))


def key_of(value: str) -> str:
    """Python twin of core.name_key for names that are not core rows."""
    return normalize(value).replace(" ", "")


def display(value: str) -> str:

    return " ".join(value.replace("_", " ").split())


def load_units(draft: GraphDraft) -> dict[str, tuple[str, str]]:
    """Curated units; returns alias key -> entity, for formation names."""
    data = yaml.safe_load(FORMATIONS.read_text(encoding="utf-8"))
    by_name: dict[str, tuple[str, str]] = {}
    by_alias: dict[str, tuple[str, str]] = {}
    for unit in data["units"]:
        extra = [str(a) for a in unit.get("aliases") or []]
        props = {"age": unit.get("age"), "strict": bool(unit.get("strict"))}
        ident = draft.add(EntityRow(
            unit["kind"], key_of(unit["name"]), unit["name"],
            props=props,
            aliases=unit_aliases(unit["name"], unit["kind"], extra)))
        by_name[unit["name"]] = ident
        for alias in [unit["name"], *extra]:
            by_alias[key_of(alias)] = ident

    for unit in data["units"]:
        ident = by_name[unit["name"]]
        for rel, field_name in (("PART_OF", "part_of"),
                                ("OVERLIES", "overlies"),
                                ("EQUIVALENT_OF", "equivalent_of")):
            target = unit.get(field_name)
            if target:
                draft.link(ident, rel, by_name[target], "curated",
                           {"file": "kg/formations.yaml"})
    return by_alias


def load_core(conn: psycopg.Connection, draft: GraphDraft) -> None:

    basin = draft.add(EntityRow("basin", key_of(VMM_BASIN), VMM_BASIN,
                                "core.basins", "1", aliases=[VMM_BASIN, "VMM"]))

    fields = {}
    for field_id, name in conn.execute(FIELDS):
        ident = draft.add(EntityRow("field", str(field_id), name,
                                    "core.fields", str(field_id),
                                    aliases=alias_variants(name)))
        fields[field_id] = ident
        draft.link(ident, "IN_BASIN", basin, "attribute")

    municipalities = {}
    extra: dict[int, list[str]] = {}
    for municipality_id, alias in conn.execute(MUNICIPALITY_ALIASES):
        extra.setdefault(municipality_id, []).append(alias)
    for municipality_id, name, department, dane in conn.execute(MUNICIPALITIES):
        municipalities[municipality_id] = draft.add(EntityRow(
            "municipality", str(municipality_id), f"{name} ({department})",
            "core.municipalities", str(municipality_id),
            {"department": department, "dane_code": dane},
            [name, *extra.get(municipality_id, [])]))

    organizations = load_organizations(conn, draft)
    areas: dict[str, tuple[str, str]] = {}

    def area(contract_name: str | None) -> tuple[str, str] | None:
        if not contract_name:
            return None
        key = key_of(contract_name)
        if key not in areas:
            name = display(contract_name)
            areas[key] = draft.add(EntityRow("contract_area", key, name,
                                             aliases=[name]))
        return areas[key]

    for row in conn.execute(WELLS):
        (well_id, name, uwi, status, field_id, municipality_id,
         operator_id, contract_name, field_name) = row
        letters = sum(ch.isalpha() for ch in name)
        has_number = any(ch.isdigit() for ch in name)
        well = draft.add(EntityRow(
            "well", str(well_id), name, "core.wells", str(well_id),
            {"uwi": uwi, "status": status, "field": field_name,
             "strict": not has_number or letters < WELL_MIN_LETTERS},
            well_aliases(name)))
        if field_id in fields:
            draft.link(well, "IN_FIELD", fields[field_id], "attribute")
        if municipality_id in municipalities:
            draft.link(well, "LOCATED_IN", municipalities[municipality_id],
                       "attribute")
        if operator_id in organizations:
            draft.link(well, "OPERATED_BY", organizations[operator_id],
                       "attribute")
        contract = area(contract_name)
        if contract:
            draft.link(well, "IN_CONTRACT", contract, "attribute")

    for survey_id, name, year, operator_id, contract_name in conn.execute(SURVEYS):
        short = name.split(" 3D")[0]
        survey = draft.add(EntityRow(
            "seismic_3d", str(survey_id), name, "core.seismic_3d",
            str(survey_id), {"acq_year": year},
            [name, f"{short} 3D"]))
        if operator_id in organizations:
            draft.link(survey, "OPERATED_BY", organizations[operator_id],
                       "attribute")
        contract = area(contract_name)
        if contract:
            draft.link(survey, "IN_CONTRACT", contract, "attribute")

    for name, fault_id, segments, fault_type, length in conn.execute(FAULTS):
        draft.add(EntityRow(
            "fault", key_of(name), name, "core.faults", str(fault_id),
            {"segments": segments, "fault_type": fault_type,
             "length_km": float(length)},
            fault_aliases(name)))


def load_organizations(conn: psycopg.Connection,
                       draft: GraphDraft) -> dict[int, tuple[str, str]]:

    extra: dict[int, list[str]] = {}
    for org_id, alias in conn.execute(ORGANIZATION_ALIASES):
        extra.setdefault(org_id, []).append(alias)

    organizations = {}
    for org_id, name, roles in conn.execute(ORGANIZATIONS):
        aliases = [name, *extra.get(org_id, [])]
        for alias in list(aliases):
            aliases.extend(s for s in organization_short_names(alias)
                           if s not in aliases)
        organizations[org_id] = draft.add(EntityRow(
            "organization", key_of(name), name, "core.organizations",
            str(org_id), {"roles": list(roles)}, aliases))
    return organizations


def organization_for(draft: GraphDraft, name: str) -> tuple[str, str]:
    """Snap a contractor name to a known organization, or add one."""
    wanted = {key_of(name), *(key_of(s) for s in organization_short_names(name))}
    for ident, row in draft.entities.items():
        if ident[0] != "organization":
            continue
        keys = {key_of(alias) for alias in row.aliases}
        if wanted & keys:
            if name not in row.aliases:
                row.aliases.append(name)
            return ident
    return draft.add(EntityRow("organization", key_of(name), name,
                               aliases=[name, *organization_short_names(name)]))


def person_aliases(author: str) -> list[str]:

    surname, _, given = (part.strip() for part in author.partition(","))
    aliases = [author]
    if given:
        aliases.append(f"{given} {surname}")
    if surname:
        aliases.append(surname)
    return aliases


def load_documents(conn: psycopg.Connection, draft: GraphDraft,
                   units: dict[str, tuple[str, str]]) -> dict:

    regulation = draft.add(EntityRow(
        "regulation", key_of(GOVERNING_REGULATION), GOVERNING_REGULATION,
        aliases=[GOVERNING_REGULATION, "Acuerdo 02 de 2017"]))
    unknown_formations: set[str] = set()
    for row in conn.execute(DOCUMENTS):
        (doc_id, title, citation, authors, institution, topics, formations,
         legal, doc_type, collection, scope, year) = row
        document = draft.add(EntityRow(
            "document", doc_id, title, "rag.documents", doc_id,
            {"citation": citation, "doc_type": doc_type,
             "collection": collection, "scope": scope, "year": year},
            [title, citation]))

        for position, author in enumerate(authors, 1):
            person = draft.add(EntityRow("person", key_of(author), author,
                                         aliases=person_aliases(author)))
            draft.link(document, "AUTHORED_BY", person, "metadata",
                       {"position": position})
        if institution:
            draft.link(document, "PUBLISHED_BY", draft.add(EntityRow(
                "institution", key_of(institution), institution,
                aliases=[institution])), "metadata")
        for topic in topics:
            draft.link(document, "ABOUT", draft.add(EntityRow(
                "topic", topic, display(topic),
                aliases=[topic, display(topic)])), "metadata")
        for name in formations:
            unit = units.get(key_of(name))
            if unit is None:
                unknown_formations.add(name)
                continue
            draft.link(document, "DESCRIBES", unit, "metadata")

        legal = legal or {}
        if legal.get("regulation"):
            rule = draft.add(EntityRow(
                "regulation", key_of(legal["regulation"]), legal["regulation"],
                aliases=[legal["regulation"]]))
            draft.link(rule, "DESCRIBED_IN", document, "metadata")
        if doc_type == "contract" and legal.get("area"):
            load_contract(draft, document, doc_id, legal, regulation)

    return {"unknown_formations": sorted(unknown_formations)}


def load_contract(draft: GraphDraft, document: tuple[str, str], doc_id: str,
                  legal: dict, regulation: tuple[str, str]) -> None:

    area_name = legal["area"]
    contract = draft.add(EntityRow(
        "contract", doc_id,
        f"Contrato {legal.get('contract_type', '')} {area_name}".replace("  ", " "),
        "rag.documents", doc_id,
        {"contract_type": legal.get("contract_type"),
         "signing_date": legal.get("signing_date"),
         "contractor": legal.get("contractor")}))
    area = draft.add(EntityRow("contract_area", key_of(area_name), area_name,
                               aliases=[area_name]))
    draft.link(contract, "COVERS", area, "metadata")
    draft.link(contract, "DESCRIBED_IN", document, "metadata")
    draft.link(contract, "GOVERNED_BY", regulation, "curated",
               {"note": "2022 ANH contracts are filed with Acuerdo 02/2017"})
    if legal.get("contractor"):
        draft.link(organization_for(draft, legal["contractor"]), "HOLDS",
                   contract, "metadata")
    if legal.get("basin"):
        basin = draft.add(EntityRow("basin", key_of(legal["basin"]),
                                    legal["basin"], aliases=[legal["basin"]]))
        draft.link(area, "IN_BASIN", basin, "metadata")


def apply_stop_aliases(draft: GraphDraft) -> dict:
    """Owner-reviewed false friends: strict entities and dropped aliases."""
    data = yaml.safe_load(STOP_ALIASES.read_text(encoding="utf-8"))
    strict = {(e["kind"], key_of(e["name"])) for e in data.get("strict") or []}
    dropped = {(e["kind"], key_of(e["alias"]))
               for e in data.get("drop_aliases") or []}
    hits = {"strict": 0, "dropped": 0}
    for (kind, _), row in draft.entities.items():
        keys = {key_of(alias) for alias in [row.name, *row.aliases]}
        if any((kind, key) in strict for key in keys):
            row.props["strict"] = True
            hits["strict"] += 1
        kept = [a for a in row.aliases if (kind, key_of(a)) not in dropped]
        hits["dropped"] += len(row.aliases) - len(kept)
        row.aliases = kept
    return hits


def build_draft(conn: psycopg.Connection) -> tuple[GraphDraft, dict]:

    draft = GraphDraft()
    units = load_units(draft)
    load_core(conn, draft)
    notes = load_documents(conn, draft, units)
    notes["stop_aliases"] = apply_stop_aliases(draft)
    return draft, notes
