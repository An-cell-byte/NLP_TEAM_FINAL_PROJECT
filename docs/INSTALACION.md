# Instalación local

Haz estos pasos una vez en una copia recién extraída. Necesitas Python 3.11, PostgreSQL 16 o 17, MAMP con MySQL 8 y Ollama. Abre Terminal en la carpeta que contiene `README.md`. Reserva varios GB para los entornos y los modelos, y usa una conexión a Internet para la primera instalación.

Usa un Mac con Apple Silicon y Python ARM64. `python3.11 -c 'import platform; print(platform.machine())'` debe mostrar `arm64`. En un Mac Intel puedes usar una instalación compartida del curso o un equipo compatible. La versión de PyTorch fijada por el demo ofrece la distribución de macOS para ARM64. [Archivos de PyTorch 2.6.0](https://pypi.org/project/torch/2.6.0/#files).

1. Abre MAMP y pulsa **Start**. Desde la copia limpia crea el entorno de la API y la configuración.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python configurar.py
.venv/bin/python configurar_mysql.py
.venv/bin/python verificar_mysql.py
```

En MAMP confirma la versión y el puerto de MySQL, que suele ser `8889`. Usa las credenciales administrativas de tu instalación para crear las bases. Para la cuenta nueva de Qwerty acepta `demo_documental` o elige un nombre que empiece con `demo_`. Al terminar, `verificar_mysql.py` debe encontrar tres préstamos ficticios.

Si ya existen las bases de MAMP y quieres reutilizarlas, restaura los archivos privados `.env.mysql` y `.env.sources` de la instalación de origen. Para una instalación independiente elige bases y usuarios nuevos en el asistente. El instalador conserva las bases existentes.

2. Prepara PostgreSQL y el entorno de Open WebUI.

```sh
.venv/bin/python configurar_postgresql.py --port 55442
.venv/bin/python gestionar_demo.py detener
python3.11 -m venv .venv_webui
.venv_webui/bin/python -m pip install -r requirements-webui.txt
```

El configurador inicia PostgreSQL para crear la cuenta y verificar el acceso. El segundo comando cierra esa instancia inicial para que el lanzador de uso diario pueda registrarla en macOS. Si `55442` está ocupado, elige otro puerto libre durante la configuración. Conserva las claves pendientes en `.env.postgresql_setup.json` si la preparación se interrumpe.

3. Abre Ollama y ejecuta `ollama pull qwen3:1.7b`. Puedes dejarlo abierto. Qwerty reutiliza la instancia que responda en `OLLAMA_URL`, normalmente `http://127.0.0.1:11434`. Si el puerto lo ocupa otro programa, elige un puerto local libre y configura Ollama y Qwerty con ese mismo puerto. El modelo de búsqueda se descarga al procesar el primer documento. [Instalación de Ollama en macOS](https://docs.ollama.com/macos)

4. Ejecuta `./iniciar_demo.sh`, abre la URL que imprime y crea tu cuenta administradora. Registra el conector una vez con el acceso de esa cuenta.

```sh
.venv/bin/python conectar_openwebui.py
```

Confirma las direcciones que propone el script. La plantilla usa `3187` para el chat y `18129` para la API. Si necesitas otros puertos, define `UI_PORT` y `API_PORT` en `.env` y verifica los valores antes de registrar el conector. Abre un chat nuevo y selecciona **Qwerty**. Pregunta **¿Cuántos préstamos tiene Ana?**. Después adjunta `datos/politicas.txt`, envía `/cargar` y pregunta **¿Cuántos préstamos se permiten por persona?**.

Si macOS indica que el script no tiene permiso de ejecución después de extraer el ZIP, ejecuta `chmod +x iniciar_demo.sh detener_demo.sh estado_demo.sh` desde esta carpeta.

## Actualizar dependencias

```sh
./detener_demo.sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
.venv_webui/bin/python -m pip install -r requirements-webui.txt
.venv_webui/bin/python -m pip check
./iniciar_demo.sh
```

Conserva los dos entornos separados. Respalda el historial y la configuración antes de actualizar Open WebUI o PostgreSQL. Las versiones requeridas están en los archivos `requirements`.

Para construir el proyecto desde el código sigue [README_CONSTRUCCION.md](../README_CONSTRUCCION.md). Para preparar una copia limpia en Windows sigue [README_WINDOWS.md](../README_WINDOWS.md).
