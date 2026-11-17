# Cómo construimos Qwerty

La idea fue usar una sola conversación para consultar archivos y datos de una biblioteca ficticia. Tomemos dos preguntas como punto de partida. **¿Cuánto dura el préstamo?** se responde con la política de préstamos. **¿Cuántos préstamos tiene Ana?** se responde contando registros de MySQL.

La guía sigue el orden de construcción. Cada etapa señala los archivos del proyecto y explica cómo comprobarla. Si quieres levantar el demo en tu equipo, empieza por la guía de instalación de tu sistema. [macOS](./docs/INSTALACION.md) | [Windows](./README_WINDOWS.md)

Si quieres ampliar el demo después de instalarlo, consulta las [preguntas frecuentes](./PREGUNTAS_FRECUENTES.md).

## 1. Reparte el trabajo entre los componentes

| Componente | Responsabilidad |
| --- | --- |
| Open WebUI | Presenta el chat, inicia sesión y administra las conversaciones. |
| PostgreSQL | Guarda las cuentas, las conversaciones y la configuración de Open WebUI. |
| FastAPI | Recibe archivos y preguntas. Decide qué fuente consultar y prepara la respuesta. |
| MySQL | Guarda documentos procesados, fragmentos y respuestas de la API. También aloja una base separada con los datos ficticios de Aurora. |
| Sentence Transformers | Convierte fragmentos y preguntas en vectores para comparar su contenido. |
| Ollama | Interpreta preguntas que no cubren las reglas y puede redactar respuestas con evidencia. |

En la carpeta, `datos/` reúne los ejemplos. `readers.py` los lee, `tabular.py` hace cálculos y `db_sources.py` abre las fuentes autorizadas. `natural_mysql.py` interpreta preguntas de Aurora. `app.py` reúne esas piezas y `openwebui_pipe.py` conecta el chat con la API.

## 2. Prepara los entornos y la configuración

Trabaja desde una copia limpia del código. El proyecto usa Python 3.11 y dos entornos para instalar las versiones de cada componente por separado.

En macOS ejecuta:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check

python3.11 -m venv .venv_webui
.venv_webui/bin/python -m pip install -r requirements-webui.txt
.venv_webui/bin/python -m pip check

.venv/bin/python configurar.py
```

En Windows usa `py -3.11` y los ejecutables de `Scripts` en lugar de `bin`. La guía de Windows tiene los comandos completos. [Instalación en Windows](./README_WINDOWS.md)

`configurar.py` toma `.env.example` como plantilla. Genera `BRIDGE_SECRET` para firmar las peticiones de la API y `WEBUI_SECRET_KEY` para las sesiones del chat. Puedes ejecutar el configurador otra vez para comprobar que conserva la configuración existente.

Estos son los valores de ejemplo que puedes revisar en `.env`. Mantén las claves que generó el programa.

```dotenv
STORAGE_BACKEND=mysql
API_PORT=18129
UI_PORT=3187
OLLAMA_URL=http://127.0.0.1:11434
GENERATION_MODEL=qwen3:1.7b
```

La copia preparada en el Mac usa `18131`, `3188` y `11435` para la API, la interfaz y Ollama. Usa los valores de tu instalación en las pruebas.

Para ejecutar los ejemplos Python de esta guía, puedes copiar cada bloque en un archivo temporal llamado `comprobar.py` junto a `app.py`. Ejecútalo con `.venv/bin/python comprobar.py` en macOS o con `.\.venv\Scripts\python.exe comprobar.py` en Windows.

## 3. Crea las bases de MySQL y verifica el caso de Aurora

En macOS inicia MAMP con MySQL 8. En Windows inicia tu servicio MySQL 8. Ejecuta los dos programas con el Python del entorno de la API. En macOS se ejecutan así.

```sh
.venv/bin/python configurar_mysql.py
.venv/bin/python verificar_mysql.py
```

Con los nombres de ejemplo, el configurador crea estas dos bases.

- `demo_documental` recibe los datos de la aplicación. Su cuenta puede crear las tablas que necesita FastAPI.
- `demo_documental_aurora` contiene los usuarios y préstamos ficticios. Su cuenta lectora solo tiene acceso a `prestamos_detalle`.

El configurador guarda las cuentas limitadas en `.env.mysql` y `.env.sources`. La contraseña administrativa se usa durante la preparación de las bases.

Revisa `datos/aurora_mysql.sql`. La vista junta el nombre del usuario con sus préstamos. Este es el fragmento que la crea dentro de la base de ejemplo.

```sql
CREATE VIEW prestamos_detalle AS
SELECT p.id, p.usuario_id, u.nombre, p.libro, p.importe, p.fecha
FROM prestamos AS p
JOIN usuarios AS u ON u.id = p.usuario_id;
```

Después de configurar, ejecuta esta consulta en la base de Aurora desde tu cliente MySQL.

```sql
SELECT COUNT(*) AS prestamos,
       COUNT(importe) AS importes_presentes,
       SUM(importe) AS importe_total
