"""Experimentos reproducibles. Los usan scripts/evaluar.py y el notebook.

Regla de oro: todo se elige con train/validación (clasificación) o con las
consultas de desarrollo (recuperación y puerta). La prueba se abre una sola vez,
después de congelar la política.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import itertools
import json
import time

from . import clasificacion as C
from . import evaluacion as E
from .datos import (DATOS, LABELS, LABELS_SISTEMA, ROOT, load_knowledge_base, load_queries,
                    load_requests, load_synonyms, sha256)
from .recuperacion import make_retriever, search
from .sistema import Config, SistemaSoporte

RETRIEVERS = [("tfidf", 0.0), ("semantico", 0.0), ("hibrido", 0.3), ("hibrido", 0.5), ("hibrido", 0.7)]
TAU_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
COVERAGE_GRID = [0.25, 0.5, 0.6, 0.75, 1.0]
# Puertas comparadas. «estricta» es la regla del demo de clase: todos los términos cubiertos.
# «relajada_con_veto» fue la mejora de la iteración 1; «veto_con_sinonimos», el intento de la
# iteración 2. La puerta final NO se fija a mano: se elige con desarrollo (elegir_puerta).
GATES = {"estricta": {"min_coverage": [1.0], "oov_veto": [False], "synonyms": False},
         "cobertura_relajada": {"min_coverage": COVERAGE_GRID, "oov_veto": [False], "synonyms": False},
         "relajada_con_veto": {"min_coverage": COVERAGE_GRID, "oov_veto": [True], "synonyms": False},
         "veto_con_sinonimos": {"min_coverage": COVERAGE_GRID, "oov_veto": [True], "synonyms": True}}
# La prueba v1 se usó una vez y quedó retirada; desde entonces forma parte de desarrollo.
DEV_SETS = ("dev", "test_v1")


@dataclass
class Contexto:
    df: object
    train: object
    validation: object
    test: object
    encoder: object
    docs: list
    chunks: list
    dev_q: list
    test_q: list


def preparar(encoder=None):
    from .encoder import Encoder
    df = load_requests()
    docs, chunks = load_knowledge_base()
    return Contexto(df, *[df[df.split == s].reset_index(drop=True) for s in ("train", "validation", "test")],
                    encoder or Encoder(), docs, chunks, [q for n in DEV_SETS for q in load_queries(n)],
                    load_queries("test"))


def resumen_datos(ctx):
    words = sum(len(c.texto.split()) for c in ctx.chunks)
    files = ["solicitudes.csv", "fuera_de_alcance.csv", "consultas_dev.json", "consultas_test_v1.json",
             "consultas_test.json", "sinonimos.json"]
    return {
        "solicitudes_por_particion": ctx.df.groupby(["split", "label"]).size().unstack().to_dict(),
        "familias": int(ctx.df.family.nunique()),
        "ids": {"originales": "S001-S144", "fuera_de_alcance": "F001-F036"},
        "base_conocimiento": {"documentos": len(ctx.docs), "fragmentos": len(ctx.chunks), "palabras": words,
                              "por_categoria": {c: sum(ch.categoria == c for ch in ctx.chunks)
                                                for c in sorted({ch.categoria for ch in ctx.chunks})}},
        "consultas": {n: {"total": len(q), "respondibles": sum(r["answerable"] for r in q)}
                      for n, q in [("dev", ctx.dev_q), ("test", ctx.test_q)]},
        "sha256": {f: sha256(DATOS / f) for f in files},
    }


# ------------------------------------------------------------- clasificación
def comparar_clasificadores(ctx):
    grid, best = [], {}
    for kind in ("clasico", "contextual"):
        rows, best[kind] = C.grid_search(kind, ctx.train, ctx.validation, ctx.encoder)
        grid += rows
    chosen = C.choose_model(best)
    final = {}
    for kind, b in best.items():
        start = time.perf_counter()
        model = C.build(kind, b["C"], ctx.encoder, b["representacion"]).fit(ctx.train.text, ctx.train.label)
        fit_s = time.perf_counter() - start
        result = {"config": b, "descripcion": model.describe(), "segundos_ajuste_final": fit_s,
                  "latencia_ms_por_texto": 1000 * C.timed_predict(model, ctx.test.text)}
        for name, part in [("validation", ctx.validation), ("test", ctx.test)]:
            pred = model.predict(part.text)
            result[name] = E.classification_metrics(part.label, pred, LABELS_SISTEMA)
            if name == "test":
                result["test_ic95_macro_f1"] = E.bootstrap_macro_f1(part.label, pred, LABELS_SISTEMA)
                result["test_predicciones"] = [{"id": i, "texto": t, "real": y, "predicha": p}
                                               for i, t, y, p in zip(part.id, part.text, part.label, pred)]
        final[kind] = result
    return {"rejilla_validacion": grid, "mejor_por_modelo": best, "elegido": chosen["modelo"], "resultados": final,
            "criterio": "macro-F1 en validación; empate -> menor log-loss en validación"}


def reproduccion_cuatro_clases(ctx):
    """Escenario de las actividades: solo las 4 clases originales y el TF-IDF de make_baseline (C=2)."""
    keep = lambda d: d[d.label.isin(LABELS)]
    tr, va, te = keep(ctx.train), keep(ctx.validation), keep(ctx.test)
    out = {}
    for kind in ("clasico", "contextual"):
        model = C.build(kind, 2.0, ctx.encoder).fit(tr.text, tr.label)
        out[kind] = {n: E.classification_metrics(p.label, model.predict(p.text), LABELS)["macro_f1"]
                     for n, p in [("validation", va), ("test", te)]}
    return out


def entrenar(ctx, kind, cfg):
    return C.build(kind, cfg["C"], ctx.encoder, cfg.get("representacion", "palabras_1-2")).fit(
        ctx.train.text, ctx.train.label)


# ------------------------------------------------------------- recuperación
def metricas_ranking(retriever, queries, k=5):
    rows = []
    for q in queries:
        if not q["answerable"]:
            continue
        ranked = [h["chunk"].id for h in search(retriever, q["query"], k=k)]
        rows.append({"id": q["id"], "query": q["query"], "tipo": q["tipo"], "relevantes": q["relevant"],
                     "ranking": ranked, **E.ranking_metrics(ranked, q["relevant"])})
    return {"recall_at_3": E.mean(r["recall_at_3"] for r in rows),
            "mrr_at_5": E.mean(r["mrr_at_5"] for r in rows), "detalle": rows}


def comparar_recuperadores(ctx):
    """Ranking puro (sin filtro ni puerta). Se elige por MRR@5 de desarrollo; empate -> recall@3."""
    table = []
    for name, alpha in RETRIEVERS:
        retriever = make_retriever(name, ctx.chunks, ctx.encoder, alpha)
        table.append({"recuperador": name, "alpha": alpha, "dev": metricas_ranking(retriever, ctx.dev_q),
                      "test": metricas_ranking(retriever, ctx.test_q)})
    best = max(table, key=lambda r: (round(r["dev"]["mrr_at_5"], 6), round(r["dev"]["recall_at_3"], 6)))
    return {"tabla": table, "elegido": {"recuperador": best["recuperador"], "alpha": best["alpha"]}}


# ---------------------------------------------------------- sistema completo
def evaluar_sistema(classifier, chunks, encoder, config, queries):
    system = SistemaSoporte(classifier, chunks, encoder, config)
    rows = [E.response_row(q, system.responder(q["query"])) for q in queries]
    return {"metricas": E.response_metrics(rows), "detalle": rows}


def clave_seleccion(m, cfg):
    """Primero evitar respuestas sin respaldo; después maximizar respuestas correctas con cita."""
    return (m["respuestas_sin_respaldo"], -m["respuestas_correctas_con_cita"],
            -(m["recall_abstencion"] or 0), -cfg.tau, -cfg.min_coverage)


def calibrar_puerta(ctx, classifier, base, gate):
    rows, best = [], None
    space = GATES[gate]
    synonyms = load_synonyms() if space["synonyms"] else {}
    for c, veto, tau in itertools.product(space["min_coverage"], space["oov_veto"], TAU_GRID):
        cfg = replace(base, min_coverage=c, oov_veto=veto, tau=tau, synonyms=synonyms)
        m = evaluar_sistema(classifier, ctx.chunks, ctx.encoder, cfg, ctx.dev_q)["metricas"]
        rows.append({"puerta": gate, "min_coverage": c, "oov_veto": veto, "tau": tau, **m})
        if best is None or clave_seleccion(m, cfg) < clave_seleccion(best[1], best[0]):
            best = (cfg, m)
    return {"rejilla_dev": rows, "config": best[0], "dev": best[1]}


def elegir_puerta(calibradas):
    """Misma clave que dentro de cada rejilla, aplicada a los mejores de cada tipo de puerta."""
    return min(calibradas, key=lambda g: clave_seleccion(calibradas[g]["dev"], calibradas[g]["config"]))


def congelar(config, clasificador, puerta, path=None):
    """Guarda la política elegida con huellas de datos y código antes de abrir la prueba."""
    files = (sorted((ROOT / "src" / "soporte_pln").glob("*.py"))
             + sorted((DATOS / "base_conocimiento").glob("*.md"))
             + [DATOS / f"consultas_{n}.json" for n in DEV_SETS]
             + [DATOS / "solicitudes.csv", DATOS / "fuera_de_alcance.csv", DATOS / "sinonimos.json"])
    policy = {"fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "clasificador": clasificador, "puerta": puerta, "config": config.as_dict(),
              "huellas": {str(f.relative_to(ROOT)).replace("\\", "/"): sha256(f) for f in files}}
    if path:
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    return policy


def ablaciones(ctx, classifier, config):
    """Se retira UN componente a la vez; todo lo demás (modelo, datos, umbrales) queda igual."""
    variants = {"sistema_completo": config,
                "sin_puerta_de_evidencia": replace(config, gate=False),
                "sin_filtro_por_clasificacion": replace(config, routing=False)}
    return {name: {split: evaluar_sistema(classifier, ctx.chunks, ctx.encoder, cfg, q)
                   for split, q in [("dev", ctx.dev_q), ("test", ctx.test_q)]}
            for name, cfg in variants.items()}
