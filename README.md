# Qwerty

Demo local para consultar archivos y hacer preguntas sobre los préstamos ficticios de la biblioteca Aurora. Open WebUI gestiona el acceso y las conversaciones. FastAPI recupera la evidencia y consulta MySQL.

- [Primera instalación en macOS](./docs/INSTALACION.md)
- [Instalar y levantar el demo en Windows](./README_WINDOWS.md)
- [Consultar PostgreSQL desde pgAdmin en macOS](./README.md#consultar-postgresql-desde-pgadmin-en-macos)
- [Cómo construimos el demo, paso a paso y con código](./README_CONSTRUCCION.md)
- [Preguntas frecuentes sobre archivos, MySQL y acceso para el grupo](./PREGUNTAS_FRECUENTES.md)

También puedes abrir [Documentacion.html](./Documentacion.html) en tu navegador. Está en esta carpeta y sus enlaces funcionan al moverla o copiarla a Windows.

## Uso diario en macOS

Si acabas de extraer el ZIP, completa primero la instalación de tu sistema. Cada instalación tiene sus propias cuentas y configuración.

1. Abre MAMP y pulsa **Start**.
2. Desde Terminal, en la carpeta del demo, ejecuta:

   ```sh
   ./iniciar_demo.sh
   ```

3. Abre la dirección que imprime el comando, inicia sesión y selecciona **Qwerty**. Si acabas de crear la primera cuenta, registra el conector como indica la guía de instalación.

## Preguntas para probar el demo

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

Al repetir una pregunta de MySQL, la frase puede variar. El resultado se calcula con los datos disponibles en ese momento. [Cómo damos formato a las respuestas](./README_CONSTRUCCION.md#cómo-damos-formato-a-las-respuestas)

Para sumar, promediar o contar filas de un archivo CSV, Excel o JSON, consulta [los ejemplos de `/calcular`](./docs/USO.md#cálculos-que-podemos-comprobar).

FastAPI usa **qwen3:1.7b** por dentro cuando necesita interpretar una pregunta o redactar con evidencia.

## Estado y cierre

macOS mantiene los procesos del demo en marcha mediante `launchd`. Puedes cerrar Terminal y ChatGPT. Después de reiniciar el Mac o cerrar tu sesión de macOS, abre MAMP y vuelve a iniciar el demo. [Servicios de usuario en macOS](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)

```sh
./estado_demo.sh
./detener_demo.sh
```

El primer comando muestra el estado de los procesos del demo y de MAMP. El segundo cierra los procesos propios de Qwerty. MAMP y cualquier instancia de Ollama que hayas iniciado aparte se controlan desde sus aplicaciones.

## Ollama local

FastAPI toma la dirección y el modelo de `OLLAMA_URL` y `GENERATION_MODEL` en `.env`. El lanzador reutiliza Ollama si ya responde en el puerto configurado. En el chat selecciona **Qwerty**. [Configuración y prueba de Ollama](./docs/PUENTE.md#conectar-ollama-local)

## Mover la carpeta

1. Apaga el demo con `./detener_demo.sh`.
2. Mueve la carpeta completa. Incluye los archivos `.env*` y las carpetas ocultas `.runtime`, `.venv` y `.venv_webui`.
3. En la carpeta nueva ejecuta `./iniciar_demo.sh`. El lanzador prepara los servicios para esa ubicación y recupera las rutas de los adjuntos locales.

Estos pasos sirven para moverlo en el mismo Mac. En otro equipo prepara Python, PostgreSQL y MAMP según la guía de instalación.

## Servicios y archivos

| Componente | Puerto de ejemplo | Configuración o datos |
| --- | --- | --- |
| Open WebUI | 3187 | `.env.webui` y `.runtime/webui` |
| FastAPI | 18129 | `.env`, `.env.mysql` y `.env.sources` |
| PostgreSQL 16 | 55442 | `.env.webui` y `.runtime/postgresql` |
| Ollama | 11434 | `OLLAMA_URL` y `GENERATION_MODEL` en `.env` |
| MySQL 8 de MAMP | 8889 | Bases de ejemplo `demo_documental` y `demo_documental_aurora` |

Los modelos de búsqueda se descargan a `.runtime/huggingface` en macOS al procesar el primer archivo. Las bases de MySQL permanecen en MAMP y se consultan con las cuentas limitadas de `.env.mysql` y `.env.sources`.

Si recibiste el ZIP, abre [los ejercicios](./EJERCICIOS.md) para ubicar el punto de partida y el trabajo de E1 y E2. Comparte únicamente el ZIP limpio. Cada instalación guarda su configuración y su historial por separado.

## Consultar PostgreSQL desde pgAdmin en macOS

1. Abre MAMP y pulsa **Start**. Desde la carpeta de Qwerty, ejecuta `./iniciar_demo.sh` para que arranque también PostgreSQL.
2. Abre pgAdmin. Si ya tienes la conexión **Qwerty local**, ábrela y pasa al paso 4. Si es la primera vez, haz clic derecho en **Servers**, elige **Register / Server** y escribe **Qwerty local** en **General / Name**. El nombre solo identifica la conexión en pgAdmin.
3. En **Connection**, usa los valores del archivo privado `.env.webui`, que se genera en la misma carpeta que este README. Ábrelo en tu editor para encontrar la línea `WEBUI_PG_PASSWORD`.

   | Campo en pgAdmin | Variable en `.env.webui` | Valor de ejemplo en macOS |
   | --- | --- | --- |
   | Host name/address | `WEBUI_PG_HOST` | `127.0.0.1` |
   | Port | `WEBUI_PG_PORT` | `55442` |
   | Maintenance database | `WEBUI_PG_DATABASE` | `demo_webui` |
   | Username | `WEBUI_PG_USER` | `demo_webui` |
   | Password | `WEBUI_PG_PASSWORD` | La contraseña de tu instalación |

4. Si acabas de registrar la conexión, pulsa **Save**. Abre **Qwerty local / Databases / demo_webui / Schemas / public / Tables**. Si ya tenías el árbol abierto, haz clic derecho en **Tables** y selecciona **Refresh**. Busca `chat`, `user`, `file`, `model` y `function`.

Si tienes varias instancias registradas, verifica el puerto. Las entradas «PostgreSQL 15» y «PostgreSQL 16» pueden apuntar a otros servicios locales. Puedes usar **Properties / Connection** para comprobar a cuál apunta cada registro. En **Query Tool**, abierto desde `demo_webui`, confirma la base, el usuario y el puerto.

```sql
SELECT current_database(), current_user, inet_server_port();
```

Los archivos de la instancia que inicia Qwerty en macOS están en `.runtime/postgresql`. La contraseña `WEBUI_PG_PASSWORD` corresponde al usuario de PostgreSQL. Para entrar al chat usa las credenciales de tu cuenta de Open WebUI. El ZIP incluye la plantilla `.env.webui.example` y cada instalación genera su propio `.env.webui`. [Conexión desde Windows](./README_WINDOWS.md#consultar-postgresql-desde-pgadmin-en-windows).

## Qué guarda cada base

| Motor y base | Qué guarda Qwerty |
| --- | --- |
| PostgreSQL, `demo_webui` | Open WebUI guarda cuentas, permisos, conversaciones, configuración y registros de los archivos adjuntos. Las tablas `model` y `function` guardan el modelo visible y el conector. Los archivos originales se almacenan en `.runtime/webui/uploads` con la configuración predeterminada. |
| MySQL, `demo_documental` | FastAPI guarda documentos procesados, fragmentos, vectores para la búsqueda, versiones y datos de las consultas y respuestas de la API. |
| MySQL, `demo_documental_aurora` | Contiene los usuarios y préstamos ficticios. La vista `prestamos_detalle` reúne esos datos para responder preguntas como «¿Cuántos préstamos tiene Ana?». |

Usa pgAdmin para PostgreSQL. Para abrir las bases MySQL en macOS, usa phpMyAdmin de MAMP o un cliente MySQL. El puerto configurado está en `.env.mysql` y suele ser `8889` en MAMP.

### Prueba rápida con SQL en macOS

Abre un chat normal con Qwerty. Adjunta `datos/politicas.txt`, envía `/cargar` y copia el `id` del documento que devuelve el chat. Pregunta **¿Cuánto dura el préstamo?** y cambia el título de la conversación a **Prueba SQL Qwerty**. En pgAdmin abre **Query Tool** desde `demo_webui`. Esta consulta muestra el identificador del chat y cuándo se actualizó.

```sql
SELECT id, title, to_timestamp(updated_at) AS ultima_actividad
FROM public.chat
WHERE title = 'Prueba SQL Qwerty'
ORDER BY updated_at DESC;
```

En phpMyAdmin, abre la pestaña **SQL** de `demo_documental` y sustituye `ID_DEL_DOCUMENTO` por el `id` que copiaste al cargar el archivo.

```sql
SELECT id, name, status, version
FROM documents
WHERE id = 'ID_DEL_DOCUMENTO' AND deleted = 0;
```

En la [prueba completa con SQL](./README_CONSTRUCCION.md#12-sigue-una-conversación-con-sql) puedes ver cómo se leen los mensajes en PostgreSQL y cómo se comprueban el texto procesado, los fragmentos y la respuesta con su fuente en MySQL.

Para comprobar qué ocurre después de `/sustituir ID` o `/eliminar ID`, vuelve a la pestaña **SQL** de `demo_documental` en phpMyAdmin y ejecuta esta consulta con el mismo identificador.

```sql
SELECT id, version AS ultima_version, deleted AS eliminado,
       CASE WHEN deleted = 0 AND status = 'disponible'
            THEN version END AS version_vigente
FROM documents
WHERE id = 'ID_DEL_DOCUMENTO';
```

La sustitución conserva el identificador e incrementa `version_vigente`. Al eliminar el archivo, `eliminado` pasa a `1` y `version_vigente` queda en `NULL`. [Prueba de versiones y fragmentos](./README_CONSTRUCCION.md#sustituir-o-eliminar-un-archivo-en-mysql).

### Borrar un archivo y sus citas en macOS

Busca el ID con `/documentos` y escribe `/purgar ID`. Qwerty muestra qué se va a borrar y devuelve un comando de confirmación. Si lo confirmas, elimina los adjuntos registrados de ese documento y sus respuestas con citas en MySQL. El texto guardado en conversaciones anteriores se gestiona desde Open WebUI. [Confirmación, comprobación SQL y procedimiento para archivos anteriores](./README_CONSTRUCCION.md#borrar-un-archivo-y-sus-citas-del-demo).

## Guías

- [Instalación y actualización de dependencias](./docs/INSTALACION.md)
- [Uso con documentos y MySQL](./docs/USO.md)
- [Arquitectura y puertos](./docs/ARQUITECTURA.md)
- [Conexión de Open WebUI con FastAPI](./docs/PUENTE.md)
- [Diagnóstico de fallos](./docs/ERRORES.md)
- [Respaldo y recuperación](./docs/RESPALDO.md)