FROM prestamos_detalle;
```

Esperamos tres préstamos y dos importes presentes. El total es 20.00. El préstamo de Luis tiene importe ausente, de modo que el promedio se calcula con 12.50 y 7.50. El resultado es 10.00.

## 4. Lee archivos y conserva la ubicación de los datos

`readers.load()` recibe un nombre, el contenido en bytes y, si hace falta, opciones de lectura. Devuelve fragmentos para buscar y tablas para calcular. Cada fragmento conserva la página, línea, fila, hoja o campo de donde salió.

El siguiente ejemplo lee el CSV de préstamos y usa `tabular.calculate()`. El cálculo usa decimales y descarta el importe ausente.

```python
from decimal import Decimal
from pathlib import Path

from readers import load
from tabular import calculate

archivo = Path("datos/prestamos.csv")
contenido = load(archivo.name, archivo.read_bytes())
tabla = contenido["tables"]["datos"]

promedio = calculate(tabla, operation="mean", column="importe")
assert Decimal(promedio["result"]) == Decimal("10.00")
assert promedio["missing_values_excluded"] == 1

print("Promedio", promedio["result"])
print("Valores ausentes", promedio["missing_values_excluded"])
```

Usamos el mismo esquema de tablas para CSV, Excel, JSON y las vistas de MySQL. Así podemos aplicar las mismas operaciones sobre fuentes distintas y mostrar de qué filas salió el resultado.

## 5. Busca fragmentos antes de responder

Al cargar un archivo, `app.py` guarda cada fragmento junto con un vector de Sentence Transformers. Un vector es una lista de números que permite comparar el contenido de un fragmento con una pregunta.

La búsqueda léxica usa coincidencias de palabras con TF-IDF. La semántica compara vectores. La híbrida toma en cuenta ambos tipos de búsqueda. En el ZIP, `exercises.py` incluye una demostración léxica y deja las comparaciones para E1. La API verifica la evidencia antes de responder.

Puedes probar primero la búsqueda por palabras con un fragmento del ejemplo. Aquí usamos el modo extractivo, que responde con el texto de la fuente.

```python
from pathlib import Path

from exercises import produce_answer, rank_candidates
from readers import load

archivo = Path("datos/politicas.txt")
partes = load(archivo.name, archivo.read_bytes())["parts"]
fragmentos = [
    {
        "id": f"politica-{numero}",
        "document": archivo.name,
        "version": 1,
        **parte,
    }
    for numero, parte in enumerate(partes, start=1)
]

pregunta = "¿Cuánto dura el préstamo?"
ordenados = rank_candidates(pregunta, fragmentos, "lexica", embed=None)
respuesta = produce_answer(pregunta, ordenados[:1], "extractivo")

assert "siete días" in respuesta["answer"]
assert respuesta["references"][0]["document"] == archivo.name
print(respuesta["answer"])
```

En E2 se desarrolla la síntesis con citas. Parte de los fragmentos seleccionados y comprueba con tus propios casos qué afirmaciones quedan respaldadas y cuándo conviene mostrar el texto original.

## 6. Convierte preguntas de MySQL en operaciones

`db_sources.py` busca la conexión y las columnas en la política de `.env.sources`. Lee la vista con la cuenta de Aurora y devuelve filas con tipos y ubicación.

`natural_mysql.py` intenta interpretar las preguntas comunes con reglas. Para **¿Cuántos préstamos tiene Ana?** prepara un plan con la operación `count` y un filtro por nombre. Para otras formulaciones, Ollama propone un plan con la misma estructura. Python lo valida y realiza el cálculo con las filas autorizadas.

Este ejemplo muestra el plan y su resultado. Ejecuta primero la configuración de MySQL.

```python
from dotenv import load_dotenv

from db_sources import read
from natural_mysql import simple_plan, validate
from tabular import calculate

load_dotenv(".env.sources", override=True)
tabla, momento, motor = read("aurora_mamp", "prestamos_detalle")
pregunta = "¿Cuántos préstamos tiene Ana?"

