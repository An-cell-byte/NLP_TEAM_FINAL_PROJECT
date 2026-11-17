# Conexión de la interfaz con la API

Open WebUI y FastAPI se ejecutan en el mismo equipo. `conectar_openwebui.py` registra el conector **Qwerty** y guarda la dirección de FastAPI. La plantilla usa `http://127.0.0.1:18129`. Si cambiaste el puerto, confirma el valor de `API_PORT` en `.env`.

El puente recibe la identidad de la cuenta, firma la solicitud con BRIDGE_SECRET y llama a la API. La API verifica la firma y el propietario antes de consultar documentos o fuentes. El navegador no recibe las contraseñas de MySQL.

El chat muestra el resultado. FastAPI guarda la vista, los filtros y el identificador de la consulta para poder revisarlos después.

## Conectar Ollama local

Open WebUI envía la pregunta a FastAPI por el conector **Qwerty**. FastAPI llama a Ollama cuando necesita interpretar la pregunta o redactar con evidencia. Mantén desactivada la conexión directa de Ollama en Open WebUI. Así el chat pasa por las fuentes del demo.

### En macOS

Descarga `qwen3:1.7b` desde Ollama en la primera instalación. Desde la carpeta del demo, revisa estos valores de ejemplo en `.env`.

```dotenv
OLLAMA_URL=http://127.0.0.1:11434
GENERATION_MODEL=qwen3:1.7b
```

Abre MAMP y pulsa **Start**. Después inicia el demo y consulta la lista de modelos.

```sh
./iniciar_demo.sh
curl -fsS http://127.0.0.1:11434/api/tags
```

### En Windows

Abre Ollama desde Inicio y descarga el modelo una vez.

```powershell
ollama pull qwen3:1.7b
(Invoke-RestMethod "http://127.0.0.1:11434/api/tags").models.name
```

Configura `.env` con la dirección de esa instancia.

```dotenv
OLLAMA_URL=http://127.0.0.1:11434
GENERATION_MODEL=qwen3:1.7b
```

Cuando las bases estén en marcha, inicia el demo con `.\iniciar_demo.cmd` desde PowerShell. El lanzador puede usar Ollama si ya está abierto. [Instalación en Windows](../README_WINDOWS.md)

### Comprueba la conexión

En ambos sistemas, `/api/tags` debe incluir `qwen3:1.7b`. Si el puerto es distinto, usa el valor de `OLLAMA_URL` al hacer la prueba. Después de editar `.env`, detén y vuelve a iniciar el demo para que FastAPI cargue los cambios. [Lista de modelos de Ollama](https://docs.ollama.com/api/tags)

Para comprobar el recorrido completo, abre un chat nuevo con **Qwerty** y pregunta **¿Cuántos préstamos tiene Ana?**. FastAPI consulta MySQL y devuelve **2 préstamos**. La frase puede variar al repetir la pregunta. La prueba de `/api/tags` comprueba Ollama por separado.
