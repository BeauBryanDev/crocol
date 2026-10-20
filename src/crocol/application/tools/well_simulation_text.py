from typing import Any

from config.settings import WELLSIM_LABEL

MODEL = (
    f"Simulación numérica {WELLSIM_LABEL} con los parámetros de pozo que "
    "envió el usuario. Modelo: flujo monofásico de petróleo subsaturado en "
    "un cilindro radial r–z (malla logarítmica en r), esquema implícito en "
    "el tiempo, PVT constante; no modela agua, gas libre ni curvas de "
    "permeabilidad relativa, y el levantamiento artificial no está incluido."
)
RULE = (
    "Regla de la recomendación: la tasa recomendada es la menor tasa cuyo Np "
    "al horizonte queda dentro de la tolerancia del mejor caso; por encima "
    "de ella, más tasa no recupera más petróleo, solo adelanta la "
    "producción y aumenta el abatimiento."
)
FLOOR_SOURCES = {
    "atmospheric": "la presión atmosférica",
    "bubble_point": "el punto de burbuja",
    "pwf_min": "la pwf mínima operativa",
    "max_drawdown": "el abatimiento máximo",
}
CONTROLS = {
    "rate": ("tasa", "STB/d"),
    "bhp": ("presión de fondo fluyente", "psi"),
}


def amount(value: float | None, fmt: str, unit: str = "") -> str:
    if value is None:
        return "sin límite"
    text = format(value, fmt)
    return f"{text} {unit}".strip()


def well_lines(well: dict[str, Any]) -> list[str]:
    ct = well["co"] + well["cf"]
    return [
        f"Yacimiento: radio de drenaje {well['re']:g} ft, espesor "
        f"{well['h']:g} ft, kh {well['kh']:g} md, kv/kh {well['kv_kh']:g}, "
        f"porosidad {well['phi']:g}, compresibilidad total {ct:.3g} 1/psi.",
        f"Petróleo: viscosidad {well['mu']:g} cP, Bo {well['Bo']:g} rb/STB, "
        f"densidad {well['rho']:g} lb/ft3, kro {well['kro']:g}; presión "
        f"inicial {well['pi']:g} psi, punto de burbuja {well['pb']:g} psi.",
        f"Pozo: radio {well['rw']:g} ft, daño (skin) {well['skin']:g}, "
        f"cañoneo de {well['perf_top']:g} a {well['perf_bot']:g} ft; malla "
        f"{well['Nr']} x {well['Nz']} celdas, {well['Nt']} pasos en "
        f"{well['T']:g} días.",
    ]


def constraint_line(inputs: dict[str, Any]) -> str:
    return (
        f"Restricciones: piso de pwf {inputs['pwf_floor_psi']:.0f} psi "
        f"(fijado por {FLOOR_SOURCES[inputs['floor_source']]}), tasa máxima "
        f"{amount(inputs['q_max_stb_d'], ',.0f', 'STB/d')}, tasa de "
        f"abandono {amount(inputs['q_abandon_stb_d'], ',.0f', 'STB/d')}, "
        f"abatimiento máximo "
        f"{amount(inputs['max_drawdown_psi'], ',.0f', 'psi')}, tasa de "
        f"descuento anual {inputs['discount_rate_annual']:.0%}.")


def case_line(label: str, row: dict[str, Any] | None) -> str:
    if row is None:
        return f"{label}: no hay caso válido."
    name, unit = CONTROLS[row["control"]]
    plateau = row["plateau_days"]
    plateau_text = "-" if plateau is None else f"{plateau:.0f} días"
    validity = "válido" if row["valid"] else "NO válido (bajo pb)"
    return (
        f"{label}: {name} {row['target']:,.1f} {unit}; Np "
        f"{row['np_stb']:,.0f} STB; factor de recobro {row['rf']:.2%}; "
        f"meseta {plateau_text}; Np descontado "
        f"{row['discounted_np_stb']:,.0f} STB; pwf final "
        f"{row['pwf_final_psi']:,.0f} psi; restricción activa "
        f"{row['limit']}; {validity}.")


def render_sweep(result: dict[str, Any]) -> str:
    inputs, bounds = result["inputs"], result["bounds"]
    lines = [MODEL, *well_lines(result["well"]), constraint_line(inputs)]
    lines.append(
        f"Objetivo: maximizar el petróleo acumulado Np a "
        f"{inputs['horizon_days']:g} días; {len(result['rows'])} casos.")
    lines.append(
        f"Límite de depleción por balance de materia: "
        f"{bounds['np_depletion_limit_stb']:,.0f} STB (factor de recobro "
        f"{bounds['rf_depletion_limit']:.2%}).")
    lines.append(case_line("Tasa recomendada", result["recommended_rate"]))
    lines.append(case_line("Mejor tasa", result["best_rate"]))
    lines.append(case_line("Mejor tasa descontada",
                           result["best_discounted_rate"]))
    lines.append(case_line("Mejor presión de fondo", result["best_bhp"]))
    lines.append(RULE)
    lines.append("Notas del simulador:")
    lines.extend(f"- {note}" for note in result["notes"])
    lines.append("Supuestos del modelo:")
    lines.extend(f"- {item}" for item in result["assumptions"])
    lines.append("Tabla de casos:")
    lines.append(result["table_markdown"])
    return "\n".join(lines)
