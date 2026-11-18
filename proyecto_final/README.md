# Mesa de ayuda con evidencia · Proyecto final integrador de PLN

El sistema recibe una solicitud de soporte, la **clasifica** (acceso, conectividad, pagos, software o fuera de alcance), **busca** pasajes en una base de conocimiento y **responde citando la fuente**. Si la evidencia es insuficiente, **se abstiene** y canaliza la solicitud a una persona.

* Clasificador integrado: MiniLM multilingüe congelado + regresión logística, comparado con TF-IDF + regresión logística.
* Recuperación: híbrida (0.3 · TF-IDF + 0.7 · MiniLM) sobre 80 pasajes de 15 artículos.
* Respuesta: **extractiva**. Copia oraciones del pasaje citado y no genera texto nuevo.
* Todo corre en CPU, sin claves ni servicios externos. Solo se necesita internet una vez, para descargar el modelo.

## Requisitos

* Python **3.11** (probado con 3.11.9 en Windows 11).
* Unos 2.5 GB libres (dependencias + modelo de 470 MB).

## Pasos (desde una carpeta limpia)

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\descargar_modelo.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\evaluar.py
.\.venv\Scripts\python.exe scripts\responder.py "¿Cuántas sesiones puedo tener abiertas al mismo tiempo?"
```

macOS / Linux:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/descargar_modelo.py
.venv/bin/python -m pytest
.venv/bin/python scripts/evaluar.py
.venv/bin/python scripts/responder.py "¿Cuántas sesiones puedo tener abiertas al mismo tiempo?"
```

Qué hace cada paso:

1. `descargar_modelo.py` descarga `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` con la revisión `e8f8c211…` fijada en `models/minilm/`. Si ya tienes el modelo, usa `--desde RUTA` para copiarlo sin internet. La variable de entorno `SOPORTE_MODELO` permite usar otra carpeta.
2. `pytest` ejecuta 24 pruebas (unos 40 s): datos sin fugas, entradas válidas e inválidas, protección de datos personales, métricas recalculadas a mano y el recorrido completo con una fuente verificable y una abstención.
3. `evaluar.py` (unos 2 min) regenera todo `resultados/`: comparación de clasificadores, recuperadores y puertas de evidencia, política congelada, prueba y ablaciones.
4. `responder.py` muestra la clasificación, el ranking de pasajes con la decisión de la puerta, la respuesta y la fuente. Con `--json` muestra el resultado completo y con `--sin-registro` no escribe el registro.

Notebook ejecutado: `notebooks/Proyecto_final.ipynb`. Para volver a ejecutarlo:

```powershell
cd notebooks
..\.venv\Scripts\python.exe -m nbconvert --to notebook --execute --inplace Proyecto_final.ipynb
```

Uso como función:

```python
import sys; sys.path.insert(0, "src")
from soporte_pln.api import responder
r = responder("¿Qué significa la luz roja del router?")
r["estado"], r["mensaje"], r["respuesta"]["fuente"]
```

## Resultados esperados

| | Clásico (TF-IDF caracteres 2-5) | Contextual (MiniLM), integrado |
|---|---|---|
| Macro-F1 validación (30) | 0.594 | **0.794** |
| Macro-F1 prueba (30) | 0.704 [IC95 0.53-0.83] | **0.841** [IC95 0.69-0.96] |

| Sistema completo, prueba vigente (20 consultas) | Valor |
|---|---|
| Recuperación híbrida: recall@3 / MRR@5 | 1.00 / 1.00 |
| Respuestas correctas con cita | 6 de 15 |
| Respuestas sin respaldo | 1 |
| Recall de abstención (consultas sin evidencia) | 0.80 (4 de 5) |
| Ablación sin puerta: correctas / sin respaldo | 15 de 15 / 5 |

Los detalles, la mejora comprobada y el análisis de fallos están en el notebook y en `informe/`.

## Estructura

```
datos/                  datos autorizados (ver datos/DATOS.md)
  solicitudes.csv         144 solicitudes originales del curso, sin cambios
  fuera_de_alcance.csv    36 solicitudes de la quinta clase
  base_conocimiento/      15 artículos Markdown (CC0-1.0)
  consultas_*.json        consultas de desarrollo, prueba retirada y prueba vigente
  registro_particiones.json  historial de roles y huella de la prueba vigente
src/soporte_pln/        código: datos, clasificación, recuperación, sistema, evaluación, API
scripts/                descargar_modelo.py, evaluar.py, responder.py
tests/                  pruebas con pytest
notebooks/              notebook ejecutado
resultados/             JSON, figuras y política congelada; prueba_v1_retirada/
informe/                informe final
```

## Datos, credenciales y registros

* No hay contraseñas, claves ni archivos `.env`. Todos los datos son ficticios.
* Antes de clasificar o registrar, el sistema oculta correos, teléfonos y números de tarjeta.
* `registros/consultas.jsonl` (opcional, ignorado por git) guarda solo la fecha, una huella SHA-256 truncada, la longitud, el estado, la etiqueta y la fuente. **Nunca** guarda el texto de la consulta.
* `models/` y `.venv/` no se entregan: se recrean con los pasos anteriores.

## Verificación desde una carpeta limpia

Se copió la carpeta del proyecto sin `.venv/`, `models/` ni `registros/` a un directorio nuevo y se siguieron los pasos de Windows tal como están escritos, incluida la descarga del modelo desde Hugging Face. Los 24 tests pasaron y `scripts/evaluar.py` reprodujo exactamente las métricas de `resultados/resumen.json`. El registro de esa ejecución está en `resultados/verificacion_carpeta_limpia.txt`.
