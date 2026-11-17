# Consultar documentos

Abre un chat con **Qwerty**. Adjunta un archivo con **Upload Files** y escribe `/cargar`. Cuando quede disponible, puedes preguntar por su contenido. Usa `/documentos` para ver tus archivos y sus identificadores.

Si falta **Qwerty**, registra el conector como indica la guía de [macOS](./INSTALACION.md) o [Windows](../README_WINDOWS.md). En una instalación compartida, pide al administrador acceso al modelo. Después recarga la página y abre un chat nuevo.

Usa `/purgar ID` para solicitar el borrado de un documento, sus adjuntos registrados y las respuestas que lo citan en MySQL. Qwerty te dará un comando de confirmación. Para un documento cargado con un conector anterior, consulta el [procedimiento manual y la verificación en MySQL](../README_CONSTRUCCION.md#borrar-un-archivo-y-sus-citas-del-demo).

## Formatos y ubicación de la evidencia

| Formato | Qué conservamos | Cómo verificarlo |
| --- | --- | --- |
| TXT Unicode UTF-8 | Texto y líneas, con posición de palabras | Abre la referencia y consulta location.line_start y line_end |
| PDF con texto | Página real y posición de palabras | Contrasta el fragmento con esa página del archivo |
| XLSX | Hojas, encabezados, filas, tipos y celdas de origen | Revisa sheet, row y range |
| CSV UTF-8 | Encabezados, filas, columnas y tipos | Revisa row y columns; el encabezado es la fila 1 |
| JSON | Campos anidados y listas sin repetir cada rama completa | Revisa path: $ es la raíz, [0] el primer elemento |

XLS y XLSM no están habilitados. Exporta una copia XLSX sin macros. No ejecutamos macros ni fórmulas. Para una fórmula Excel se utiliza su resultado guardado, si existe; sin ese resultado queda un valor ausente y una advertencia. Un PDF escaneado necesita reconocimiento óptico de caracteres, OCR, antes de cargarlo. No se ha incorporado OCR automático.

## Cargar una hoja o un CSV

Con biblioteca.xlsx adjunto, escribe /cargar hoja=Prestamos. Para nombres con espacios utiliza /cargar "hoja=Mi hoja". Sin selección se procesan las hojas dentro de los límites. /estructura ID muestra hojas, conjuntos de datos disponibles, columnas y advertencias. Cada carga tiene su propio ID; reemplaza ID por el valor recibido, sin comillas adicionales.

El separador CSV se detecta entre coma, punto y coma, tabulador y barra vertical. Para especificar punto y coma y coma decimal: /cargar separador=; decimal=,. Se admite UTF-8 con o sin marca inicial BOM. Los identificadores como 001 se conservan como texto. Las fechas ISO se reconocen; otras fechas quedan como texto para evitar interpretar día y mes de manera incorrecta. No se adivinan separadores de miles.

## Preguntas sobre el contenido

Carga datos/politicas.pdf o datos/politicas.txt y pregunta: ¿Cuánto dura el préstamo? Con politicas.txt también puedes consultar: ¿Cuándo se permite la renovación? Abre el botón de la fuente y revisa el fragmento. /fuente ID_FRAGMENTO permite comprobar que la fuente sigue vigente y pertenece a tu cuenta.

Para buscar contenido de prestamos.csv, prueba PLN aplicado y verifica el registro citado. Para consultar una fila concreta utiliza /calcular con operation=rows y un filtro sobre id. Una pregunta como ¿Qué libro corresponde al identificador 1? puede producir abstención porque el filtro léxico no reconoce todas las paráfrasis. En biblioteca.json revisa las rutas de los campos y utiliza /calcular para listas tabulares. La búsqueda puede devolver varios registros parecidos; verifica los identificadores antes de concluir.

Para comparar fuentes, carga los documentos y pregunta por la misma condición en ambos. Las referencias permiten contrastar lo que dice cada uno. Si se contradicen, no elijas una versión solo por su puntuación de búsqueda. Comprueba fecha, versión y autoridad del documento. El sistema no certifica automáticamente cuál es verdadero. Una pregunta sin información disponible, por ejemplo ¿Cuál es el clima en Marte?, debe producir una abstención.

## Cálculos que podemos comprobar

Una suma no debe hacerse sobre los pocos fragmentos recuperados para redactar una respuesta. /calcular opera sobre todas las filas autorizadas de la tabla seleccionada. Por eso los cálculos requieren un comando estructurado: no ofrecemos traducción libre de preguntas a SQL.

Después de cargar prestamos.csv, usa /estructura ID. El conjunto de ese CSV se llama datos. Sustituye ID por su identificador:

/calcular {"document_id":"ID","dataset":"datos","operation":"sum","column":"importe"}

/calcular {"document_id":"ID","dataset":"datos","operation":"mean","column":"importe"}

/calcular {"document_id":"ID","dataset":"datos","operation":"count"}

/calcular {"document_id":"ID","dataset":"datos","operation":"rows","filters":[{"column":"usuario_id","op":"eq","value":10}]}

En Excel cambia dataset por Prestamos. En el JSON de demostración utiliza "dataset":"$[\"prestamos\"]". También existen min y max. Los filtros admiten eq (igual), ne (distinto), gt (mayor), ge (mayor o igual), lt (menor) y le (menor o igual).

El chat presenta el resultado en una frase o una tabla. `count` cuenta filas. `mean` usa los valores numéricos presentes y deja fuera los que faltan. Si no hay valores disponibles, el chat lo indica. El importe de la demostración está expresado en pesos ficticios. `rows` muestra hasta 100 registros. La API conserva los filtros y las ubicaciones para revisar el cálculo.

## Preguntas normales sobre MySQL

Pregunta **¿Cuántos préstamos tiene Ana?**. El chat puede decir **Ana tiene 2 préstamos** o **Encontré 2 préstamos de Ana**. Si después preguntas **¿Y Luis?**, el resultado es **1 préstamo**. Pide **Muestra los préstamos de Ana** para ver el detalle en una tabla. FastAPI calcula con las filas autorizadas de Aurora. Cuando las reglas no bastan, Ollama propone una interpretación. Si no se puede validar, el chat pide que aclares la pregunta.

Los siguientes comandos siguen disponibles para comprobaciones específicas. Las preguntas naturales de esta versión se aplican a MySQL; los cálculos sobre archivos conservan /calcular.

## Consultas a bases autorizadas

El administrador debe configurar primero las fuentes siguiendo docs/BASES_DE_DATOS.md. En el chat no se escriben contraseñas ni cadenas de conexión. /conectar aurora_mamp registra un alias autorizado para tu identidad. /conexiones muestra sus IDs y las vistas permitidas.

/calcular {"connection_id":"ID_CONEXION","dataset":"prestamos_detalle","operation":"sum","column":"importe"}

/calcular {"connection_id":"ID_CONEXION","dataset":"prestamos_detalle","operation":"rows","filters":[{"column":"usuario_id","op":"eq","value":10}]}

Estas consultas son en vivo: source.queried_at indica el momento UTC. No se indexa ni se conserva el contenido de la base como documento. En cambio, un archivo cargado es una instantánea con versión; hay que sustituirlo para actualizarlo. Para comparar dos fuentes, ejecuta el mismo cálculo, con los mismos filtros y columnas, en cada una y compara sus resultados y fechas.

/revocar ID_CONEXION invalida tu registro. El administrador puede retirar un alias o tu autorización en la política del servidor y reiniciar la API. No se permite SQL libre ni escrituras.

## Sustituir, eliminar y conservar el historial

Adjunta el archivo nuevo y escribe /sustituir ID, con las opciones de hoja o decimal si hacen falta. Se genera una nueva versión y se retiran los fragmentos anteriores de las búsquedas. /eliminar ID retira el documento. Las citas antiguas que aparecen en conversaciones son evidencia histórica; /fuente comprueba la vigencia actual. /auditar contrasta el inventario de fragmentos con el manifiesto de la carga; no verifica la verdad del contenido.

Las carpetas internas las crean los servicios. No prepares directorios manualmente para subir archivos.

## Límites

Por defecto: 5 MB por archivo, 100 páginas PDF, 20 hojas Excel, 5000 filas totales por archivo, 200 columnas, 1000 fragmentos, profundidad JSON 20, 10000 caracteres por celda y 40 MB de contenido XLSX expandido. Los límites principales se configuran en el servidor; también se comprueban durante el procesamiento. La función de Open WebUI tiene un máximo adicional de 5 MB. Para aumentarlo deben revisarse ambos controles y los recursos disponibles.
