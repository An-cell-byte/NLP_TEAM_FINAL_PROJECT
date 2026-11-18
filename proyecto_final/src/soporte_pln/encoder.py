"""Encoder contextual MiniLM multilingüe en CPU, siempre desde una carpeta local."""
from pathlib import Path
import os

import numpy as np

from .datos import ROOT

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Revisión fijada (la misma del demo de clase) para que los vectores no cambien.
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
DEFAULT_PATH = ROOT / "models" / "minilm"


def model_path():
    return Path(os.environ.get("SOPORTE_MODELO", DEFAULT_PATH))


class Encoder:
    """Envuelve SentenceTransformer con una caché en memoria por texto."""

    def __init__(self, path=None):
        path = Path(path or model_path())
        if not (path / "modules.json").is_file():
            raise FileNotFoundError(
                f"No se encontró el modelo en {path}. Ejecuta: python scripts/descargar_modelo.py")
        from sentence_transformers import SentenceTransformer
        import torch
        torch.manual_seed(42)
        torch.set_num_threads(2)
        self.model = SentenceTransformer(str(path), device="cpu", local_files_only=True)
        self.path = path
        self._cache = {}

    def encode(self, texts):
        texts = list(texts)
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            vectors = self.model.encode(missing, batch_size=32, normalize_embeddings=True,
                                        show_progress_bar=False, convert_to_numpy=True)
            self._cache.update(zip(missing, vectors))
        return np.vstack([self._cache[t] for t in texts])