plan = simple_plan(pregunta, tabla)
assert plan is not None
plan = validate(plan, tabla, pregunta, [])

resultado = calculate(
    tabla,
    operation=plan.operation,
    column=plan.column,
    filters=[filtro.model_dump() for filtro in plan.filters],
)

assert resultado["result"] == 2
print(plan.model_dump())
print("Préstamos de Ana", resultado["result"])
```

La validación revisa que existan las columnas y que el plan conserve el nombre y los valores pedidos. Ollama entrega datos estructurados. El código controla la consulta y los permisos de lectura.

## 7. Conecta la lógica con FastAPI

`storage.py` prepara la conexión con MySQL. `app.py` crea las tablas de la aplicación al iniciar y reúne la carga, la búsqueda y los cálculos.

| Ruta | Qué hace |
| --- | --- |
| `GET /health` | Comprueba la conexión de la API con su base. |
| `POST /documents` | Procesa un archivo y guarda los fragmentos y sus vectores. |
| `POST /query` | Elige la consulta de Aurora o la búsqueda en documentos. Guarda la respuesta por propietario e identificador de solicitud. |
| `POST /calculate` | Calcula sobre una tabla de archivo o una vista autorizada. |
| `GET /sources/{identifier}` | Permite revisar el fragmento que respaldó una respuesta. |

El conector envía la identidad del usuario, la hora y una firma HMAC. La firma se calcula con la clave del puente y los bytes exactos de la petición. La API la verifica antes de abrir los datos del propietario.

Con FastAPI en marcha, puedes comprobar una petición de lectura firmada. El ejemplo obtiene la clave del archivo local sin imprimirla.

```python
import hashlib
import hmac
import time

import httpx
from dotenv import dotenv_values

config = dotenv_values(".env")
api = "http://127.0.0.1:" + config.get("API_PORT", "18129")
propietario = "comprobacion_construccion"
marca = str(int(time.time()))
mensaje = f"{propietario}\n{marca}\n".encode()
firma = hmac.new(config["BRIDGE_SECRET"].encode(), mensaje, hashlib.sha256)

with httpx.Client(timeout=10) as cliente:
    salud = cliente.get(api + "/health")
    salud.raise_for_status()
    assert salud.json()["storage"] == "mysql"

    assert cliente.get(api + "/documents").status_code == 401
    documentos = cliente.get(
        api + "/documents",
        headers={
            "X-Owner": propietario,
            "X-Time": marca,
            "X-Signature": firma.hexdigest(),
        },
    )
    documentos.raise_for_status()
    assert isinstance(documentos.json(), list)
    print("La API acepta la petición firmada.")
```

La lista puede estar vacía porque el perfil de comprobación todavía no tiene documentos. En una petición con cuerpo, la firma incluye también esos bytes.

### Cómo damos formato a las respuestas

El cálculo devuelve el resultado y sus datos de revisión. `natural_mysql.py` conserva los filtros y la fuente en `database_result`. `app.py` guarda el identificador de consulta con la respuesta. Quitamos **Filtros**, **Fuente** y **Consulta** del texto del chat al separar esos campos del mensaje que se muestra.

`tabular.render_answer()` redacta con los valores ya calculados. Usa el nombre y el número para el conteo, identifica la operación en los importes y arma una tabla en los listados. `/calcular` usa el mismo formato. `openwebui_pipe.py` muestra `answer` y envía las citas de los documentos por separado.

Este ejemplo usa un resultado reducido para mostrar las dos frases posibles.

```python
from tabular import render_answer

resultado = {
    "operation": "count",
    "result": 2,
    "filters": [{"column": "nombre", "op": "eq", "value": "Ana"}],
    "source": {"dataset": "prestamos_detalle"},
}

print(render_answer(resultado, variant=0))
print(render_answer(resultado, variant=1))
```

Las frases son **Ana tiene 2 préstamos** y **Encontré 2 préstamos de Ana**. FastAPI alterna entre las dos formas según las veces que esa cuenta haya enviado la misma pregunta. Guarda el texto elegido, así un reintento con el mismo identificador devuelve la misma frase. La variación se hace en Python y no requiere otra llamada a Ollama.

En una respuesta extractiva, la variante puede añadir una frase breve antes del fragmento. El texto del documento y sus citas se conservan tal como se recuperaron.

## 8. Prepara Ollama y PostgreSQL

Instala Ollama, abre su aplicación y descarga el modelo.

```sh
ollama pull qwen3:1.7b
ollama list
```

Confirma que la lista incluya `qwen3:1.7b`. FastAPI lee `OLLAMA_URL` y `GENERATION_MODEL` de `.env`. La plantilla usa el puerto `11434`. Si lo cambiaste, usa el puerto de tu instalación. [Configuración por sistema](./docs/PUENTE.md#conectar-ollama-local)

Con Ollama en marcha, este ejemplo usa los mismos valores del demo y pide una respuesta breve. Sirve para comprobar el motor por separado antes de probar el chat con datos.

```python
import httpx
from dotenv import dotenv_values

