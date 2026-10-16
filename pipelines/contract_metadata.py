"""Metadata and structure rules for ANH legal documents (contracts, acuerdos, decrees, resolutions)."""

import difflib
import re
import unicodedata

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
BASINS = {
    "VMM": "Valle Medio del Magdalena",
    "VIM": "Valle Inferior del Magdalena",
    "VSM": "Valle Superior del Magdalena",
}
KNOWN_CONTRACTORS = [
    "CNE OIL & GAS S.A.S.",
    "ECOPETROL S.A.",
    "FRONTERA ENERGY COLOMBIA CORP.",
    "LEWIS ENERGY COLOMBIA INC.",
    "PAREX RESOURCES (COLOMBIA) LTD",
]
CONTRACTOR_MATCH_CUTOFF = 0.8
ORDINALS = (r"PRIMER[OA]?|SEGUND[OA]|TERCER[OA]?|CUART[OA]|QUINT[OA]|SEXT[OA]|S[EÉ]PTIM[OA]|"
            r"OCTAV[OA]|NOVEN[OA]|D[EÉ]CIM[OA]|[IVXLC]+|\d+")

AREA_RE = re.compile(r"\b(VMM|VIM|VSM)\s*[-_ ]?\s*(\d+(?:\s*-\s*\d+)?)", re.I)
DATE_RE = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:de|del)\s+(\d{4})", re.I)
ACUERDO_RE = re.compile(r"ACUERDO\s+No\.?\s*(\d+)\s+DE\s+(\d{4})", re.I)
DRAFT_ACUERDO_RE = re.compile(r"ACUERDO\s+(X{2,})\s+DEL?\s+(\d{4})", re.I)
RESOLUCION_RE = re.compile(r"RESOLUCI[OÓ]N\s+No\.?\s*(\S+)\s+DEL?\s+(\S+)", re.I)
DECRETO_FILE_RE = re.compile(r"Decreto[-_ ](\d+)[-_ ](\d{1,2})([A-Za-z]{3})(\d{4})", re.I)
NUMERIC_DATE_RE = re.compile(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})")
SUBJECT_RE = re.compile(r"[“\"]\s*(Por\s+(?:el|la|medio\s+del?|medio\s+de\s+la)\s+cual[^”\"]{10,600})[”\"]", re.I)
EN_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
ANH_ISSUER = "Agencia Nacional de Hidrocarburos (ANH)"
DOC_TYPE_NAMES = {
    "acuerdo": "Acuerdo", "anexo_acuerdo": "Anexos del Acuerdo", "anexo_tecnico": "Anexo Técnico",
    "aviso": "Aviso", "decreto": "Decreto", "memoria_justificativa": "Memoria Justificativa",
    "resolucion": "Resolución", "contrato": "Contrato",
}

TOC_PAGE_RE = re.compile(
    r"\b(CONTENIDO|[IÍ]NDICE|TABLA DE CONTENIDO|DOCUMENTOS CONSTITUTIVOS)\b"
)
TOC_ENTRY_RE = re.compile(r"\s\d{1,3}$")
ARTICLE_NUMBER = (rf"(?:(?:{ORDINALS})[A-Za-z°º]*\s*[.\-–:]+"
                  r"|\d+(?:\s?\.\s?\d+|\s\d+(?=\.))+\.?)")
