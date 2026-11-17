# Arquitectura local

Open WebUI guarda las cuentas, los permisos y las conversaciones en PostgreSQL. Los adjuntos quedan en `.runtime/webui/uploads`. La interfaz usa su propio entorno de Python.

openwebui_pipe.py firma la identidad y llama a FastAPI. app.py verifica esa firma y decide si la pregunta corresponde a documentos o a una fuente MySQL. La API utiliza MySQL de MAMP para su evidencia y sus respuestas. La cuenta lectora de Aurora consulta únicamente prestamos_detalle.

`natural_mysql.py` interpreta las preguntas habituales con reglas. Para otras formulaciones, Ollama propone un plan. La API lo valida y `tabular.py` calcula el resultado sobre las filas autorizadas. Las preguntas sobre el límite de préstamos por persona se buscan en los documentos.

`readers.py` extrae documentos conservando su ubicación. Sentence Transformers produce las representaciones numéricas que se guardan en MySQL. En el ZIP, `exercises.py` muestra búsqueda por palabras y respuestas extractivas. La ampliación corresponde a E1 y E2.

Las guías indican puertos de ejemplo. Consulta `.env`, `.env.mysql` y `.env.webui` para ver los de tu instalación. `gestionar_demo_mac.py` registra los procesos propios en `launchd`. Las definiciones quedan en `.runtime/launchd` y los registros en `.runtime`.

Las rutas de `.env.webui` parten de la carpeta del demo. `launchd` necesita la ubicación completa de cada servicio. El lanzador la calcula al iniciar y regenera las definiciones si la carpeta se movió.