config = dotenv_values(".env")
url = config["OLLAMA_URL"].rstrip("/")
respuesta = httpx.post(
    url + "/api/chat",
    json={
        "model": config["GENERATION_MODEL"],
        "messages": [{"role": "user", "content": "¿Cuánto es dos más dos?"}],
        "think": False,
        "stream": False,
    },
    timeout=60,
)
respuesta.raise_for_status()
print(respuesta.json()["message"]["content"])
```

`natural_mysql.py` usa esa conexión cuando necesita interpretar una pregunta. El mismo servicio local permite experimentar con la redacción generativa en E2. [API de chat de Ollama](https://docs.ollama.com/api/chat)

Para las conversaciones, elige el procedimiento de tu sistema. En macOS, desde una instalación limpia, prepara una instancia local.

```sh
.venv/bin/python configurar_postgresql.py --port 55442
.venv/bin/python gestionar_demo.py detener
```

El primer comando crea la base y verifica la cuenta. El segundo cierra esa instancia de preparación. El lanzador de macOS la vuelve a iniciar cuando abras el demo.

En Windows crea el usuario y la base desde pgAdmin. Usa `configurar_webui_windows.py` para guardar y comprobar la conexión a ese servicio. [Paso 4 de la guía de Windows](./README_WINDOWS.md)

En ambos sistemas, `iniciar_webui.py` lee `WEBUI_DATABASE_URL` y usa `WEBUI_DATA_DIR` para los adjuntos. En una instalación nueva, la ruta de datos es relativa al proyecto.

```dotenv
WEBUI_DATA_DIR=.runtime/webui
```

Para inspeccionar la base, registra una conexión en pgAdmin con el host, puerto, base y usuario que aparecen en `.env.webui`. La contraseña está en `WEBUI_PG_PASSWORD`. Abre **Databases / demo_webui / Schemas / public / Tables** después del primer arranque de Open WebUI. Ahí puedes ver las cuentas, las conversaciones y la configuración. En MySQL, FastAPI guarda sus documentos procesados y consultas en `demo_documental`, y la biblioteca ficticia queda en `demo_documental_aurora`. [Pasos en macOS](./README.md#consultar-postgresql-desde-pgadmin-en-macos) y [pasos en Windows](./README_WINDOWS.md#consultar-postgresql-desde-pgadmin-en-windows).

## 9. Registra el conector en Open WebUI

Abre el demo con `./iniciar_demo.sh` en macOS o `.\iniciar_demo.cmd` en PowerShell. Abre la dirección que imprime el lanzador y crea la primera cuenta.

`conectar_openwebui.py` registra la función de `openwebui_pipe.py` con el nombre **Qwerty**. En macOS ejecútalo así.

```sh
.venv/bin/python conectar_openwebui.py
```

En Windows usa `.\.venv\Scripts\python.exe conectar_openwebui.py`. Introduce la cuenta administradora del chat y confirma los puertos de la interfaz y de la API. La conexión se hace desde Open WebUI con la clave de `.env`.

El conector toma el último mensaje y la identidad de Open WebUI. Si escribes `/cargar`, lee el adjunto de tu cuenta y lo envía a `POST /documents`. Si haces una pregunta, llama a `POST /query`. Con `file_context=false`, el conector controla qué archivos se envían y qué fuentes se muestran.

Si ya tenías Qwerty instalado, reinicia el demo y vuelve a ejecutar `conectar_openwebui.py` con tu cuenta administradora para registrar el conector actualizado. Revisa la actualización cuando el programa pida confirmarla. Desde esa actualización, las cargas y sustituciones guardan el ID del adjunto para que `/purgar` pueda identificarlo.

### Preguntas para probar el demo

Escribe estas preguntas directamente en un chat con **Qwerty**. Los resultados de MySQL corresponden a los datos ficticios de Aurora incluidos en el demo.

| Pregunta sobre MySQL | Qué puedes comprobar |
| --- | --- |
| ¿Cuántos préstamos hay en MySQL? | Hay 3 préstamos. |
| ¿Cuántos préstamos tiene Ana? | Ana tiene 2 préstamos. |
| ¿Y Luis? | Si la haces después de la pregunta sobre Ana, Luis tiene 1 préstamo. |
| ¿Cuántos préstamos tiene cada usuario? | Ana tiene 2 y Luis tiene 1. |
| Muestra los préstamos de Ana | Aparecen *PLN aplicado* y *Bases de datos*. |
| ¿Cuál es el importe total de los préstamos? | El total es 20.00. |
| ¿Cuál es el importe promedio de los préstamos? | El promedio es 10.00 y se calcula con los 2 importes disponibles. |
| ¿Cuál es el importe máximo de los préstamos? | El máximo es 12.50. |
| ¿Cuál es el importe mínimo de los préstamos? | El mínimo es 7.50. |
| ¿Cuál es el importe total de los préstamos con importe mayor que 10 en MySQL? | El total de los préstamos que cumplen la condición es 12.50. |
| ¿Qué columnas tiene la vista de préstamos en MySQL? | La vista `prestamos_detalle` incluye ID, ID de usuario, nombre, libro, importe y fecha. |

Para probar los archivos, adjunta el indicado desde `datos/` y envía `/cargar`. Cuando el chat confirme la carga, escribe la pregunta y abre la referencia para revisar de dónde sale la respuesta.

| Archivo de ejemplo | Qué escribir en el chat | Qué puedes comprobar |
| --- | --- | --- |
| `politicas.txt` o `politicas.pdf` | ¿Cuánto dura el préstamo? | El préstamo dura siete días naturales. |
| `politicas.txt` | ¿Cuántos préstamos se permiten por persona? | La política permite hasta tres libros por persona. |
| `politicas.txt` | ¿Cuándo se permite la renovación? | Se permite una vez si no existe otra reserva. |
| `horarios.txt` | ¿Cuál es el horario de la biblioteca? | Abre de lunes a viernes de 8 a 20 y el sábado de 9 a 13. El domingo permanece cerrada. |
| `horarios.txt` | ¿Cuándo abre los sábados? | Abre de 9 a 13 horas. |
| `multas.txt` | ¿Cuál es la multa por retraso? | Cinco créditos ficticios por libro y día. |
| `salas.txt` | ¿Por cuántas horas se reservan las salas de estudio? | Se reservan por dos horas. |
| `salas.txt` | ¿Cuándo se cancela la reserva de sala? | Después de quince minutos de retraso. |
| `prestamos.csv`, `biblioteca.xlsx` o `biblioteca.json` | PLN aplicado | El chat localiza el título en el archivo. Prueba cada formato por separado para revisar su referencia. |
| Cualquiera de estos ejemplos | ¿Cuál es el clima en Marte? | El asistente indica que no encontró esa información. |

Al repetir una pregunta de MySQL, la frase puede variar. El resultado se calcula con los datos disponibles en ese momento. Para sumar, promediar o contar filas de un archivo CSV, Excel o JSON, consulta [los ejemplos de `/calcular`](./docs/USO.md#cálculos-que-podemos-comprobar).

## 10. Reúne el arranque y prueba el cierre

En macOS, `gestionar_demo_mac.py` registra los servicios en `launchd`. Calcula sus rutas a partir de la ubicación actual de la carpeta. En Windows, `gestionar_demo_windows.py` comprueba MySQL y PostgreSQL y administra los procesos de FastAPI y Open WebUI. Los comandos de cada sistema llaman al lanzador correspondiente.

| Acción | macOS | Windows |
| --- | --- | --- |
| Iniciar | `./iniciar_demo.sh` | `.\iniciar_demo.cmd` |
| Detener | `./detener_demo.sh` | `.\detener_demo.cmd` |

Haz una pregunta, detén el demo y vuelve a iniciarlo. Entra con la misma cuenta y abre la conversación anterior. La prueba comprueba tanto el cierre de los procesos como la persistencia de los datos.

## 11. Comprueba los resultados y prepara un respaldo

Ejecuta la suite con `.venv/bin/python -m pytest -q` en macOS o `.\.venv\Scripts\python.exe -m pytest -q` en Windows. Las pruebas cubren lectores, cálculos, filtros y control de procesos. Aparte, prueba con el chat y tus servicios locales.

| Qué comprobar | Resultado esperado |
| --- | --- |
| Consulta de Ana | Ana tiene 2 préstamos. |
| Cálculo de importes | Total 20.00 y promedio 10.00. |
| Política de préstamos | Siete días naturales, con referencia al archivo. |
| Pregunta ajena a las fuentes | El asistente indica que no tiene evidencia suficiente. |
| Dos cuentas | Cada una consulta sus propios archivos y conversaciones. |
| Reinicio | La cuenta y la conversación siguen disponibles. |

Para actualizar dependencias, detén el demo y respalda las bases, los adjuntos y la configuración privada. Después usa los requisitos fijados de cada entorno y repite las pruebas.

Si editas las guías, vuelve a generar `Documentacion.html` con `.venv_webui/bin/python generar_documentacion.py` en macOS o con `.\.venv_webui\Scripts\python.exe generar_documentacion.py` en Windows. Puedes mover o copiar la documentación sin regenerarla.

## 12. Sigue una conversación con SQL

Abre un chat normal con **Qwerty**. Adjunta `datos/politicas.txt`, envía `/cargar` y copia el `id` del documento que devuelve el chat. Después pregunta **¿Cuánto dura el préstamo?**. La respuesta debe mencionar siete días naturales y citar `politicas.txt`. Cambia el título de esa conversación a **Prueba SQL Qwerty** y úsala para las consultas siguientes.

### Historial del chat en PostgreSQL

En pgAdmin abre **Query Tool** desde `demo_webui`. Busca el chat por su título y copia su `id`. La fecha de la última actividad se obtiene a partir de la marca de tiempo que guarda Open WebUI.

```sql
SELECT id, title, to_timestamp(updated_at) AS ultima_actividad
FROM public.chat
WHERE title = 'Prueba SQL Qwerty'
ORDER BY updated_at DESC;
```

En la siguiente consulta, reemplaza `ID_DEL_CHAT` por ese valor. `role` indica quién escribió cada mensaje. `content` está guardado como JSON y `#>> '{}'` extrae su valor como texto. Verás el comando de carga, la pregunta y las respuestas en el orden en que se guardaron.