STRUCTURE_ONLY = [
    (re.compile(r"^(LIBRO|PARTE|T[IÍ]TULO|ANEXO|Anexo)\s*[\dIVXLC.\s]+$"), 2),
    (re.compile(r"^CAP[IÍ]TULO\s*[\dIVXLC.\s]+$"), 3),
    (re.compile(r"^(SECCI[OÓ]N|ART[IÍ]CULO|Art[ií]culo)\s*\d[\d.\s]*$"), 4),
]
HEADING_PATTERNS = [
    (re.compile(r"^ANEXO\s*([A-Z]|\d+)\b"), 2),
    (re.compile(rf"^(LIBRO|PARTE)\s+({ORDINALS})\b"), 2),
    (re.compile(rf"^SECCI[OÓ]N\s+({ORDINALS})\b"), 4),
    (re.compile(r"^Anexo\s+\d+$"), 2),
    (re.compile(rf"^T[IÍ]TULO\s+({ORDINALS})\b"), 2),
    (re.compile(rf"^CAP[IÍ]TULO\s+({ORDINALS})\b"), 3),
    (re.compile(rf"^CL[AÁ]USULA\s+({ORDINALS})\b"), 4),
    (re.compile(r"^\d{1,2}\.\s+[A-ZÁÉÍÓÚÑ][^.:;]{2,65}$"), 4),
    (re.compile(r"^[A-E]\.?\s?\d{1,2}(\.\d{1,2})?\.?\s+[A-ZÁÉÍÓÚÑ][^:;]{2,65}$"), 4),
    (re.compile(r"^\d{1,2}\.\d{1,2}\.?\s+[A-ZÁÉÍÓÚÑ][^.:;]{2,65}$"), 5),
]
LEGAL_MARGIN_RE = re.compile(
    r"^(anexo\s*[a-z1-9]\b.{0,60}|.{0,60}p\S{0,2}g?ina\.?\s*[\dSOIl]{1,3}\s*(de|of)\s*[\dSOIl\]]{1,3}.{0,20}|"
    r"anh\s*[-–•·]?\s*con[a-z]{0,3}rato\b.{0,120})$",
    re.I,
)
INLINE_HEADING_RE = re.compile(
    rf"^((?:ART[IÍ]CULO|Art[ií]culo|CL[AÁ]USULA|Cl[aá]usula)\s+{ARTICLE_NUMBER}"
    r"\s*(?:[^.:]|\.(?=\S)){0,220}?)\s*[:.](?:\s+(\S.*))?$",
    re.S,
)
MAX_HEADING_CHARS = 140


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def parse_date(text):
    match = DATE_RE.search(text)
    if not match:
        return ""
    day, month, year = match.groups()
    month_number = MONTHS.get(strip_accents(month.lower()))
    if not month_number:
        return ""
    return f"{int(year):04d}-{month_number:02d}-{int(day):02d}"


def value_after(label_re, lines, stop_re):
    for index, line in enumerate(lines):
        match = label_re.match(line)
        if not match:
            continue
        rest = line[match.end():].strip(" :;")
        parts = [rest] if rest else []
        for following in lines[index + 1:index + 4]:
            if stop_re.match(following):
                break
            parts.append(following.strip())
            if rest or len(parts) >= 2 and not parts[-1].endswith(("(", ",")):
                break
        return " ".join(p for p in parts if p).strip(" .:")
    return ""


def canonical_contractor(raw):
    cleaned = re.sub(r"\s+", " ", raw).strip(" '\"`.,;:-")
    keys = {strip_accents(name.upper()).rstrip("."): name for name in KNOWN_CONTRACTORS}
    match = difflib.get_close_matches(strip_accents(cleaned.upper()).rstrip("."), list(keys),
                                      n=1, cutoff=CONTRACTOR_MATCH_CUTOFF)
    return keys[match[0]] if match else cleaned


def numeric_date(text):
    match = NUMERIC_DATE_RE.search(text)
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}" if 1 <= month <= 12 and 1 <= day <= 31 else ""


