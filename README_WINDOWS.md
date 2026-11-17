# Qwerty en Windows

Sigue esta guía para instalar el demo en Windows y arrancarlo desde PowerShell. En una instalación ya preparada, inicia MySQL y PostgreSQL y ejecuta `.\iniciar_demo.cmd` desde la carpeta del demo.

Puedes abrir [Documentacion.html](./Documentacion.html) en tu navegador para consultar todas las guías de la carpeta.

Para agregar archivos, consultar otras tablas o dar acceso a más personas, revisa las [preguntas frecuentes](./PREGUNTAS_FRECUENTES.md).

Si el demo ya funciona, puedes ir directamente a [la conexión de pgAdmin](./README_WINDOWS.md#consultar-postgresql-desde-pgadmin-en-windows).

## 1. Instala las herramientas

| Herramienta | Para qué la usamos |
| --- | --- |
| Python 3.11 para Windows x64 | Ejecuta FastAPI y Open WebUI en entornos separados. [Instalar Python](https://docs.python.org/3.11/using/windows.html) |
| MySQL 8.x | Guarda los documentos y contiene la base de ejemplo de Aurora. Instala MySQL 8.4 con su configurador o usa un servidor 8.x que ya tengas. [Instalar MySQL](https://dev.mysql.com/doc/refman/8.4/en/windows-installation.html) |
| PostgreSQL 16 o 17 con pgAdmin | Guarda las cuentas y las conversaciones. Selecciona el servidor y pgAdmin en el instalador. [Instalar PostgreSQL](https://www.postgresql.org/download/windows/) |
| Ollama | Ejecuta el modelo local `qwen3:1.7b`. [Instalar Ollama](https://docs.ollama.com/windows) |

Configura MySQL y PostgreSQL como servicios de Windows. Guarda el puerto y la contraseña administrativa de cada uno. En los ejemplos usamos `3306` para MySQL y `5432` para PostgreSQL.

MAMP para Windows incluye MySQL 5.7.24. Para el demo usa MySQL 8 independiente. Si otro servidor ya usa `3306`, elige un puerto libre como `3307` al configurar el servidor nuevo. [Versiones de MAMP para Windows](https://www.mamp.info/en/release-notes/windows/)

## 2. Prepara una copia limpia

Usa una copia que contenga `app.py`, `iniciar_demo.cmd`, `datos/` y los archivos de requisitos. Si vienes del Mac, copia el código, los datos de ejemplo y las plantillas `.env.example`, `.env.mysql.example` y `.env.webui.example`. Prepara entornos y credenciales nuevos en Windows. Las carpetas `.venv`, `.venv_webui` y `.runtime` del Mac pertenecen a esa instalación.

Abre PowerShell en la carpeta del demo. Todos los comandos de esta guía parten de ahí.

```powershell
py -3.11 --version
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check

py -3.11 -m venv .venv_webui
& .\.venv_webui\Scripts\python.exe -m pip install -r requirements-webui.txt
& .\.venv_webui\Scripts\python.exe -m pip check
```

El primer entorno es para la API. El segundo es para Open WebUI y usa `requirements-webui.lock.txt` para fijar sus dependencias. Llamamos a cada Python por su ruta relativa para usar el entorno correcto.

## 3. Prepara MySQL

En **Servicios** de Windows comprueba que MySQL 8 esté en ejecución. El configurador pedirá la cuenta que puede crear las bases del demo.

```powershell
& .\.venv\Scripts\python.exe configurar.py
& .\.venv\Scripts\python.exe configurar_mysql.py
& .\.venv\Scripts\python.exe verificar_mysql.py
```

| Dato que pide el programa | Qué escribir |
| --- | --- |
| Host | `127.0.0.1` |
| Puerto | El de tu MySQL 8. Escribe `3306` si usas el puerto habitual. La sugerencia `8889` corresponde al Mac. |
| Administrador y contraseña | La cuenta que configuraste para MySQL, normalmente `root`, y su contraseña. |
| Base nueva y usuario nuevo | `demo_documental` si ambos nombres están libres. Para otra instalación usa nombres nuevos que empiecen por `demo_`. |

El programa crea una base para la API y otra para Aurora. Con el nombre sugerido quedan `demo_documental` y `demo_documental_aurora`. También crea una cuenta de escritura para la API y una cuenta que solo puede leer la vista ficticia. La última comprobación debe mostrar MySQL conectado y **tres filas** en la vista de Aurora.

## 4. Prepara PostgreSQL desde pgAdmin

1. Abre pgAdmin. En **Servers**, abre **Register** y elige **Server**. Escribe un nombre como **PostgreSQL local** y conecta con `127.0.0.1`, el puerto del servidor, el usuario `postgres` y la contraseña elegida en el instalador.
2. En **Login/Group Roles**, abre **Create** y elige **Login/Group Role**. Crea `demo_webui`, ponle una contraseña en **Definition** y habilita **Can login** en **Privileges**. Déjalo como usuario normal.
3. En **Databases**, abre **Create** y elige **Database**. Crea `demo_webui` y selecciona `demo_webui` como propietario. Si el nombre ya existe, elige uno nuevo para esta instalación.
4. Guarda la conexión del demo desde PowerShell.

```powershell
& .\.venv\Scripts\python.exe configurar_webui_windows.py
```

Ingresa el host, el puerto, la base y la cuenta que acabas de crear. Usa la contraseña de `demo_webui`. El programa comprueba la conexión y genera `.env.webui` con `MANAGE_LOCAL_POSTGRES=false`, porque Windows administra PostgreSQL como servicio.

## 5. Conecta Ollama local

Abre Ollama desde Inicio y ejecuta lo siguiente en PowerShell.

```powershell
ollama pull qwen3:1.7b
ollama list
(Invoke-RestMethod "http://127.0.0.1:11434/api/tags").models.name
```

La lista debe incluir `qwen3:1.7b`. Si PowerShell todavía no encuentra `ollama`, abre una ventana nueva. La primera descarga necesita conexión a Internet. La búsqueda en documentos también descarga un modelo de representaciones la primera vez que lo necesita.

Revisa estos valores en el archivo `.env` de la carpeta del demo. Si tu Ollama usa otro puerto, escribe ese puerto en `OLLAMA_URL` y úsalo también al probar `/api/tags`.

```dotenv
OLLAMA_URL=http://127.0.0.1:11434
GENERATION_MODEL=qwen3:1.7b
```

FastAPI se conecta a Ollama por esa dirección. En Open WebUI usa **Qwerty** para que el conector pueda consultar MySQL y los documentos. [Cómo se conectan los servicios](./docs/PUENTE.md#conectar-ollama-local)

## 6. Arranca el demo y conecta el chat

Con MySQL y PostgreSQL en marcha, ejecuta:

```powershell
.\iniciar_demo.cmd
```

El lanzador comprueba las bases y Ollama. Después inicia FastAPI y Open WebUI en segundo plano. Abre la dirección que imprime. Con la configuración de ejemplo es [Open WebUI en 3187](http://127.0.0.1:3187).

La primera cuenta que crees en Open WebUI administra el chat. Usa el correo y la contraseña de esa cuenta para registrar el conector.

```powershell
& .\.venv\Scripts\python.exe conectar_openwebui.py
```

Acepta la dirección de Open WebUI que propone el programa. Para la API usa `http://127.0.0.1:18129` si conservaste el puerto de ejemplo. En una instalación de una sola persona puedes dejar vacía la lista de usuarios autorizados. Después recarga la página, abre un chat nuevo y selecciona **Qwerty**.

## 7. Comprueba que responde

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

### Estado de los servicios

```powershell
Invoke-RestMethod "http://127.0.0.1:18129/health"
Invoke-RestMethod "http://127.0.0.1:3187/health"
```

FastAPI debe mostrar `status = ok` y `storage = mysql`.

## Consultar PostgreSQL desde pgAdmin en Windows

1. Abre **Servicios** de Windows y comprueba que el servicio de PostgreSQL esté en ejecución. Si es una instalación nueva, completa el paso 4 y arranca Qwerty una vez con `.\iniciar_demo.cmd` para que Open WebUI cree sus tablas.
2. En pgAdmin, haz clic derecho en **Servers** y elige **Register / Server**. En **General / Name** escribe **Qwerty local**. Puedes conservar la conexión administrativa del paso 4 y usar esta entrada para consultar la base con el usuario del demo.
3. En **Connection**, copia los valores de `.env.webui`. Ese archivo se genera al ejecutar `configurar_webui_windows.py` y queda en la misma carpeta que este README.

   | Campo en pgAdmin | Variable en `.env.webui` | Valor de ejemplo en Windows |
   | --- | --- | --- |
   | Host name/address | `WEBUI_PG_HOST` | `127.0.0.1` |
   | Port | `WEBUI_PG_PORT` | `5432` |
   | Maintenance database | `WEBUI_PG_DATABASE` | `demo_webui` |
   | Username | `WEBUI_PG_USER` | `demo_webui` |
   | Password | `WEBUI_PG_PASSWORD` | La contraseña que elegiste para ese usuario en el paso 4 |

4. Pulsa **Save** y abre **Qwerty local / Databases / demo_webui / Schemas / public / Tables**. Si elegiste otro nombre para la base, busca el que indica `WEBUI_PG_DATABASE`. Si el árbol ya estaba abierto, usa **Refresh** en **Tables**. Deben aparecer tablas como `chat`, `user`, `file`, `model` y `function`.

Si tienes varias instalaciones de PostgreSQL, usa el puerto exacto de `WEBUI_PG_PORT`. En **Query Tool**, abierto desde la base de Qwerty, verifica la conexión.

```sql
SELECT current_database(), current_user, inet_server_port();
```

El archivo `.env.webui` es privado. El ZIP trae la plantilla `.env.webui.example`. Usa `WEBUI_PG_PASSWORD` para la conexión de PostgreSQL y tu cuenta de Open WebUI para entrar al chat. En Windows, el servicio de PostgreSQL administra su propio directorio de datos.

### Qué guarda cada base en Windows

- **PostgreSQL, `demo_webui`.** Guarda las cuentas, los permisos, las conversaciones, los modelos y la configuración de Open WebUI. También guarda los registros de los adjuntos. Los archivos originales quedan en `.runtime/webui/uploads` con la configuración predeterminada.
- **MySQL, `demo_documental`.** Guarda documentos procesados, fragmentos, vectores, versiones y datos de las consultas y respuestas de FastAPI.
- **MySQL, `demo_documental_aurora`.** Guarda los usuarios y préstamos ficticios que consulta la vista `prestamos_detalle`.

Usa pgAdmin para PostgreSQL. Para revisar las dos bases de MySQL en Windows, puedes usar MySQL Workbench con el puerto indicado en `.env.mysql`. [Conexión desde macOS](./README.md#consultar-postgresql-desde-pgadmin-en-macos).

### Prueba rápida con SQL en Windows

Abre un chat normal con Qwerty. Adjunta `datos/politicas.txt`, envía `/cargar` y copia el `id` del documento que devuelve el chat. Pregunta **¿Cuánto dura el préstamo?** y cambia el título de la conversación a **Prueba SQL Qwerty**. En pgAdmin abre **Query Tool** desde `demo_webui` y busca ese chat por su título.

```sql
SELECT id, title, to_timestamp(updated_at) AS ultima_actividad
FROM public.chat
WHERE title = 'Prueba SQL Qwerty'
ORDER BY updated_at DESC;
```

En MySQL Workbench, selecciona `demo_documental` como esquema y reemplaza `ID_DEL_DOCUMENTO` por el `id` que copiaste al cargar el archivo.

```sql
SELECT id, name, status, version
FROM documents
WHERE id = 'ID_DEL_DOCUMENTO' AND deleted = 0;
```

Sigue la [prueba completa con SQL](./README_CONSTRUCCION.md#12-sigue-una-conversación-con-sql) para ver los mensajes del chat, los fragmentos indexados y el registro de la pregunta y la respuesta.

Después de `/sustituir ID` o `/eliminar ID`, usa el mismo identificador en una pestaña SQL de MySQL Workbench con `demo_documental` seleccionado.

```sql
SELECT id, version AS ultima_version, deleted AS eliminado,
       CASE WHEN deleted = 0 AND status = 'disponible'
            THEN version END AS version_vigente
FROM documents
WHERE id = 'ID_DEL_DOCUMENTO';
```

La sustitución conserva el identificador e incrementa `version_vigente`. Al eliminar el archivo, `eliminado` pasa a `1` y `version_vigente` queda en `NULL`. [Prueba de versiones y fragmentos](./README_CONSTRUCCION.md#sustituir-o-eliminar-un-archivo-en-mysql).

### Borrar un archivo y sus citas en Windows

Busca el ID con `/documentos` y escribe `/purgar ID`. Qwerty muestra qué se va a borrar y devuelve un comando de confirmación. Si lo confirmas, elimina los adjuntos registrados de ese documento y sus respuestas con citas en MySQL. El texto guardado en conversaciones anteriores se gestiona desde Open WebUI. [Confirmación, comprobación SQL y procedimiento para archivos anteriores](./README_CONSTRUCCION.md#borrar-un-archivo-y-sus-citas-del-demo).

## Uso diario

Inicia MySQL y PostgreSQL desde **Servicios** si están apagados. Después puedes arrancar o detener el demo desde su carpeta.

```powershell
.\iniciar_demo.cmd
```

```powershell
.\detener_demo.cmd
```

Al detener el demo, Windows conserva los servicios de las bases. Ollama se cierra si lo inició el lanzador. Para la siguiente sesión usa tu misma cuenta y los archivos que ya configuraste.

Para actualizar dependencias, detén el demo y respalda tus datos. Vuelve a ejecutar los comandos `pip install` y `pip check` del paso 2 en sus respectivos entornos. Después inicia el demo y repite las comprobaciones del paso 7.

## Dónde revisar la configuración

| Archivo | Qué guarda |
| --- | --- |
| `.env` | Puertos `API_PORT` y `UI_PORT`, dirección `OLLAMA_URL`, modelo y claves internas. |
| `.env.mysql` | Host, puerto y cuenta de la API en MySQL. |
| `.env.sources` | Acceso de lectura y vista autorizada de Aurora. |
| `.env.webui` | Conexión de PostgreSQL y ruta de los adjuntos. |

| Si ocurre esto | Revisa esto |
| --- | --- |
| Python no se encuentra | Confirma que `py -3.11 --version` responde en una ventana nueva. |
| MySQL muestra versión 5.7 | Revisa el puerto del servicio MySQL 8 en `.env.mysql` y `.env.sources`. |
| PostgreSQL rechaza la conexión | Prueba en pgAdmin con la cuenta propietaria de la base del demo. |
| Open WebUI no abre | Revisa `.runtime/windows/webui.log` y el puerto impreso por el lanzador. |
| La interfaz abre pero la consulta falla | Revisa `.runtime/windows/api.log` y la dirección de la API que usa el conector. |
| Ollama no responde | Abre Ollama y revisa el puerto `11434`. Si lo inició el demo, consulta `.runtime/windows/modelo.log`. |

Si necesitas ver los mensajes en pantalla, ejecuta `.\detener_demo.cmd`. Desde la carpeta del demo abre dos ventanas de PowerShell y ejecuta un comando en cada una. Usa Ctrl+C en esas ventanas para cerrar el inicio manual.

```powershell
& .\.venv\Scripts\python.exe iniciar_api.py
```

```powershell
& .\.venv_webui\Scripts\python.exe iniciar_webui.py
```

Los pasos de esta guía se contrastaron con los scripts y la documentación oficial. La ejecución completa del demo en Windows queda por validar en ese sistema.

[Construcción paso a paso](./README_CONSTRUCCION.md) | [Respaldo de datos](./docs/RESPALDO.md) | [Guía de uso](./docs/USO.md)