```sql
SELECT to_timestamp(created_at) AS fecha,
       role AS quien_escribio,
       content #>> '{}' AS mensaje
FROM public.chat_message
WHERE chat_id = 'ID_DEL_CHAT'
ORDER BY created_at, id;
```

### Documento, fragmentos y respuesta en MySQL

En macOS, abre phpMyAdmin de MAMP. En Windows, usa MySQL Workbench o el cliente MySQL que ya tengas. Selecciona `demo_documental` o el esquema indicado en `MYSQL_DATABASE` dentro de `.env.mysql`. En el primer renglón reemplaza `ID_DEL_DOCUMENTO` por el valor que devolvió `/cargar`. Ejecuta el bloque en la misma pestaña. `@documento_id` conserva ese valor solo en la sesión SQL.

```sql
SET @documento_id = 'ID_DEL_DOCUMENTO';

SELECT id, name, version, status, LEFT(body, 180) AS texto_procesado
FROM documents
WHERE id = @documento_id AND deleted = 0;

SELECT id, version, page,
       LEFT(body, 180) AS fragmento,
       JSON_LENGTH(embedding) AS dimensiones_del_vector
FROM chunks
WHERE document_id = @documento_id
ORDER BY page, id;

SELECT t.request_id, t.query AS pregunta,
       JSON_UNQUOTE(JSON_EXTRACT(t.response, '$.answer')) AS respuesta,
       JSON_EXTRACT(t.response, '$.references[*].document') AS archivos_citados
FROM turns AS t
JOIN documents AS d ON d.owner = t.owner
WHERE d.id = @documento_id AND d.deleted = 0
  AND t.query = '¿Cuánto dura el préstamo?'
  AND JSON_SEARCH(t.response, 'one', CONCAT(d.id, ':v%:part%'),
                  NULL, '$.references[*].id') IS NOT NULL;
```

