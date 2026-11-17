# Respaldo y recuperación

Conserva .env, .env.mysql, .env.sources y .env.webui en una ubicación privada. No los incluyas en paquetes públicos.

Exporta las bases del demo MySQL desde phpMyAdmin con una cuenta autorizada. En pgAdmin usa Backup sobre demo_webui con formato Custom. También puedes ejecutar pg_dump con los datos de .env.webui. Conserva una copia de WEBUI_DATA_DIR, que contiene los adjuntos. WEBUI_SECRET_KEY debe mantenerse para conservar la configuración de sesión.

Recupera primero en bases nuevas. Comprueba acceso, número de conversaciones, un mensaje anterior, un adjunto y una pregunta MySQL antes de utilizar el destino recuperado. No sobrescribas la única copia de tus datos.

## Trasladar un historial anterior

Usa la misma versión de Open WebUI en ambos sitios. Inicia la interfaz una vez para crear el esquema de PostgreSQL. Detén la interfaz y deja PostgreSQL en marcha durante la importación. Conserva la base de destino vacía.

Crea una instantánea consistente de la base SQLite anterior y conserva una copia de sus adjuntos fuera de la distribución. Copia los adjuntos al directorio uploads de WEBUI_DATA_DIR respetando sus nombres. Después ejecuta desde la carpeta del proyecto:

```sh
.venv/bin/python migrar_historial_webui.py respaldos/webui.db
```

El programa exige tablas destino vacías, copia los campos y compara las filas antes de confirmar. Conserva cuentas, hashes de acceso, mensajes y permisos; adapta únicamente las rutas locales de los adjuntos. No modifica la instantánea ni la base de origen. Si el destino tiene datos, se detiene para que elijas una base nueva.

Inicia el destino, prueba ambas cuentas y una referencia anterior. Actualiza la dirección de la API con `conectar_openwebui.py` y confirma el `API_PORT` de la instalación nueva. Conserva el origen y el respaldo hasta comprobar el nuevo entorno.
