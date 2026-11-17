"""Punto de partida de Qwerty para desarrollar E1 y E2."""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def rank_candidates(query, rows, mode, embed):
    """Ordena los fragmentos por coincidencia de palabras en la demostración."""
    if not rows:
        return []
    # E1. Implementa y compara las búsquedas semántica e híbrida.
    vectorizer = TfidfVectorizer(strip_accents='unicode', ngram_range=(1, 2))
    documents = vectorizer.fit_transform([row['text'] for row in rows])
    scores = cosine_similarity(vectorizer.transform([query]), documents)[0]
    order = np.argsort(-scores, kind='stable')
    return [
        {key: value for key, value in rows[index].items() if key != 'vector'}
        | {'lexical': float(scores[index]), 'semantic': None}
        for index in order
    ]


def produce_answer(query, hits, mode, *, variant=0):
    """Muestra el texto recuperado y la referencia de cada fragmento."""
    # E2. Desarrolla la síntesis con citas y comprueba cuándo falla.
    if not hits:
        return {
            'answer': 'No encontré esa información en tus documentos. ¿Puedes precisar la pregunta?',
            'abstained': True,
            'references': [],
            'generation': 'base_lexica',
        }
    references = [
        {key: hit.get(key) for key in ('id', 'document', 'page', 'version', 'text', 'location')}
        for hit in hits
    ]
    return {
        'answer': '\n\n'.join(dict.fromkeys(hit['text'] for hit in hits)),
        'abstained': False,
        'references': references,
        'generation': 'base_lexica',
    }