`documents` muestra el estado y la versión del archivo procesado. `chunks` muestra las partes del texto y el tamaño de su representación numérica. `turns` guarda la pregunta y el resultado de FastAPI. La última consulta busca la pregunta en la misma cuenta y exige una cita a ese documento. Si no devuelve filas, verifica que la respuesta en el chat haya citado el archivo que acabas de cargar.

### Sustituir o eliminar un archivo en MySQL

Continúa con el documento ficticio de la prueba anterior. En phpMyAdmin o MySQL Workbench, selecciona `demo_documental` o el esquema indicado en `.env.mysql`. Reemplaza `ID_DEL_DOCUMENTO` por el `id` que devolvió `/cargar`. Ejecuta el bloque completo en cada etapa para comparar los resultados.

```sql
SET @documento_id = 'ID_DEL_DOCUMENTO';

SELECT id, name, status,
       version AS ultima_version, deleted AS eliminado,
       CASE WHEN deleted = 0 AND status = 'disponible'
            THEN version END AS version_vigente
FROM documents
WHERE id = @documento_id;

SELECT version, COUNT(*) AS fragmentos
FROM chunks
WHERE document_id = @documento_id
GROUP BY version
ORDER BY version;
```

1. **Antes de sustituir.** Si acabas de cargar `politicas.txt`, `version_vigente` debe mostrar `1`. Anota cuántos fragmentos aparecen para esa versión.
2. **Después de sustituir.** Crea una copia de prueba con el texto «El préstamo dura nueve días naturales». Adjunta esa copia en el chat y envía `/sustituir ID` con el identificador original. Al confirmar la carga, repite el bloque. El identificador es el mismo, `version_vigente` ahora muestra `2` y en `chunks` aparecen solo los fragmentos de la versión 2. Pregunta de nuevo **¿Cuánto dura el préstamo?** y comprueba que el chat cite la versión nueva. Si falla la sustitución, la versión anterior sigue disponible.
3. **Después de eliminar.** Envía `/eliminar ID` en el chat con el mismo identificador. Al repetir el bloque, la fila de `documents` conserva `ultima_version = 2`, `eliminado` vale `1` y `version_vigente` es `NULL`. La consulta de fragmentos devuelve cero filas. Para saber si puedes consultar el documento, revisa `version_vigente`. El campo `status` por sí solo puede seguir mostrando `disponible`.

