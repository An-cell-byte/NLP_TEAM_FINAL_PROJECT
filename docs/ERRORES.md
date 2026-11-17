# Diagnóstico

Ejecuta `./estado_demo.sh` desde la carpeta del demo. Muestra qué servicios están registrados en macOS y si MySQL responde.

| Síntoma | Qué revisar |
| --- | --- |
| Open WebUI no abre | Abre MAMP, pulsa **Start** y ejecuta `./iniciar_demo.sh`. Comprueba la dirección que imprime. |
| MySQL no responde en 8889 | Comprueba que MAMP use MySQL 8. Revisa el puerto en MAMP y en `.env.mysql`. |
| Un puerto está ocupado | Comprueba qué instalación está activa. Detén esa copia con su propio comando de cierre o elige otro puerto para la instalación nueva. |
| PostgreSQL no inicia | Consulta `.runtime/postgresql.log`. El lanzador busca la versión de PostgreSQL que corresponde a los datos. Si lo instalaste en otra ubicación, indica su carpeta `bin` en `PG_BIN`. |
| Moviste la carpeta | Apaga el demo antes de moverlo. Incluye `.runtime` y los archivos ocultos de configuración al trasladarlo. |
| Ollama no responde | Comprueba `OLLAMA_URL` en `.env` y abre `/api/tags` en esa dirección. La lista debe incluir `qwen3:1.7b`. Si Qwerty inició el proceso, revisa `.runtime/modelo.log`. |
| El chat falla al consultar | Consulta `.runtime/webui.log` y `.runtime/api.log`. El conector debe apuntar al `API_PORT` de `.env` en `127.0.0.1` y utilizar la clave del puente de esa instalación. |
| Un chat anterior respondía con qwen3 | Recarga Open WebUI y abre un chat nuevo con **Qwerty**. La interfaz ofrece el conector y FastAPI usa Ollama por dentro. |
| La lista de modelos está vacía | En una copia nueva, registra el conector con `conectar_openwebui.py`. Consulta la guía de instalación de tu sistema. |
| Un reemplazo falla | Puedes seguir consultando la versión que ya estaba disponible. Adjunta un archivo válido y vuelve a enviar `/sustituir ID`. |

Para reiniciar los servicios de esta carpeta, ejecuta `./detener_demo.sh` y después `./iniciar_demo.sh`. Los registros quedan en `.runtime/`. Comparte únicamente el mensaje de error pertinente y omite valores de los archivos `.env`.
