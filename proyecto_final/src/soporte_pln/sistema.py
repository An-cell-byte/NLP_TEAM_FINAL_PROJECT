"""Recorrido completo: validar -> proteger datos -> clasificar -> buscar -> verificar -> responder."""
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

from .datos import OOD, normalize, redact
from .recuperacion import EvidenceGate, extract_answer, make_retriever, search

MAX_CHARS = 1000
MSG_ABSTENCION = "No encuentro evidencia suficiente en la base de conocimiento para responder. {destino}"
DESTINOS = {"cola": "Tu solicitud se canaliza a la cola de {label} para que la atienda una persona.",
            "otra_area": "Parece fuera del alcance de la mesa de ayuda (acceso, conectividad, pagos y software); "
                         "consulta con el área correspondiente.",
            "revision": "La categoría no es clara; tu solicitud pasa a revisión general de la mesa de ayuda."}
MSG_INVALIDA = "La solicitud no es válida: {motivo}."


@dataclass
class Config:
    retriever: str = "hibrido"
    alpha: float = 0.5
    tau: float = 0.1
    min_coverage: float = 1.0
    oov_veto: bool = False
    synonyms: dict = field(default_factory=dict)
    routing: bool = True          # filtrar la búsqueda con la categoría predicha
    gate: bool = True             # exigir evidencia antes de responder
    route_min_conf: float = 0.5   # por debajo, se busca en toda la base
    k: int = 3                    # candidatos que revisa la puerta

    def as_dict(self):
        return asdict(self)


def validate_input(text):
    """Devuelve (texto_normalizado, None) o (None, motivo)."""
    if not isinstance(text, str):
        return None, f"se esperaba texto y se recibió {type(text).__name__}"
    text = normalize(text)
    if not text:
        return None, "la solicitud está vacía"
    if len(text) > MAX_CHARS:
        return None, f"supera {MAX_CHARS} caracteres"
    if not re.search(r"[^\W\d_]{2,}", text):
        return None, "no contiene palabras"
    return text, None


class SistemaSoporte:
    def __init__(self, classifier, chunks, encoder=None, config=None, registro=None):
        self.classifier, self.chunks = classifier, chunks
        self.config = config or Config()
        self.retriever = make_retriever(self.config.retriever, chunks, encoder, self.config.alpha)
        self.gate = EvidenceGate(chunks, self.config.tau, self.config.min_coverage,
                                 self.config.oov_veto, self.config.synonyms)
        self.registro = Path(registro) if registro else None

    def categories_for(self, label, confidence):
        # Solo se filtra con una categoría de soporte segura. Si la etiqueta es
        # «fuera de alcance» o la confianza es baja, se busca en toda la base y
        # la puerta de evidencia decide: así un error del clasificador no oculta
        # un pasaje que sí responde.
        if not self.config.routing or label == OOD or confidence < self.config.route_min_conf:
            return None
        return {label, "general"}

    def route(self, label, confidence):
        """Decisión de canalización que apoya el clasificador (la usa el agente al escalar)."""
        if confidence < self.config.route_min_conf:
            return "revision", DESTINOS["revision"]
        if label == OOD:
            return "otra_area", DESTINOS["otra_area"]
        return f"cola_{label}", DESTINOS["cola"].format(label=label)

    def responder(self, texto):
        clean, problem = validate_input(texto)
        if problem:
            result = {"estado": "entrada_invalida", "mensaje": MSG_INVALIDA.format(motivo=problem),
                      "motivo": problem, "clasificacion": None, "busqueda": None, "respuesta": None}
            self._log(None, result)
            return result
        safe = redact(clean)
        proba = self.classifier.predict_proba([safe])[0]
        order = proba.argsort()[::-1]
        label, confidence = str(self.classifier.classes_[order[0]]), float(proba[order[0]])
        destino, destino_msg = self.route(label, confidence)
        clasificacion = {"etiqueta": label, "confianza": round(confidence, 4), "canalizacion": destino,
                         "probabilidades": {str(c): round(float(p), 4) for c, p in zip(self.classifier.classes_, proba)}}
        categories = self.categories_for(label, confidence)
        hits = search(self.retriever, safe, categories, k=self.config.k)
        ranking, accepted = [], None
        for hit in hits:
            decision = self.gate.check(safe, hit) if self.config.gate else {"aceptado": True, "motivo": "sin_puerta"}
            c = hit["chunk"]
            ranking.append({"rank": hit["rank"], "id": c.id, "documento": c.doc_id, "titulo": c.titulo,
                            "seccion": c.seccion, "score": round(hit["score"], 4), **decision})
            if decision["aceptado"] and accepted is None:
                accepted = hit
        busqueda = {"recuperador": self.config.retriever,
                    "categorias": sorted(categories) if categories else "todas", "ranking": ranking}
        if accepted is None:
            result = {"estado": "abstencion", "mensaje": MSG_ABSTENCION.format(destino=destino_msg),
                      "motivo": ranking[0]["motivo"],
                      "clasificacion": clasificacion, "busqueda": busqueda, "respuesta": None, "consulta_protegida": safe}
        else:
            c = accepted["chunk"]
            texto_respuesta = extract_answer(safe, c)
            result = {"estado": "respondida", "mensaje": texto_respuesta, "motivo": "evidencia_suficiente",
                      "clasificacion": clasificacion, "busqueda": busqueda, "consulta_protegida": safe,
                      "respuesta": {"tipo": "extractiva", "texto": texto_respuesta, "pasaje": c.texto,
                                    "fuente": {"id": c.id, "documento": c.doc_id, "archivo": c.archivo,
                                               "titulo": c.titulo, "seccion": c.seccion,
                                               "rank": accepted["rank"], "score": round(accepted["score"], 4)}}}
        self._log(safe, result)
        return result

    def _log(self, safe, result):
        """Registro mínimo: sin texto de la consulta, solo una huella y la decisión."""
        if not self.registro:
            return
        fuente = result["respuesta"]["fuente"]["id"] if result.get("respuesta") else None
        entry = {"fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "huella": hashlib.sha256(safe.encode()).hexdigest()[:12] if safe else None,
                 "caracteres": len(safe) if safe else 0, "estado": result["estado"],
                 "etiqueta": (result.get("clasificacion") or {}).get("etiqueta"), "fuente": fuente}
        self.registro.parent.mkdir(parents=True, exist_ok=True)
        with self.registro.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def format_result(result):
    """Texto legible para la terminal o el notebook."""
    lines = [f"Estado: {result['estado']}"]
    if result["clasificacion"]:
        cl = result["clasificacion"]
        lines.append(f"Clasificación: {cl['etiqueta']} (confianza {cl['confianza']:.2f}) -> {cl['canalizacion']}")
    if result["busqueda"]:
        lines.append(f"Búsqueda ({result['busqueda']['recuperador']}, categorías: {result['busqueda']['categorias']}):")
        for r in result["busqueda"]["ranking"]:
            mark = "✔" if r["aceptado"] else "✘"
            lines.append(f"  {r['rank']}. {mark} {r['id']} «{r['seccion']}» score={r['score']:.3f} · {r['motivo']}")
    lines.append(f"Respuesta: {result['mensaje']}")
    if result.get("respuesta"):
        f = result["respuesta"]["fuente"]
        lines.append(f"Fuente: {f['documento']} «{f['titulo']}» › «{f['seccion']}» ({f['archivo']}, {f['id']})")
        lines.append("Tipo de respuesta: extractiva (oraciones copiadas literalmente del pasaje citado)")
    return "\n".join(lines)