La eliminación marca el documento como retirado y quita sus fragmentos del índice. MySQL conserva la fila del documento y las respuestas guardadas en `turns`. Puedes comprobar qué versiones se citaron antes de eliminar el archivo. Ejecuta esta consulta en la sesión donde definiste `@documento_id`.

```sql
SELECT t.request_id, t.query AS pregunta,
       JSON_EXTRACT(t.response, '$.references[*].version') AS versiones_citadas
FROM turns AS t
JOIN documents AS d ON d.owner = t.owner
WHERE d.id = @documento_id
  AND JSON_SEARCH(t.response, 'one', CONCAT(d.id, ':v%:part%'),
                  NULL, '$.references[*].id') IS NOT NULL;
```

Las versiones de esta última consulta corresponden a citas guardadas en respuestas previas. Para revisar qué versión puede recuperar Qwerty ahora, usa el primer bloque.

### Borrar un archivo y sus citas del demo

Para los archivos cargados con el conector actualizado, escribe `/purgar ID` con el identificador que devolvió `/cargar`. Qwerty muestra el nombre del documento y devuelve un comando como `/purgar ID confirmar CODIGO`. Copia el comando exacto dentro de los 10 minutos siguientes. El primer mensaje solo muestra la operación. Si cambias de opinión, basta con dejar vencer el código.

La confirmación retira los adjuntos registrados de todas las versiones y elimina el documento, sus fragmentos, sus metadatos y las respuestas de FastAPI que lo citaban. Si una respuesta cita varios archivos, se elimina ese registro completo de MySQL. Qwerty cancela la purga si detecta que un adjunto se usa en otro documento de Qwerty o en una base de conocimiento de Open WebUI. Si la operación queda pendiente por un fallo, vuelve a escribir `/purgar ID` y usa una confirmación nueva.

Los fragmentos purgados dejan de estar disponibles en `/fuente ID_FRAGMENTO`. Las conversaciones ya guardadas pueden conservar el texto y las citas que mostraron. Para retirar esas copias, usa el menú de cada conversación en Open WebUI. La comprobación SQL al final de esta sección también sirve para verificar `/purgar`.

#### Procedimiento manual para archivos anteriores

Los documentos cargados antes de esta actualización pueden carecer del ID de uno o más adjuntos. En ese caso Qwerty indica que debes seguir el procedimiento manual. Identifica cada adjunto por su cuenta, conversación y versión antes de borrarlo. Si pertenece a otro documento o base de conocimiento, conserva ese adjunto. Haz la prueba con un documento ficticio en un chat dedicado, porque borrar una conversación elimina todos sus mensajes.

