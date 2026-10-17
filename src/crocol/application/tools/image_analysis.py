from crocol.domains.models.chunks import Chunk
from crocol.domains.models.cracks import CrackReport

CNN_CITATION = "MobileNetV2-UNet"
TOOL_DESCRIPTION = (
    "Herramienta: segmentación geológica de grietas. MobileNetV2-UNet es una "
    "red neuronal convolucional (codificador MobileNet-v2 y decodificador "
    "U-Net, 6,6 millones de parámetros) entrenada con el conjunto GeoCrack "
    "para separar los píxeles de grieta de la roca intacta. Sobre la máscara "
    "de grietas se miden densidad, dimensión fractal (conteo de cajas), "
    "orientación, número, longitud y ancho de las grietas."
)
NOTE = (
    "Nota: longitudes y anchos en píxeles; ángulos medidos en el marco de la "
    "imagen (0° horizontal, sentido antihorario), no rumbo ni buzamiento "
    "reales. La severidad es una clasificación heurística basada en densidad "
    "y dimensión fractal, no un estándar de ingeniería."
)


def angle_text(report: CrackReport) -> str:

    if not report.dominant_angles:
        return "sin dirección dominante"
    parts = []
    for angle, share in report.dominant_angles:
        parts.append(f"{angle}° ({round(share * 100)} %)")
    return ", ".join(parts)


def outputs_text(report: CrackReport) -> str:
    """The model's measurements as plain lines, for evidence and prompts."""
    return "\n".join([
        f"modelo: {report.model}; umbral: {report.threshold}",
        f"imagen analizada: {report.width_px} x {report.height_px} px "
        f"({report.tiles} recortes de 224 px)",
        f"densidad de grietas: {report.density_pct} %",
        f"dimensión fractal: {report.fractal_dimension} "
        f"(R² {report.fractal_r2})",
        f"severidad: {report.severity}",
        f"número de grietas: {report.crack_count}",
        f"longitud total: {report.total_length_px} px",
        f"ancho medio: {report.mean_width_px} px; ancho máximo: "
        f"{report.max_width_px} px",
        f"direcciones dominantes: {angle_text(report)}",
        f"confianza media del modelo: {report.mean_confidence}; píxeles "
        f"ambiguos: {report.ambiguous_pct} %",
    ])


def crack_chunk(report: CrackReport) -> Chunk:
    """Evidence passage with the CNN's measurements of the sent image."""
    text = "\n".join([
        TOOL_DESCRIPTION,
        "Resultados sobre la imagen enviada:",
        outputs_text(report),
        NOTE,
    ])
    return Chunk(
        chunk_id="vision-cnn",
        doc_id="vision-cnn",
        text=text,
        citation=CNN_CITATION,
        title="Segmentación de grietas MobileNetV2-UNet (GeoCrack)",
        collection="vision",
        doc_type="crack_model",
        chunk_type="vision",
        heading_path="geo crack segmentation",
    )


def interpretation_chunk(description: str, diagnosis: str, fluid_flow: str,
                         model: str) -> Chunk:
    """Evidence passage with the multimodal model's reading of the photo."""
    text = "\n".join([
        f"Interpretación visual de la imagen por {model} (IA, sin "
        "verificación de campo).",
        f"Descripción de la roca: {description}",
        f"Diagnóstico: {diagnosis}",
        f"Flujo de fluidos: {fluid_flow}",
    ])
    return Chunk(
        chunk_id="vision-interpretation",
        doc_id="vision-interpretation",
        text=text,
        citation=f"{model}, interpretación visual",
        title="Interpretación visual de la imagen",
        collection="vision",
        doc_type="visual_interpretation",
        chunk_type="vision",
        heading_path="visual interpretation",
    )
