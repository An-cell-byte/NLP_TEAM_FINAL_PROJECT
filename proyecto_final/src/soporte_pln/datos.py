"""Carga y validación de datos: solicitudes, base de conocimiento y consultas.

Las funciones de validación y normalización provienen de `apoyo_pln.py`
(Clases 7-10 y Actividad 3); se conservan las mismas reglas de partición.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import re
import unicodedata

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATOS = ROOT / "datos"
LABELS = ["acceso", "conectividad", "pagos", "software"]
OOD = "fuera_de_alcance"
LABELS_SISTEMA = LABELS + [OOD]
SEED = 42


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_splits(df):
    """Mismas reglas que apoyo_pln.validate_splits: sin fugas por familia ni por texto."""
    required = {"id", "text", "label", "family", "split"}
    if not required <= set(df):
        raise ValueError(f"Faltan columnas: {required - set(df)}")
    if df.id.duplicated().any() or df.text.isna().any():
        raise ValueError("IDs duplicados o textos ausentes")
    if df.groupby("family").split.nunique().max() > 1:
        raise ValueError("Fuga: una familia aparece en más de una partición")
    if df.groupby("text").split.nunique().max() > 1:
        raise ValueError("Fuga: texto idéntico en distintas particiones")
    if set(df.split) != {"train", "validation", "test"}:
        raise ValueError("Se requieren train, validation y test")
    return True


def load_requests(include_ood=True):
    """Solicitudes originales (IDs S###) y, si se pide, la clase fuera de alcance (F###)."""
    frames = [pd.read_csv(DATOS / "solicitudes.csv")]
    if include_ood:
        frames.append(pd.read_csv(DATOS / "fuera_de_alcance.csv"))
    df = pd.concat(frames, ignore_index=True)
    validate_splits(df)
    return df


def normalize(text):
    if not isinstance(text, str):
        raise TypeError("Se esperaba una cadena de texto")
    # Se conservan negación, acentos y signos con valor lingüístico.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


PII_PATTERNS = [
    ("[CORREO]", r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}"),
    ("[TARJETA]", r"\b(?:\d[ -]?){13,16}\b"),
    ("[TELEFONO]", r"(?<!\d)(?:\+?52[ -]?)?(?:\d[ -]?){10}(?!\d)"),
]


def redact(text):
    """Oculta correos, números de tarjeta y teléfonos antes de procesar o registrar."""
    for token, pattern in PII_PATTERNS:
        text = re.sub(pattern, token, text)
    return text


@dataclass(frozen=True)
class Chunk:
    id: str          # DOC-ID#sN, N = número de sección dentro del documento
    doc_id: str
    archivo: str
    titulo: str
    seccion: str
    categoria: str
    texto: str

    def indexable(self):
        # El título y el encabezado describen el tema del pasaje.
        return f"{self.titulo}. {self.seccion}. {self.texto}"

    def as_dict(self):
        return asdict(self)


def parse_document(path):
    raw = Path(path).read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, flags=re.S)
    if not match:
        raise ValueError(f"{path}: falta el encabezado de metadatos")
    meta = dict(line.split(": ", 1) for line in match.group(1).splitlines())
    for key in ("id", "titulo", "categoria", "licencia"):
        if key not in meta:
            raise ValueError(f"{path}: falta '{key}' en los metadatos")
    sections = re.split(r"^## ", match.group(2), flags=re.M)[1:]
    chunks = []
    for n, block in enumerate(sections, 1):
        heading, _, body = block.partition("\n")
        chunks.append(Chunk(id=f"{meta['id']}#s{n}", doc_id=meta["id"], archivo=Path(path).name,
                            titulo=meta["titulo"], seccion=heading.strip(), categoria=meta["categoria"],
                            texto=normalize(body)))
    return meta, chunks


def load_knowledge_base(folder=None):
    folder = Path(folder or DATOS / "base_conocimiento")
    docs, chunks = [], []
    for path in sorted(folder.glob("*.md")):
        meta, parts = parse_document(path)
        docs.append({**meta, "archivo": path.name, "secciones": len(parts)})
        chunks.extend(parts)
    if not chunks:
        raise ValueError("Base de conocimiento vacía")
    ids = [c.id for c in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs de fragmento duplicados")
    return docs, chunks


def load_queries(name):
    rows = json.loads((DATOS / f"consultas_{name}.json").read_text(encoding="utf-8"))
    for row in rows:
        if row["answerable"] != bool(row["relevant"]):
            raise ValueError(f"{row['id']}: 'answerable' no coincide con 'relevant'")
    return rows


def load_synonyms():
    """Equivalencias declaradas del dominio: {término del usuario: término del corpus}."""
    data = json.loads((DATOS / "sinonimos.json").read_text(encoding="utf-8"))
    return {k: v["corpus"] for k, v in data["equivalencias"].items()}
