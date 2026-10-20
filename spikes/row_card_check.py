import json
from pathlib import Path

from crocol.application.tools.text_search import text_search
from crocol.infrastructure.vectors.chroma_store import ChromaVectorStore

STORE = ChromaVectorStore()
REPORT = Path(__file__).with_name("row_card_check_report.json")
TOP = 10
NUMERIC_MAX_RANK = 5
CONCEPTUAL_MAX_CARDS = 1

CONCEPTUAL = [
    "¿Cuál es el ambiente de depósito de la Formación Mugrosa?",
    "What controls the thermal maturity of the La Luna Formation in the "
    "Middle Magdalena Valley?",
    "¿Cómo evolucionó tectónicamente la cuenca del Valle Medio del "
    "Magdalena durante el Cenozoico?",
    "¿Cuáles son las rocas generadoras del sistema petrolífero del Valle "
    "Medio del Magdalena?",
    "Describe the lithofacies and depositional environment of the Galembo "
    "Member.",
]

NUMERIC = [
    (
        "¿Cuál es el porcentaje de metano del gas en el pozo Llanito 91?",
        "Dialnet-HabitatGeologicoGeoquimicaDeGasesYProspectividadDe-"
        "10384272.pdf",
        ["Llanito 91", "77,35"],
    ),
    (
        "What is the matrix porosity of the Tablazo limestones measured in "
        "the Crisol 1 well?",
        "VOLUMEN_11_MIDDLE-MAGDALENA_BASIN.pdf",
        ["Crisol 1"],
    ),
    (
        "¿Qué valor de resistividad del agua de formación (Rw) se usó en la "
        "evaluación petrofísica de La Luna?",
        "EVALUACION_PETROFISICA_VMM.pdf",
        ["Rw", "0.23"],
    ),
    (
        "What is the total gas content of La Luna canister sample QLL-40?",
        "sgcpubesp36201909.pdf",
        ["QLL", "6.56"],
    ),
    (
        "¿Cuál es el TOC y la Tmax de la Formación Tablazo según Martínez "
        "Alarcón?",
        "Tesis/Nicolas_Martinez_Alarcon_UIS_2023.pdf",
        ["Tablazo", "475"],
    ),
]

SCOPE = [
    (
        "¿Qué establece el contrato VMM 53 sobre el programa exploratorio "
        "mínimo?",
        "exact",
    ),
    (
        "¿Qué significa abandono de un pozo según el glosario de la ANH?",
        "conceptual",
    ),
]


def unfiltered(question: str, query_type: str = "conceptual") -> list[dict]:
    return STORE.search(question, query_type, limit=TOP)


def with_policy(question: str, query_type: str = "conceptual",
                corpus_scope: str = "core",
                chunk_policy: str = "prose_tables") -> list[dict]:
    return text_search(
        STORE,
        question,
        query_type,
        corpus_scope=corpus_scope,
        chunk_policy=chunk_policy,
        limit=TOP,
    )


def row_cards(rows: list[dict]) -> int:
    return sum(1 for r in rows if r["metadata"]["chunk_type"] == "table_row")


def answer_rank(rows: list[dict], source_path: str,
                needles: list[str]) -> int | None:
    for rank, row in enumerate(rows, 1):
        same_doc = row["metadata"]["source_path"] == source_path
        if same_doc and all(n in row["document"] for n in needles):
            return rank
    return None


def collections(rows: list[dict]) -> list[str]:
    return sorted({r["metadata"]["collection"] for r in rows})


def check_conceptual(report: dict) -> bool:
    ok = True
    print("conceptual: row cards in top 10 (old -> new)")
    for question in CONCEPTUAL:
        old = row_cards(unfiltered(question))
        new = row_cards(with_policy(question))
        ok = ok and new <= CONCEPTUAL_MAX_CARDS
        report["conceptual"].append({
            "question": question,
            "old": old,
            "new": new,
        })
        print(f"  {old:2d} -> {new:2d}  {question}")
    return ok


def check_numeric(report: dict) -> bool:
    ok = True
    print("numeric: row cards and rank of the answer chunk (old -> new)")
    for question, source_path, needles in NUMERIC:
        old_rows = unfiltered(question, "exact")
        new_rows = with_policy(question, "exact", chunk_policy="numeric")
        old_rank = answer_rank(old_rows, source_path, needles)
        new_rank = answer_rank(new_rows, source_path, needles)
        ok = ok and new_rank is not None and new_rank <= NUMERIC_MAX_RANK
        report["numeric"].append({
            "question": question,
            "old_cards": row_cards(old_rows),
            "new_cards": row_cards(new_rows),
            "old_rank": old_rank,
            "new_rank": new_rank,
        })
        print(f"  cards {row_cards(old_rows):2d} -> "
              f"{row_cards(new_rows):2d}  rank {old_rank} -> {new_rank}  "
              f"{question}")
    return ok


def check_scope(report: dict) -> bool:
    ok = True
    print("scope: collections in top 10 (core -> all)")
    for question, query_type in SCOPE:
        core = collections(with_policy(question, query_type, "core"))
        every = collections(with_policy(question, query_type, "all"))
        peripheral = any(c != "VMM_Basin" for c in every)
        ok = ok and core == ["VMM_Basin"] and peripheral
        report["scope"].append({
            "question": question,
            "core": core,
            "all": every,
        })
        print(f"  {core} -> {every}  {question}")
    return ok


def main() -> None:
    report: dict = {"conceptual": [], "numeric": [], "scope": []}
    conceptual = check_conceptual(report)
    numeric = check_numeric(report)
    scope = check_scope(report)
    report["passed"] = conceptual and numeric and scope

    text = json.dumps(report, ensure_ascii=False, indent=2)
    REPORT.write_text(text, encoding="utf-8")
    print(f"passed: {report['passed']}  ({REPORT.name})")


if __name__ == "__main__":
    main()
