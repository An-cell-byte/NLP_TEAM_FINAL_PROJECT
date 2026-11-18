"""Clasificador clásico (TF-IDF) y contextual (MiniLM) con la misma cabeza y la misma rejilla.

El clásico es `make_baseline` de apoyo_pln (TF-IDF de unigramas y bigramas con
regresión logística). El contextual sustituye solo la representación: embeddings
de MiniLM congelados y la misma regresión logística. Ambos eligen C con validación.
"""
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, log_loss
from sklearn.pipeline import Pipeline

from .datos import SEED, normalize

GRID_C = [0.1, 1.0, 10.0, 100.0]
# El clásico también prueba n-gramas de caracteres (make_baseline admite `analyzer`):
# se le da su mejor oportunidad para que la comparación no lo perjudique.
CLASSIC_FEATURES = {"palabras_1-2": ("word", (1, 2)), "caracteres_2-5": ("char_wb", (2, 5))}


def _head(C):
    return LogisticRegression(C=C, max_iter=2000, random_state=SEED)


class ClassicClassifier:
    kind = "clasico"

    def __init__(self, C=2.0, features="palabras_1-2"):
        self.C, self.features = C, features
        analyzer, ngrams = CLASSIC_FEATURES[features]
        self.pipe = Pipeline([("tfidf", TfidfVectorizer(analyzer=analyzer, ngram_range=ngrams)),
                              ("classifier", _head(C))])

    def fit(self, texts, labels):
        self.pipe.fit([normalize(t) for t in texts], list(labels))
        return self

    @property
    def classes_(self):
        return self.pipe.classes_

    def predict_proba(self, texts):
        return self.pipe.predict_proba([normalize(t) for t in texts])

    def predict(self, texts):
        return self.classes_[self.predict_proba(texts).argmax(1)]

    def describe(self):
        return f"TF-IDF ({self.features}) + regresión logística, C={self.C}"


class ContextualClassifier:
    kind = "contextual"

    def __init__(self, encoder, C=2.0):
        self.encoder, self.C = encoder, C
        self.head = _head(C)

    def fit(self, texts, labels):
        self.head.fit(self.encoder.encode([normalize(t) for t in texts]), list(labels))
        return self

    @property
    def classes_(self):
        return self.head.classes_

    def predict_proba(self, texts):
        return self.head.predict_proba(self.encoder.encode([normalize(t) for t in texts]))

    def predict(self, texts):
        return self.classes_[self.predict_proba(texts).argmax(1)]

    def describe(self):
        return f"MiniLM multilingüe congelado + regresión logística, C={self.C}"


def build(kind, C, encoder=None, features="palabras_1-2"):
    return ClassicClassifier(C, features) if kind == "clasico" else ContextualClassifier(encoder, C)


def grid_search(kind, train, validation, encoder=None, grid=GRID_C):
    """Ajusta con train y evalúa en validación. Criterio: macro-F1, después log-loss y C menor."""
    rows = []
    variants = list(CLASSIC_FEATURES) if kind == "clasico" else ["minilm"]
    for features, C in [(f, c) for f in variants for c in grid]:
        model = build(kind, C, encoder, features)
        start = time.perf_counter()
        model.fit(train.text, train.label)
        fit_s = time.perf_counter() - start
        proba = model.predict_proba(validation.text)
        pred = model.classes_[proba.argmax(1)]
        rows.append({"modelo": kind, "representacion": features, "C": C,
                     "macro_f1_val": f1_score(validation.label, pred, average="macro", zero_division=0),
                     "log_loss_val": log_loss(validation.label, proba, labels=model.classes_),
                     "segundos_ajuste": fit_s})
    best = max(rows, key=lambda r: (round(r["macro_f1_val"], 6), -r["log_loss_val"], -r["C"]))
    return rows, best


def choose_model(best_by_kind):
    """Mismo criterio entre modelos: macro-F1 de validación y, si empatan, menor log-loss."""
    return max(best_by_kind.values(), key=lambda r: (round(r["macro_f1_val"], 6), -r["log_loss_val"]))


def timed_predict(model, texts, repeats=3):
    """Latencia media por texto (s), sin la caché de embeddings para el contextual."""
    texts = list(texts)
    times = []
    for _ in range(repeats):
        if hasattr(model, "encoder"):
            model.encoder._cache.clear()
        start = time.perf_counter()
        model.predict(texts)
        times.append((time.perf_counter() - start) / len(texts))
    return float(np.median(times))