def legal_metadata(first_pages_text, file_name):
    lines = [line.strip() for line in first_pages_text.splitlines() if line.strip()]
    upper = strip_accents(first_pages_text.upper())
    head = strip_accents(re.sub(r"\s+", " ", first_pages_text[:900]).upper())
    flat = re.sub(r"\s+", " ", first_pages_text)
    meta = {}
    acuerdo = ACUERDO_RE.search(first_pages_text)
    resolucion = RESOLUCION_RE.search(flat[:900])
    draft_acuerdo = DRAFT_ACUERDO_RE.search(flat[:900])
    decreto_file = DECRETO_FILE_RE.search(file_name)
    if "MEMORIA JUSTIFICATIVA" in head:
        meta["doc_type"] = "memoria_justificativa"
        meta["document_status"] = "proyecto" if "PROYECTO" in head else ""
        meta["issuer"] = ANH_ISSUER
    elif "ANEXO TECNICO" in head or "ANEXO_TECNICO" in strip_accents(file_name.upper()):
        meta["doc_type"] = "anexo_tecnico"
        meta["issuer"] = ANH_ISSUER
        meta["issue_date"] = parse_date(flat[:900].replace(",", " "))
    elif resolucion:
        meta["doc_type"] = "resolucion"
        number, date_text = resolucion.groups()
        if re.fullmatch(r"\d+", number):
            meta["number"] = number
            meta["issue_date"] = numeric_date(date_text) or parse_date(flat[:900])
            year = meta["issue_date"][:4] if meta["issue_date"] else ""
            meta["regulation"] = f"Resolución No. {number}" + (f" de {year}" if year else "")
        else:
            meta["document_status"] = "proyecto"
        meta["issuer"] = ANH_ISSUER
    elif decreto_file or re.search(r"\bDECRETO\s+(NUMERO|No)", head):
        meta["doc_type"] = "decreto"
        if decreto_file:
            number, day, month, year = decreto_file.groups()
            meta["number"] = number
            meta["regulation"] = f"Decreto {number} de {year}"
            month_number = EN_MONTHS.get(month.lower()[:3]) or MONTHS.get(strip_accents(month.lower()))
            if month_number:
                meta["issue_date"] = f"{int(year):04d}-{month_number:02d}-{int(day):02d}"
        meta["issuer"] = "Ministerio de Minas y Energía"
    elif re.search(r"\bAVISO\b", head) and "CONTRATO DE" not in head:
        meta["doc_type"] = "aviso"
        meta["issue_date"] = parse_date(flat[:900])
        meta["issuer"] = ANH_ISSUER
    elif "CONTRATO DE" in head and not acuerdo:
        meta["doc_type"] = "contrato"
        if "EVALUACION TECNICA" in upper:
            meta["contract_type"] = "TEA"
            meta["contract_type_name"] = "Contrato de Evaluación Técnica"
        elif "EXPLORACION Y PRODUCCION" in upper:
            meta["contract_type"] = "E&P"
            meta["contract_type_name"] = "Contrato de Exploración y Producción de Hidrocarburos"
        stop = re.compile(r"^(CONTRATISTA|FECHA|DOCUMENTOS|Los contratantes)", re.I)
        area_text = value_after(re.compile(r"^[AÁ]REA\s*[:;]", re.I), lines, stop)
        area = AREA_RE.search(area_text) or AREA_RE.search(file_name.replace("_", " "))
        if area:
            prefix = area.group(1).upper()
            meta["area"] = f"{prefix} {re.sub(r'\s+', '', area.group(2))}"
            meta["basin"] = BASINS[prefix]
        contractor = value_after(re.compile(r"^CONTRATISTA\s*[:;]", re.I), lines,
                                 re.compile(r"^(FECHA|DOCUMENTOS|Los contratantes)", re.I))
        if contractor:
            meta["contractor"] = canonical_contractor(contractor)
            meta["contractor_raw"] = re.sub(r"\s+", " ", contractor)
        date_text = value_after(re.compile(r"^FECHA DE FIRMA\s*[:;]", re.I), lines,
                                re.compile(r"^(DOCUMENTOS|Los contratantes)", re.I))
        meta["signing_date"] = parse_date(date_text or first_pages_text)
        meta["counterparty"] = "Agencia Nacional de Hidrocarburos (ANH)"
    elif acuerdo:
        meta["doc_type"] = "anexo_acuerdo" if "ANEXO" in strip_accents(file_name.upper()) else "acuerdo"
        meta["regulation"] = f"Acuerdo No. {int(acuerdo.group(1)):02d} de {acuerdo.group(2)}"
        meta["issuer"] = "Consejo Directivo de la Agencia Nacional de Hidrocarburos (ANH)"
    elif draft_acuerdo:
        meta["doc_type"] = "acuerdo"
        meta["document_status"] = "proyecto"
        meta["issuer"] = "Consejo Directivo de la Agencia Nacional de Hidrocarburos (ANH)"
    subject = SUBJECT_RE.search(flat[:3000])
    if subject:
        meta["subject"] = re.sub(r"\s+", " ", subject.group(1)).strip()
    return {k: v for k, v in meta.items() if v}


ANNEX_NUMBER_RE = re.compile(r"^(ANEXO|Anexo)\s*\d{1,2}$")
WRAPPED_ARTICLE_RE = re.compile(rf"^(ART[IÍ]CULO|Art[ií]culo|CL[AÁ]USULA|Cl[aá]usula)\s+{ARTICLE_NUMBER}")


def legal_heading(text, n_lines):
    if ANNEX_NUMBER_RE.match(text):
        return 2
    for pattern, level in STRUCTURE_ONLY:
        if n_lines <= 2 and pattern.match(text):
            return level
    if n_lines > 2 or len(text) > MAX_HEADING_CHARS or TOC_ENTRY_RE.search(text):
        return None
    for pattern, level in HEADING_PATTERNS:
        if pattern.match(text):
            return level
    return None


def wrapped_article(text):
    return bool(WRAPPED_ARTICLE_RE.match(text)) and ":" not in text and not text.endswith(".")


def split_inline_heading(text):
    match = INLINE_HEADING_RE.match(text)
    if not match:
        return None
    return match.group(1).strip(), (match.group(2) or "").strip()
