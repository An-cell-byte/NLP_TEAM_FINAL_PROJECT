# Preguntas frecuentes de Qwerty

Esta guía explica cómo incorporar fuentes, dar acceso a más personas y personalizar el demo. Para instalarlo y hacer las primeras pruebas, abre el [README de macOS](./README.md) o el [README de Windows](./README_WINDOWS.md).

## ¿Dónde pongo los archivos que quiero consultar?

Guárdalos donde te resulte práctico. La carpeta `datos/` contiene los ejemplos del demo. Para que el asistente lea un archivo, adjúntalo en un chat con **Qwerty** y envía `/cargar`. El servicio procesa el contenido y lo deja disponible para tu cuenta. Puedes preguntar en cuanto termine la carga, sin reiniciar.

Puedes cargar TXT, PDF con texto seleccionable, Excel en formato XLSX, CSV y JSON. Prueba con `datos/politicas.txt` y pregunta **¿Cuánto dura el préstamo?**. Abre la referencia que acompaña la respuesta para comprobar los siete días naturales.

## ¿Cómo actualizo un archivo ya cargado?

Escribe `/documentos` para localizar su identificador. Adjunta la versión nueva y envía `/sustituir ID`, cambiando `ID` por el que te mostró el chat. Espera la confirmación y repite la pregunta. El asistente consulta la versión nueva sin reiniciar. Si el archivo nuevo falla, puedes seguir consultando la versión anterior y volver a intentar el reemplazo con un archivo válido.

## ¿Puedo agregar tablas de MySQL?

Sí. El chatbot consulta únicamente las tablas y vistas que el administrador autoriza. Una vista permite exponer un conjunto concreto de filas y columnas. Por ejemplo, `prestamos_detalle` reúne los préstamos y los nombres de los usuarios de Aurora.

1. Prepara una tabla o vista con los campos que quieres consultar y concede permiso `SELECT` a una cuenta lectora.
2. Agrega la tabla o vista y las columnas permitidas a `SOURCE_CONNECTIONS` en `.env.sources`. Si es otra base, configura también el alias, su conexión privada y las cuentas autorizadas.
3. Reinicia el demo para que FastAPI lea la configuración. Prueba con una cuenta autorizada y verifica el resultado en MySQL.

Para las preguntas en lenguaje natural, menciona MySQL y el nombre de la vista cuando haya varias. El intérprete de `natural_mysql.py` está preparado para el vocabulario de Aurora. Si incorporas otro tema, puedes adaptar sus reglas y probar las nuevas preguntas. El comando `/calcular` permite indicar de forma explícita la fuente, la operación y las columnas. [Configuración de fuentes de lectura](./docs/BASES_DE_DATOS.md) y [ejemplos de uso](./docs/USO.md).

## ¿Tengo que reiniciar si agrego filas a las tablas actuales?

Guarda los cambios en MySQL y envía una pregunta nueva. El chatbot vuelve a consultar `prestamos_detalle`, así que las filas que aparezcan en esa vista se reflejan sin reiniciar. Por ejemplo, si Ana tiene dos préstamos y agregas un tercero vinculado a su usuario, el siguiente conteo dará tres. Si agregas columnas o cambias qué fuente se puede consultar, revisa la configuración de acceso y reinicia después de editarla.

## ¿Puedo cambiar el nombre o el logo?

En el **Panel de administración**, abre **Ajustes / Modelos** y edita **Qwerty**. Ahí puedes cambiar el nombre y el ícono que aparecen en el selector del chat. Conserva el identificador interno `pln_documental` para que el conector siga asociado al modelo. [Editor de modelos](https://docs.openwebui.com/features/workspace/models/).

El título y el logo de la interfaz pertenecen a Open WebUI. El ajuste `WEBUI_NAME` se aplica al iniciar y añade «(Open WebUI)» al nombre configurado. Antes de personalizar el título general o sustituir el logo oficial, revisa las condiciones de marca. Para un grupo de clase puedes usar un ícono propio en el asistente y conservar la identidad de la interfaz. [Ajuste del título](https://docs.openwebui.com/reference/env-configuration/#webui_name) y [política de marca](https://docs.openwebui.com/license/).

## ¿Puedo tener más de 50 usuarios? ¿Cuándo tiene un costo?

Sí. Puedes dar acceso a más de 50 personas en una instalación interna de Open WebUI sin pagar una licencia por usuario si conservas el nombre y el logo oficiales. La excepción de 50 se refiere a modificar la marca. Cuenta personas con acceso directo en cualquier periodo móvil de 30 días. Si superas ese número y quieres sustituir la marca, necesitas permiso previo por escrito de Open WebUI o una licencia empresarial que autorice el cambio. La licencia empresarial se cotiza con el proveedor. [Licencia de la versión 0.12.5](https://github.com/open-webui/open-webui/blob/v0.12.5/LICENSE) y [opciones empresariales](https://docs.openwebui.com/enterprise/).

En este demo, Ollama ejecuta el modelo de forma local. Si alojas el demo para todo el grupo, considera los recursos del equipo o el costo de hospedar los servicios. La cantidad de cuentas y la cantidad de consultas simultáneas se comprueban por separado.

## ¿Cómo doy acceso a todo el grupo?

1. Desde el panel de administración de Open WebUI, crea o aprueba las cuentas con el rol de usuario. En **Ajustes / Modelos**, edita **Qwerty** y concede acceso a los usuarios o al grupo correspondiente. Prueba con una cuenta de alumno que pueda seleccionar el asistente, cargar un archivo y consultar los datos ficticios de Aurora. [Guía para compartir Open WebUI](https://docs.openwebui.com/getting-started/sharing/).
2. Si cada alumno ejecuta su copia, usa la guía de instalación de su sistema. Si todos van a usar una sola instancia, la dirección `127.0.0.1` de este demo solo funciona en el equipo que lo ejecuta. Para compartirla, instala el demo en un equipo accesible por una red institucional o VPN. Expón la interfaz mediante HTTPS y mantén FastAPI, Ollama y las bases de datos detrás de la interfaz.
3. Antes de abrir el acceso al grupo completo, prueba varias consultas simultáneas con datos ficticios. Mide el tiempo de respuesta y revisa memoria y CPU. Usa dos cuentas para comprobar que cada persona ve sus propios documentos. En macOS el lanzador usa Ollama en `127.0.0.1`. Para atender a más personas puedes instalar el demo completo en un equipo institucional con más recursos y repetir las pruebas. [Conexión con Ollama](./docs/PUENTE.md#conectar-ollama-local).