1. Copia el `id` que devolvió `/cargar` o usa `/documentos` para localizarlo. En el chat, envía `/eliminar ID` con ese valor. A partir de ahí, una cita antigua puede seguir mostrando el texto guardado en la conversación. Si pides el fragmento con `/fuente ID_FRAGMENTO`, Qwerty ya no puede recuperarlo.
2. En tu perfil de Open WebUI abre **Settings / Data Controls / Manage Files / Manage**. Busca y elimina el adjunto exacto. Si sustituiste el archivo, revisa también los adjuntos de las versiones anteriores. Borra las conversaciones que incluyan esas citas o reproduzcan el contenido. Si hay enlaces compartidos o exportaciones, revisa también esas copias. [Gestión de archivos en Open WebUI](https://docs.openwebui.com/features/chat-conversations/data-controls/files/).
3. Detén Qwerty con `./detener_demo.sh` en macOS o `.\detener_demo.cmd` en Windows. Deja MySQL en marcha. Abre una sesión en MySQL Workbench o en el cliente de terminal y selecciona el esquema indicado en `MYSQL_DATABASE` dentro de `.env.mysql`. Usa una cuenta autorizada para borrar registros de ese esquema. Conserva la misma sesión hasta confirmar o revertir la transacción.

Comprueba primero el nombre, el propietario y el estado del documento. Sustituye `ID_DEL_DOCUMENTO` por el valor que copiaste. El resultado esperado es una fila del archivo que elegiste con `deleted = 1`.

```sql
SET @documento_id = 'ID_DEL_DOCUMENTO';

SELECT id, owner, name, version, deleted
FROM documents
WHERE id = @documento_id;
```

Copia el valor de `owner` en `ID_DEL_PROPIETARIO`. El bloque siguiente solo actúa cuando el ID y el propietario corresponden a un documento ya retirado. La purga borra de FastAPI cada respuesta que cita ese documento. Si una respuesta cita varios archivos, se borra ese registro completo de `turns` y los demás documentos permanecen disponibles.

```sql
SET @propietario = 'ID_DEL_PROPIETARIO';
SET @objetivo = NULL;

START TRANSACTION;

SELECT id INTO @objetivo
FROM documents
WHERE id = @documento_id AND owner = @propietario AND deleted = 1
FOR UPDATE;

DELETE FROM turns
WHERE owner = @propietario
  AND JSON_SEARCH(response, 'one', CONCAT(@objetivo, ':v%:part%'),
                  NULL, '$.references[*].id') IS NOT NULL;

DELETE FROM chunks WHERE document_id = @objetivo;
DELETE FROM document_locations WHERE document_id = @objetivo;
DELETE FROM document_structures WHERE document_id = @objetivo;
DELETE FROM source_manifest WHERE document_id = @objetivo;
DELETE FROM document_attachments WHERE document_id = @objetivo;

DELETE FROM documents
WHERE id = @objetivo AND owner = @propietario AND deleted = 1;
SELECT ROW_COUNT() AS documentos_borrados;
```

Si los comandos terminan correctamente y `documentos_borrados` vale `1`, ejecuta `COMMIT;` en la misma sesión. Si aparece un error o el resultado es distinto, ejecuta `ROLLBACK;` y revisa el identificador y el esquema antes de reintentar. Tras confirmar, el borrado es irreversible en esa base activa.

Verifica que todos los conteos sean `0`. Si abriste otra sesión, define de nuevo `@documento_id` y `@propietario` antes de ejecutar la consulta.

```sql
SELECT
  (SELECT COUNT(*) FROM documents WHERE id = @documento_id) AS documentos,
  (SELECT COUNT(*) FROM chunks WHERE document_id = @documento_id) AS fragmentos,
  (SELECT COUNT(*) FROM document_locations WHERE document_id = @documento_id) AS ubicaciones,
  (SELECT COUNT(*) FROM document_structures WHERE document_id = @documento_id) AS estructuras,
  (SELECT COUNT(*) FROM source_manifest WHERE document_id = @documento_id) AS manifiestos,
  (SELECT COUNT(*) FROM document_attachments WHERE document_id = @documento_id) AS adjuntos_registrados,
  (SELECT COUNT(*) FROM turns
   WHERE owner = @propietario
     AND JSON_SEARCH(response, 'one', CONCAT(@documento_id, ':v%:part%'),
                     NULL, '$.references[*].id') IS NOT NULL) AS respuestas_con_citas;
```

Esta verificación cubre el ID en la base activa. Cada carga duplicada tiene su propio ID. Si necesitas retirar todas las copias, revisa por separado los respaldos, los registros de recuperación de la base y cualquier mensaje o exportación que contenga texto copiado sin una cita registrada.

[Respaldo y recuperación](./docs/RESPALDO.md) | [Diagnóstico](./docs/ERRORES.md) | [Instalación en Windows](./README_WINDOWS.md)
