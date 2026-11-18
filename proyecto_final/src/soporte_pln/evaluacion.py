"""Métricas recalculadas a mano y contrastadas con scikit-learn."""
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score


def macro_f1_from_confusion(matrix):
    """F1 por clase = 2·TP / (2·TP + FP + FN); macro = promedio simple entre clases."""
    m = np.asarray(matrix, dtype=float)
    tp = np.diag(m)
    fp = m.sum(0) - tp
    fn = m.sum(1) - tp
    denom = 2 * tp + fp + fn
    per_class = np.divide(2 * tp, denom, out=np.zeros_like(tp), where=denom > 0)
    return float(per_class.mean()), per_class


def classification_metrics(y_true, y_pred, labels):
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    manual, per_class = macro_f1_from_confusion(cm)
    sk = f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    assert abs(manual - sk) < 1e-12, "El F1 manual no coincide con scikit-learn"
    return {"accuracy": accuracy_score(y_true, y_pred), "macro_f1": manual,
            "f1_por_clase": dict(zip(labels, per_class.round(4).tolist())),
            "confusion": cm.tolist(), "labels": list(labels), "n": len(y_true)}


def bootstrap_macro_f1(y_true, y_pred, labels, n=2000, seed=42):
    """Intervalo percentil 95 % remuestreando ejemplos de prueba."""
    rng = np.random.default_rng(seed)
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    values = []
    for _ in range(n):
        idx = rng.integers(0, len(y_true), len(y_true))
        values.append(f1_score(y_true[idx], y_pred[idx], labels=labels, average="macro", zero_division=0))
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def ranking_metrics(ranked_ids, relevant, k_recall=3, k_mrr=5):
    """Recall@3 = relevantes en el top 3 / relevantes. MRR@5 = 1/rango del primer relevante."""
    relevant = set(relevant)
    if not relevant:
        return {"recall_at_3": None, "mrr_at_5": None}
    recall = len(set(ranked_ids[:k_recall]) & relevant) / len(relevant)
    rr = next((1 / i for i, x in enumerate(ranked_ids[:k_mrr], 1) if x in relevant), 0.0)
    return {"recall_at_3": recall, "mrr_at_5": rr}


def mean(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def response_row(query, result):
    answered = result["estado"] == "respondida"
    cited = result["respuesta"]["fuente"]["id"] if answered else None
    return {"id": query["id"], "query": query["query"], "tipo": query["tipo"],
            "categoria_esperada": query["categoria"], "answerable": query["answerable"],
            "etiqueta_predicha": (result["clasificacion"] or {}).get("etiqueta"),
            "estado": result["estado"], "fuente": cited,
            "cita_valida": bool(answered and cited in query["relevant"]),
            "motivo": result["motivo"],
            "top_ids": [r["id"] for r in (result["busqueda"] or {}).get("ranking", [])]}


def response_metrics(rows):
    """Métricas de la respuesta final con evidencia.

    respuestas_sin_respaldo: el error que más importa evitar (responder sin fuente correcta).
    """
    yes = [r for r in rows if r["answerable"]]
    no = [r for r in rows if not r["answerable"]]
    emitted = [r for r in rows if r["estado"] == "respondida"]
    return {
        "n": len(rows), "respondibles": len(yes), "sin_evidencia": len(no),
        "respuestas_correctas_con_cita": sum(r["cita_valida"] for r in yes),
        "tasa_respuesta_correcta": sum(r["cita_valida"] for r in yes) / len(yes) if yes else None,
        "respuestas_sin_respaldo": sum(not r["cita_valida"] for r in emitted),
        "precision_de_cita": sum(r["cita_valida"] for r in emitted) / len(emitted) if emitted else None,
        "recall_abstencion": sum(r["estado"] != "respondida" for r in no) / len(no) if no else None,
        "tasa_abstencion_falsa": sum(r["estado"] != "respondida" for r in yes) / len(yes) if yes else None,
    }
