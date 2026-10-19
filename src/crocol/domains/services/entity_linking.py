import re
import unicodedata
from dataclasses import dataclass

LINKED_KINDS = ("formation", "member", "group", "field", "well",
                "municipality", "organization", "seismic_3d", "fault",
                "contract_area")
UNIT_KINDS = ("formation", "member", "group")

CUES_BEFORE = {
    "formation": {"FORMACION", "FORMACIONES", "FM", "FMS"},
    "member": {"MIEMBRO", "MIEMBROS", "MBR", "MB"},
    "group": {"GRUPO", "GRUPOS", "GP"},
    "field": {"CAMPO", "CAMPOS"},
    "well": {"POZO", "POZOS", "WELL", "WELLS"},
    "municipality": {"MUNICIPIO", "MUNICIPIOS", "MUNICIPALITY"},
    "contract_area": {"CONTRATO", "CONTRATOS", "BLOQUE", "BLOQUES",
                      "CONTRACT", "BLOCK", "ASOCIACION"},
    "seismic_3d": {"PROGRAMA", "LEVANTAMIENTO", "SURVEY", "SISMICA"},
}
CUES_AFTER = {
    "formation": {"FORMATION", "FORMATIONS", "FM", "FMS"},
    "member": {"MEMBER", "MEMBERS", "MBR", "MB"},
    "group": {"GROUP", "GP"},
    "field": {"FIELD", "FIELDS"},
    "well": {"WELL", "WELLS"},
    "contract_area": {"CONTRACT", "BLOCK"},
}
WINDOW_BEFORE = 3
WINDOW_AFTER = 1
MARKER_WORDS = {"SHALE", "SHALES", "FOSSIL", "FOSILIFERO", "FOSILIFERA",
                "HORIZON", "HORIZONTE", "LUTITAS", "MARKER", "MARCADOR",
                "ALTO", "PALEOHIGH", "HIGH", "ANTICLINE", "ANTICLINES",
                "ANTICLINAL", "SYNCLINE", "SINCLINAL", "MONOCLINE",
                "MONOCLINAL"}
PLACE_KINDS = ("field", "municipality", "contract_area")

LEGAL_SUFFIXES = {
    "S", "A", "SA", "SAS", "LTDA", "LTD", "LIMITED", "INC", "CORP",
    "CORPORATION", "PLC", "LLC", "SUCURSAL", "EN", "DE", "COLOMBIA", "CIA",
    "Y", "E", "P", "ESP", "CO", "THE",
}
GENERIC_WORDS = {
    "ENERGY", "PETROLEUM", "OIL", "GAS", "COLOMBIA", "SERVICES",
    "RESOURCES", "EXPLORATION", "PETROLEO", "PETROLEOS", "COMPANY",
    "INTERNATIONAL", "HOLDINGS", "GROUP", "ANDINA", "WESTERN", "EASTERN",
    "NORTHERN", "SOUTHERN", "OCCIDENTAL", "ORIENTAL", "NORTE", "SUR",
    "CENTRAL", "NACIONAL", "NATIONAL", "AMERICAN", "GLOBAL", "GENERAL",
}
STOP_FORMS = {" VMM ", " VIM ", " VSM ", " MMV ", " MMB ", " ANH "}
YEAR_RE = re.compile(r"^(1[89]|20)\d\d[A-Z]?$")
MIN_ALIAS_CHARS = 4
DIGIT_RE = re.compile(r"\d")
COMBINING_RE = re.compile("[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff"
                          "\u20d0-\u20ff\ufe20-\ufe2f]")
NON_TOKEN_RE = re.compile(r"[^A-Z0-9]+")
CASED_TOKEN_RE = re.compile(r"[^A-Za-z0-9]+")
PAREN_RE = re.compile(r"^(.*?)\s*\((.*?)\)\s*$")


@dataclass(frozen=True)
class Candidate:
    entity_id: int
    kind: str
    strict: bool = False
    cued: bool = False


@dataclass(frozen=True)
class Match:
    start: int
    end: int
    candidates: tuple[Candidate, ...]
    lowercase: bool = False
    marker: bool = False
    joined: bool = True


@dataclass(frozen=True)
class Link:
    entity_id: int
    confidence: float
    rule: str


