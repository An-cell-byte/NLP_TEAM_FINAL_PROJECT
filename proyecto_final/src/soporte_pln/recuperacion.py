"""Búsqueda de pasajes, puerta de evidencia y extracción de la respuesta.

La puerta sigue la idea del demo de clase (core.evidence_check): una respuesta
solo se emite si el pasaje cubre los términos informativos de la consulta.
"""
import re
import unicodedata

import numpy as np
from nltk.stem.snowball import SpanishStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STEMMER = SpanishStemmer()

# Palabras funcionales y verbos de petición; no aportan evidencia.
STOP_WORDS = frozenset("""
a al algo alguna alguno algunos ante como con contra cual cuales cuando cuanto cuanta cuantos cuantas
de del desde donde durante el ella ellas ellos en entre es esta estas este estos esto eso ese esa la las
le les lo los me mi mis o para por que quien se si su sus te tu tus un una uno unas unos y yo ya muy mas
tambien solo sobre tras despues antes porque pero aunque nos hasta todavia hay
puedo puede pueden quiero necesito saber dime favor tiene tienen tengo debe debo deben
cada son ser soy fue ha han haber he hemos sea estar estoy esta estan hace hacer hago
podria podemos pueda sirve significa
""".split())

# Fórmulas de cortesía y plantillas del corpus de solicitudes (no describen el problema).
COURTESY = [r"buen(?:os|as)? d[ií]as?", r"buenas tardes", r"¿?me pueden orientar\??",
            r"ya reinici[eé] y sigue igual", r"urge tantito", r"por favor", r"gracias", r"\bhola\b"]


def plain(text):
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def strip_courtesy(text):
    for pattern in COURTESY:
        text = re.sub(pattern, " ", text, flags=re.I)
    return text


def tokens(text):
    return re.findall(r"[^\W_]+", plain(text), flags=re.UNICODE)


def stem(token):
    return token if token.isdigit() or token in {"no", "ni", "nunca"} else STEMMER.stem(token)


def content_terms(text):
    """Términos informativos de la consulta: sin cortesía ni palabras funcionales."""
    return sorted({t for t in tokens(strip_courtesy(text)) if t not in STOP_WORDS and len(t) > 1})


def stems(text):
    return {stem(t) for t in tokens(text)}


# ---------------------------------------------------------------- recuperadores
class TfidfRetriever:
    name = "tfidf"

    def __init__(self, chunks):
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(strip_accents="unicode", lowercase=True,
                                          stop_words=sorted(STOP_WORDS), ngram_range=(1, 2),
                                          sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([c.indexable() for c in chunks])

    def scores(self, query):
        return cosine_similarity(self.vectorizer.transform([strip_courtesy(query)]), self.matrix)[0]


class SemanticRetriever:
    name = "semantico"

    def __init__(self, chunks, encoder):
        self.chunks, self.encoder = chunks, encoder
        self.matrix = encoder.encode([c.indexable() for c in chunks])

    def scores(self, query):
        return self.matrix @ self.encoder.encode([strip_courtesy(query)])[0]


class HybridRetriever:
    """Combinación lineal de cosenos: alpha·TF-IDF + (1-alpha)·MiniLM."""
    name = "hibrido"

    def __init__(self, chunks, encoder, alpha=0.5):
        self.chunks, self.alpha = chunks, alpha
        self.lexical = TfidfRetriever(chunks)
        self.semantic = SemanticRetriever(chunks, encoder)

    def scores(self, query):
        return self.alpha * self.lexical.scores(query) + (1 - self.alpha) * self.semantic.scores(query)


def make_retriever(name, chunks, encoder=None, alpha=0.5):
    if name == "tfidf":
        return TfidfRetriever(chunks)
    if name == "semantico":
        return SemanticRetriever(chunks, encoder)
    if name == "hibrido":
        return HybridRetriever(chunks, encoder, alpha)
    raise ValueError(f"Recuperador desconocido: {name}")


def search(retriever, query, categories=None, k=5):
    """Ranking estable de los k pasajes con mayor puntuación, opcionalmente filtrado por categoría."""
    if not query.strip() or not 1 <= k <= 50:
        raise ValueError("Consulta vacía o k fuera de 1-50")
    scores = retriever.scores(query)
    allowed = [i for i, c in enumerate(retriever.chunks) if categories is None or c.categoria in categories]
    order = sorted(allowed, key=lambda i: (-scores[i], i))[:k]
    return [{"rank": r, "chunk": retriever.chunks[i], "score": float(scores[i])} for r, i in enumerate(order, 1)]


# ---------------------------------------------------------- puerta de evidencia
class EvidenceGate:
    """Acepta un pasaje si su puntuación supera tau y cubre los términos de la consulta.

    min_coverage: fracción mínima de términos informativos presentes (por raíz) en el pasaje.
    oov_veto: si un término no aparece en NINGÚN pasaje del corpus, no hay evidencia posible
              para esa parte de la pregunta y el sistema se abstiene.
    synonyms: equivalencias declaradas del dominio (término de usuario -> término del corpus).
    No es una prueba de implicación lógica: es un filtro conservador y auditable.
    """

    def __init__(self, chunks, tau=0.1, min_coverage=1.0, oov_veto=False, synonyms=None):
        if not 0 <= min_coverage <= 1:
            raise ValueError("min_coverage fuera de [0, 1]")
        self.tau, self.min_coverage, self.oov_veto = tau, min_coverage, oov_veto
        self.synonyms = {plain(k): plain(v) for k, v in (synonyms or {}).items()}
        self.vocabulary = set().union(*(stems(c.indexable()) for c in chunks))
        self._chunk_stems = {c.id: stems(c.indexable()) for c in chunks}

    def keys(self, term):
        alt = self.synonyms.get(term)
        return {stem(term)} | ({stem(w) for w in alt.split()} if alt else set())

    def check(self, query, hit):
        terms = content_terms(query)
        available = self._chunk_stems[hit["chunk"].id]
        missing = [t for t in terms if not self.keys(t) & available]
        unknown = [t for t in terms if not self.keys(t) & self.vocabulary]
        coverage = (len(terms) - len(missing)) / len(terms) if terms else 0.0
        if not terms:
            reason = "sin_terminos_informativos"
        elif self.oov_veto and unknown:
            reason = "termino_desconocido_en_corpus"
        elif coverage < self.min_coverage:
            reason = "cobertura_insuficiente"
        elif hit["score"] < self.tau:
            reason = "similitud_insuficiente"
        else:
            reason = "evidencia_suficiente"
        return {"aceptado": reason == "evidencia_suficiente", "motivo": reason, "terminos": terms,
                "faltantes": missing, "desconocidos": unknown, "cobertura": round(coverage, 4),
                "score": round(hit["score"], 4)}


SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ«¿¡0-9])")


def extract_answer(query, chunk, max_sentences=2):
    """Respuesta extractiva: las oraciones del pasaje que más términos de la consulta comparten.

    Se copian literalmente y en su orden original; no se genera texto nuevo.
    """
    sentences = SENTENCE.split(chunk.texto)
    wanted = {stem(t) for t in content_terms(query)}
    overlap = [len(wanted & stems(s)) for s in sentences]
    best = sorted(range(len(sentences)), key=lambda i: (-overlap[i], i))[:max_sentences]
    chosen = [sentences[i] for i in sorted(best) if overlap[i] > 0] or sentences[:1]
    return " ".join(chosen)
