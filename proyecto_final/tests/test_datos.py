"""Datos autorizados: identificadores, particiones sin fuga y base de conocimiento verificable."""
import json

import pandas as pd
import pytest

from soporte_pln.datos import DATOS, load_knowledge_base, load_queries, load_requests, sha256, validate_splits

# Huella del solicitudes.csv entregado en las actividades (ACT3, C7-C9): no se modifica.
SHA_SOLICITUDES = "923d4fd289a7f12f8654d1ebcdc60c30bb550257b76d203a8b60920848eb099f"


def test_csv_original_intacto():
    assert sha256(DATOS / "solicitudes.csv") == SHA_SOLICITUDES


def test_ids_y_particiones_conservados():
    df = load_requests()
    original = df[df.id.str.startswith("S")]
    assert list(original.id) == [f"S{i:03d}" for i in range(1, 145)]
    assert (df.groupby("split").size() == pd.Series({"test": 30, "train": 120, "validation": 30})).all()
    assert df.groupby("label").size().min() >= 36


def test_validacion_detecta_fuga_por_familia():
    df = load_requests()
    leaked = df.copy()
    leaked.loc[leaked.index[0], "split"] = "test"  # misma familia en train y test
    with pytest.raises(ValueError, match="Fuga"):
        validate_splits(leaked)


def test_base_de_conocimiento():
    docs, chunks = load_knowledge_base()
    assert len(docs) >= 10
    # 4,412 palabras en el cuerpo de los pasajes (5,050 con títulos y encabezados).
    assert sum(len(c.texto.split()) for c in chunks) >= 4000
    assert all(d["licencia"] == "CC0-1.0" for d in docs)
    assert len({c.id for c in chunks}) == len(chunks)


def test_consultas_coherentes_y_sin_duplicados():
    _, chunks = load_knowledge_base()
    ids = {c.id for c in chunks}
    pools = {n: load_queries(n) for n in ("dev", "test_v1", "test")}
    for rows in pools.values():
        assert all(set(r["relevant"]) <= ids for r in rows)
    norm = lambda q: q["query"].casefold().strip()
    test = {norm(q) for q in pools["test"]}
    assert not test & {norm(q) for n in ("dev", "test_v1") for q in pools[n]}
    assert sum(q["answerable"] for q in pools["test"]) == 15 and len(pools["test"]) == 20


def test_prueba_vigente_es_la_registrada():
    registro = json.loads((DATOS / "registro_particiones.json").read_text(encoding="utf-8"))
    esperado = registro["eventos"][-1]["sha256_consultas_test"]
    assert sha256(DATOS / "consultas_test.json") == esperado