def fold_char(char: str) -> str:

    decomposed = unicodedata.normalize("NFD", char)
    kept = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return kept.upper()


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Space-padded token text (upper, unaccented) and source offsets."""
    out = [" "]
    origin = [0]
    for index, char in enumerate(text):
        for folded in fold_char(char):
            if folded.isalnum() and folded.isascii():
                out.append(folded)
                origin.append(index)
            elif out[-1] != " ":
                out.append(" ")
                origin.append(index)
    if out[-1] != " ":
        out.append(" ")
        origin.append(len(text))
    return "".join(out), origin


def fold(text: str) -> str:
    """Accents removed, case kept."""
    return COMBINING_RE.sub("", unicodedata.normalize("NFD", text))


def normalize(text: str) -> str:
    """Fast form of normalize_with_map(text)[0], for matching."""
    return " " + " ".join(NON_TOKEN_RE.split(fold(text).upper())).strip() + " "


def token_form(alias: str) -> str:
    """The padded form an alias must match in normalized text."""
    form = normalize(alias)
    return form if form.strip() else ""


def alias_variants(name: str) -> list[str]:
    """The name, plus both parts of 'MIDAS (CHUIRA)' style names."""
    variants = [name]
    found = PAREN_RE.match(name)
    if found:
        variants.extend(part for part in found.groups() if part.strip())
    return variants


def organization_short_names(name: str) -> list[str]:
    """Drop legal suffixes: 'LEWIS ENERGY COLOMBIA INC' -> 'LEWIS ENERGY'."""
    words = normalize(name).split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
        
    if not words:
        return []
    
    short = " ".join(words)
    if len(short) < MIN_ALIAS_CHARS:
        return []
    
    if len(words) == 1 and words[0] in GENERIC_WORDS:
        return []
    
    return [short]


def well_aliases(name: str) -> list[str]:
    """'ANH PAILITAS-1-X' is also written 'ANH Pailitas 1X'."""
    joined = re.sub(r"(\d)[-\s]+([A-Z])$", r"\1\2", name.strip())
    return [name] if joined == name else [name, joined]


def fault_aliases(name: str) -> list[str]:
    """'Falla de Ibagué' -> also 'Falla Ibagué' and 'Ibagué Fault'."""
    found = re.match(r"(?i)^falla\s+(?:de\s+)?(.+)$", name.strip())
    if not found:
        return [name]
    base = found.group(1)
    return [name, f"Falla {base}", f"{base} Fault"]


def unit_aliases(name: str, kind: str, extra: list[str]) -> list[str]:
    """Bare names plus the cue-word forms of a stratigraphic unit."""
    bare = [name, *extra]
    prefixes = {
        "formation": ("Formación", "Fm."),
        "member": ("Miembro", "Mbr."),
        "group": ("Grupo",),
    }[kind]
    suffix = {"formation": "Formation", "member": "Member",
              "group": "Group"}[kind]
    forms = list(bare)
    
    for base in bare:
        forms.extend(f"{prefix} {base}" for prefix in prefixes)
        forms.append(f"{base} {suffix}")
        
    return forms


def is_cue_form(form: str, kind: str) -> bool:
    """True when the alias itself carries its cue word ('FALLA ...')."""
    words = form.split()
    
    if kind == "fault":
        return True
    
    before = CUES_BEFORE.get(kind, set())
    after = CUES_AFTER.get(kind, set())
    
    return bool(words) and (words[0] in before or words[-1] in after)


def cued_kinds(text: str, start: int, end: int) -> set[str]:
    """Kinds announced by cue words just before or after a match."""
    before = text[:start].split()[-WINDOW_BEFORE:]
    after = text[end:].split()[:WINDOW_AFTER]
    kinds = set()
    
    for kind, words in CUES_BEFORE.items():
        if words.intersection(before):
            kinds.add(kind)
            
    for kind, words in CUES_AFTER.items():
        if words.intersection(after):
            kinds.add(kind)
            
    return kinds


def longest_matches(matches: list[Match]) -> list[Match]:
    """Drop matches contained in a longer one ('LA CIRA' in 'LA CIRA 3292')."""
    ordered = sorted(matches, key=lambda m: (m.start, -(m.end - m.start)))
    kept: list[Match] = []
    for match in ordered:
        if kept and match.start < kept[-1].end:
            if match.end <= kept[-1].end:
                continue
            
        kept.append(match)
        
    return kept


def cased(text: str) -> str:
    """normalize() without the upper-casing, for proper-noun checks."""
    return " " + " ".join(CASED_TOKEN_RE.split(fold(text))).strip() + " "


def next_to_marker(text: str, start: int, end: int) -> bool:
    """'La Cira shale', or a citation such as 'Morales et al. 1958'."""
    before = text[:start].split()[-2:]
    after = text[end:].split()[:2]
    
    if MARKER_WORDS.intersection(before + after[:1]):
        return True
    
    return after[:2] == ["ET", "AL"] or bool(after and YEAR_RE.match(after[0]))


def joined_in(folded: str, form: str) -> bool:
    """Tokens of a name appear with only a hyphen or space between them."""
    pattern = r"[-\s_]?".join(re.escape(t) for t in form.split())
    
    return re.search(rf"(?<![A-Z0-9]){pattern}(?![A-Z0-9])", folded) is not None


def decide(match: Match,
           cues: set[str],
           document_prior: set[int]
           ) -> list[Link]:
    """Pick the entities a match refers to, with a confidence and rule.

    A cue word decides the kind; Formación, Miembro and Grupo cue any
    stratigraphic unit. Without a cue, strict names never link, names shared
    by several kinds need document evidence, single lowercase words are
    common nouns, and the rest link by kind-specific rules.
    """
    announced = set(cues)
    if announced.intersection(UNIT_KINDS):
        announced.update(UNIT_KINDS)
    cued = [c for c in match.candidates if c.cued or c.kind in announced]
    if cued:
        return [Link(c.entity_id, 1.0, "cue") for c in cued]

    kinds = {c.kind for c in match.candidates}
    links = []
    for candidate in match.candidates:
        if candidate.strict:
            continue
        
        if candidate.kind == "well":
            if match.joined:
                links.append(Link(candidate.entity_id, 0.9, "well_name"))
            continue
        
        if match.lowercase:
            continue
        
        if match.marker and candidate.kind in PLACE_KINDS:
            continue
        
        if candidate.entity_id in document_prior:
            links.append(Link(candidate.entity_id, 0.8, "document_prior"))
            
        elif len(kinds) > 1:
            continue
        
        elif candidate.kind in ("organization", "seismic_3d"):
            links.append(Link(candidate.entity_id, 0.8, "unique_name"))
            
        elif candidate.kind == "municipality":
            links.append(Link(candidate.entity_id, 0.7, "unique_name"))
            
    return links


def area_code(form: str) -> bool:
    """Contract area codes such as 'VMM 53' carry their own number."""
    return bool(DIGIT_RE.search(form))
