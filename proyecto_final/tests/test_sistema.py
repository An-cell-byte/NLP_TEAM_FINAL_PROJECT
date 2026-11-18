"""Recorrido completo con el modelo real y la política congelada."""
import json

from soporte_pln.api import leer_politica, verificar_huellas
from soporte_pln.recuperacion import SENTENCE
from soporte_pln.sistema import SistemaSoporte


def test_politica_corresponde_a_los_archivos_actuales():
    assert verificar_huellas(leer_politica()) == []


def test_respuesta_con_fuente_verificable(sistema):
    r = sistema.responder("¿Cuántas sesiones puedo tener abiertas al mismo tiempo?")
    assert r["estado"] == "respondida"
    fuente = r["respuesta"]["fuente"]
    assert fuente["id"] == "ACC-03#s4"
    pasaje = next(c.texto for c in sistema.chunks if c.id == fuente["id"])
    # Extractiva: cada oración de la respuesta aparece literalmente en el pasaje citado.
    assert all(sentence in pasaje for sentence in SENTENCE.split(r["respuesta"]["texto"]))
    assert [h["rank"] for h in r["busqueda"]["ranking"]] == [1, 2, 3]


def test_abstencion_sin_evidencia(sistema):
    r = sistema.responder("¿La VPN funciona en Linux?")
    assert r["estado"] == "abstencion" and r["respuesta"] is None
    assert "linux" in r["busqueda"]["ranking"][0]["desconocidos"]


def test_fuera_de_alcance_se_canaliza(sistema):
    r = sistema.responder("¿Cuál es la capital de Australia?")
    assert r["estado"] == "abstencion"
    assert r["clasificacion"]["canalizacion"] in {"otra_area", "revision"}


def test_entrada_invalida_no_llega_al_modelo(sistema):
    class Explota:
        classes_ = []

        def predict_proba(self, _):
            raise AssertionError("no debía clasificarse")

    s = SistemaSoporte.__new__(SistemaSoporte)
    s.__dict__.update(sistema.__dict__)
    s.classifier = Explota()
    for value in ["", None, "1234"]:
        assert s.responder(value)["estado"] == "entrada_invalida"


def test_registro_sin_texto_ni_datos_personales(sistema, tmp_path):
    s = SistemaSoporte.__new__(SistemaSoporte)
    s.__dict__.update(sistema.__dict__)
    s.registro = tmp_path / "log.jsonl"
    secret = "Olvidé mi contraseña, mi correo es ana.perez@example.com"
    r = s.responder(secret)
    assert "ana.perez" not in r["consulta_protegida"]
    log = s.registro.read_text(encoding="utf-8")
    assert "contraseña" not in log and "ana.perez" not in log
    entry = json.loads(log)
    assert set(entry) == {"fecha_utc", "huella", "caracteres", "estado", "etiqueta", "fuente"}
