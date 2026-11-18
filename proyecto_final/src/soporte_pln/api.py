"""Interfaz de una función: `responder(texto)`.

Reconstruye el sistema con la política congelada en resultados/politica.json:
mismo clasificador (entrenado solo con train), mismo recuperador y mismos umbrales.
"""
import json
from functools import lru_cache

from .clasificacion import build
from .datos import ROOT, load_knowledge_base, load_requests, sha256
from .sistema import Config, SistemaSoporte

POLITICA = ROOT / "resultados" / "politica.json"


def leer_politica(path=POLITICA):
    if not path.is_file():
        raise FileNotFoundError("Falta resultados/politica.json. Ejecuta: python scripts/evaluar.py")
    return json.loads(path.read_text(encoding="utf-8"))


def verificar_huellas(policy):
    """Lista de archivos que cambiaron desde que se congeló la política."""
    return [f for f, h in policy["huellas"].items() if not (ROOT / f).is_file() or sha256(ROOT / f) != h]


def cargar_sistema(registro=None, encoder=None, path=POLITICA):
    from .encoder import Encoder
    policy = leer_politica(path)
    encoder = encoder or Encoder()
    df = load_requests()
    train = df[df.split == "train"]
    cfg = policy["clasificador"]
    classifier = build(cfg["modelo"], cfg["C"], encoder, cfg.get("representacion", "palabras_1-2"))
    classifier.fit(train.text, train.label)
    _, chunks = load_knowledge_base()
    return SistemaSoporte(classifier, chunks, encoder, Config(**policy["config"]), registro)


@lru_cache(maxsize=1)
def _sistema():
    return cargar_sistema(registro=ROOT / "registros" / "consultas.jsonl")


def responder(texto):
    """Clasifica, busca y responde con fuente, o se abstiene. Devuelve un diccionario."""
    return _sistema().responder(texto)
