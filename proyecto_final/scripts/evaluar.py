"""Ejecuta todos los experimentos y guarda los resultados en resultados/.

Orden (cada paso solo usa lo permitido):
 1. Resumen y huellas de los datos.
 2. Clasificadores: rejilla en validación, elección y métricas de prueba.
 3. Recuperadores: elección por MRR@5 en consultas de desarrollo.
 4. Puerta de evidencia: calibración en desarrollo (estricta vs. mejorada).
 5. Se congela la política (resultados/politica.json) y DESPUÉS se evalúa la prueba.
 6. Ablaciones: se retira un componente a la vez.
Uso: python scripts/evaluar.py
"""
import json
import sys
import time
import warnings
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore", category=FutureWarning)

from soporte_pln import experimentos as X  # noqa: E402
from soporte_pln.sistema import Config  # noqa: E402

OUT = ROOT / "resultados"


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def figures(cls, gates, abl):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#c9c8c3", "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                         "axes.spines.right": False})

    # 1) Macro-F1 de validación y prueba de los dos clasificadores.
    fig, ax = plt.subplots(figsize=(6, 3.4))
    names = {"clasico": "Clásico (TF-IDF + RL)", "contextual": "Contextual (MiniLM + RL)"}
    x = np.arange(2)
    for i, (kind, color) in enumerate([("clasico", BLUE), ("contextual", ORANGE)]):
        r = cls["resultados"][kind]
        vals = [r["validation"]["macro_f1"], r["test"]["macro_f1"]]
        bars = ax.bar(x + (i - 0.5) * 0.36, vals, 0.34, color=color, label=names[kind], edgecolor="white", linewidth=2)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}", ha="center", color=INK, fontsize=9)
    ax.set_xticks(x, ["Validación (n=30)", "Prueba (n=30)"])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Macro-F1 (5 clases)")
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig_clasificadores.png", dpi=200)
    plt.close(fig)

    # 2) Matriz de confusión del modelo elegido en prueba.
    chosen = cls["resultados"][cls["elegido"]]["test"]
    cm, labels = np.array(chosen["confusion"]), chosen["labels"]
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    ax.imshow(cm, cmap="Blues", vmin=0, vmax=cm.max())
    short = [l.replace("fuera_de_alcance", "fuera de\nalcance") for l in labels]
    ax.set_xticks(range(len(labels)), short, rotation=0, fontsize=8)
    ax.set_yticks(range(len(labels)), short, fontsize=8)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else INK)
    ax.set_xlabel("Predicha")
    ax.set_ylabel("Real")
    ax.spines[:].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_confusion_prueba.png", dpi=200)
    plt.close(fig)

    # 3) Puertas y ablaciones: respuestas correctas con cita vs. respuestas sin respaldo (prueba).
    rows = [("Puerta estricta (demo)", gates["estricta"]["test"]),
            ("Cobertura relajada sin veto", gates["cobertura_relajada"]["test"]),
            ("Relajada + veto (final)", gates["relajada_con_veto"]["test"]),
            ("Relajada + veto + sinónimos", gates["veto_con_sinonimos"]["test"]),
            ("Ablación: sin puerta", abl["sin_puerta_de_evidencia"]["test"]["metricas"]),
            ("Ablación: sin filtro por clase", abl["sin_filtro_por_clasificacion"]["test"]["metricas"])]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    y = np.arange(len(rows))[::-1]
    good = [m["respuestas_correctas_con_cita"] for _, m in rows]
    bad = [m["respuestas_sin_respaldo"] for _, m in rows]
    ax.barh(y + 0.18, good, 0.34, color=BLUE, label="Correctas con cita (de 15)", edgecolor="white", linewidth=2)
    ax.barh(y - 0.18, bad, 0.34, color=ORANGE, label="Sin respaldo (error a evitar)", edgecolor="white", linewidth=2)
    for yy, g, b in zip(y, good, bad):
        ax.text(g + 0.2, yy + 0.18, str(g), va="center", fontsize=9, color=INK)
        ax.text(b + 0.2, yy - 0.18, str(b), va="center", fontsize=9, color=INK)
    ax.set_yticks(y, [r[0] for r in rows], fontsize=9)
    ax.set_xlabel("Consultas de prueba (20: 15 respondibles, 5 sin evidencia)")
    ax.grid(axis="x", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "fig_puertas_ablaciones.png", dpi=200)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    ctx = X.preparar()
    save("datos_resumen.json", X.resumen_datos(ctx))

    cls = X.comparar_clasificadores(ctx)
    cls["reproduccion_4_clases"] = X.reproduccion_cuatro_clases(ctx)
    save("clasificacion.json", cls)
    kind = cls["elegido"]
    classifier = X.entrenar(ctx, kind, cls["mejor_por_modelo"][kind])
    print(f"Clasificador elegido: {classifier.describe()}")

    ret = X.comparar_recuperadores(ctx)
    save("recuperacion.json", ret)
    base = Config(retriever=ret["elegido"]["recuperador"], alpha=ret["elegido"]["alpha"])
    print(f"Recuperador elegido: {ret['elegido']}")

    # Calibración solo con desarrollo.
    gates = {g: X.calibrar_puerta(ctx, classifier, base, g) for g in X.GATES}
    final_gate = X.elegir_puerta(gates)
    final = gates[final_gate]["config"]
    policy = X.congelar(final, {"modelo": kind, **cls["mejor_por_modelo"][kind]}, final_gate, OUT / "politica.json")
    print(f"Política congelada: {policy['config']}")

    # Prueba: se abre una vez, con la política ya congelada.
    for g in gates.values():
        g["test_eval"] = X.evaluar_sistema(classifier, ctx.chunks, ctx.encoder, g["config"], ctx.test_q)
        g["test"] = g["test_eval"]["metricas"]
        g["dev_eval"] = X.evaluar_sistema(classifier, ctx.chunks, ctx.encoder, g["config"], ctx.dev_q)
        g["config"] = g["config"].as_dict()
    save("puerta.json", gates)

    abl = X.ablaciones(ctx, classifier, final)
    save("ablaciones.json", abl)
    figures(cls, gates, abl)

    summary = {
        "clasificador": {k: {"val_macro_f1": v["validation"]["macro_f1"], "test_macro_f1": v["test"]["macro_f1"],
                             "test_ic95": v["test_ic95_macro_f1"], "test_accuracy": v["test"]["accuracy"]}
                         for k, v in cls["resultados"].items()} | {"elegido": kind},
        "recuperacion": {f"{r['recuperador']}_{r['alpha']}": {"dev_mrr": r["dev"]["mrr_at_5"], "test_mrr": r["test"]["mrr_at_5"],
                                                              "dev_r3": r["dev"]["recall_at_3"], "test_r3": r["test"]["recall_at_3"]}
                         for r in ret["tabla"]},
        "puertas": {g: {"dev": v["dev"], "test": v["test"], "config": v["config"]} for g, v in gates.items()},
        "puerta_final": final_gate,
        "ablaciones": {a: {s: v[s]["metricas"] for s in v} for a, v in abl.items()},
        "segundos": round(time.perf_counter() - t0, 1),
    }
    save("resumen.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
