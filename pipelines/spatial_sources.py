import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import psycopg

from config.settings import ROOT
from spatial_sql import STAGE_COPY, STAGE_TABLE, STAGE_TO_RAW, VMM

SOURCES = ROOT / "ColBasins"
WELLS = SOURCES / "Banco_de_infromacion_Petrolera_pozos.geojson"
SEISMIC_2D = SOURCES / "SimicaPetrolera2D.geojson"
SEISMIC_3D = SOURCES / "Banco_de_Información_Petrolera_Sísmica_3D.geojson"
FAULTS = SOURCES / "Atlas_Fallas_Geologicas.geojson"
Feature = tuple[int, dict, dict | None]


def sha256_of(path: Path) -> str:

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def basin_of(props: dict, key: str) -> bool:

    return (props.get(key) or "").strip() == VMM


def read_features(path: Path, basin_key: str | None) -> list[Feature]:

    data = json.loads(path.read_text(encoding="utf-8"))
    features = []
    for feature in data["features"]:
        props = feature["properties"] or {}
        if basin_key is None or basin_of(props, basin_key):
            features.append((int(props["FID"]), props, feature["geometry"]))
    return features


def stream_2d(path: Path) -> Iterator[Feature]:
    """One feature per line; only lines naming the VMM are parsed."""
    marker = VMM.encode("utf-8")
    with path.open("rb") as handle:
        for raw in handle:
            if marker not in raw:
                continue
            text = raw.decode("utf-8").strip().rstrip(",")
            feature = json.loads(text)
            props = feature["properties"] or {}
            if basin_of(props, "CUENCA"):
                yield int(props["FID"]), props, feature["geometry"]


def copy_stage(conn: psycopg.Connection, features: list[Feature]) -> None:

    conn.execute(STAGE_TABLE)
    with conn.cursor() as cur:
        with cur.copy(STAGE_COPY) as copy:
            for fid, props, geometry in features:
                geojson = json.dumps(geometry) if geometry else None
                copy.write_row((fid, json.dumps(props, ensure_ascii=False),
                                geojson))


def load_raw(conn: psycopg.Connection, table: str,
             features: list[Feature]) -> None:

    with conn.transaction():
        conn.execute(f"TRUNCATE raw.{table}")
        copy_stage(conn, features)
        conn.execute(STAGE_TO_RAW.format(table=table))
