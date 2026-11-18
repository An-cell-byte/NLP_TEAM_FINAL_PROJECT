"""Funciones sin modelo: validación de entrada, protección de datos y métricas."""
import pytest
from sklearn.metrics import f1_score

from soporte_pln.datos import redact
from soporte_pln.evaluacion import macro_f1_from_confusion, ranking_metrics, response_metrics
from soporte_pln.recuperacion import content_terms
from soporte_pln.sistema import validate_input


@pytest.mark.parametrize("value, reason", [
    (None, "se esperaba texto"), (42, "se esperaba texto"), ("", "vacía"), ("   \n ", "vacía"),
    ("?!? 123", "no contiene palabras"), ("a" * 1001, "supera"),
])
def test_entradas_invalidas(value, reason):
    text, problem = validate_input(value)
    assert text is None and reason in problem


def test_entrada_valida_se_normaliza():
    assert validate_input("  Olvidé   mi contraseña ") == ("Olvidé mi contraseña", None)


def test_redaccion_de_datos_personales():
    text = "Soy ana.perez@example.com, tel 81 1234 5678, tarjeta 4111 1111 1111 1111, folio INC-0412"
    safe = redact(text)
    assert "[CORREO]" in safe and "[TELEFONO]" in safe and "[TARJETA]" in safe
    assert "example.com" not in safe and "4111" not in safe and "INC-0412" in safe


def test_cortesia_no_cuenta_como_evidencia():
    assert content_terms("Buen día, la VPN no conecta. ¿Me pueden orientar?") == ["conecta", "no", "vpn"]


def test_macro_f1_manual_coincide_con_sklearn():
    y = ["a", "a", "b", "b", "c", "c"]
    p = ["a", "b", "b", "b", "a", "c"]
    from sklearn.metrics import confusion_matrix
    manual, _ = macro_f1_from_confusion(confusion_matrix(y, p, labels=["a", "b", "c"]))
    assert manual == pytest.approx(f1_score(y, p, average="macro"))


def test_metricas_de_ranking_a_mano():
    assert ranking_metrics(["x", "r", "y"], ["r"]) == {"recall_at_3": 1.0, "mrr_at_5": 0.5}
    assert ranking_metrics(["x", "y", "z", "r"], ["r"]) == {"recall_at_3": 0.0, "mrr_at_5": 0.25}
    assert ranking_metrics(["x"], []) == {"recall_at_3": None, "mrr_at_5": None}


def test_metricas_de_respuesta():
    rows = [{"answerable": True, "estado": "respondida", "cita_valida": True},
            {"answerable": True, "estado": "abstencion", "cita_valida": False},
            {"answerable": False, "estado": "respondida", "cita_valida": False},
            {"answerable": False, "estado": "abstencion", "cita_valida": False}]
    m = response_metrics(rows)
    assert m["respuestas_sin_respaldo"] == 1 and m["recall_abstencion"] == 0.5
    assert m["precision_de_cita"] == 0.5 and m["tasa_abstencion_falsa"] == 0.5
