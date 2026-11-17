# Conexiones de MySQL y fuentes de lectura

La ruta MAMP se prepara con configurar_mysql.py y se comprueba con verificar_mysql.py. La conexión principal de la aplicación está en .env.mysql. El alias aurora_mamp está en .env.sources y utiliza una cuenta distinta, de solo lectura. /conectar aurora_mamp devuelve un ID privado para utilizar /calcular. El README contiene todos los pasos y ejemplos.

No utilices la cuenta principal de la aplicación para consultar datos externos. La base demo_documental guarda la infraestructura; demo_documental_aurora contiene exclusivamente los datos ficticios proporcionados. Para otras fuentes se aplica la política de esta guía.

# Bases de datos de lectura

PostgreSQL y MySQL se consultan con SQLAlchemy; psycopg y PyMySQL son sus controladores. Un controlador permite que Python se comunique con el motor. El código no usa las credenciales administrativas de la aplicación para leer fuentes externas.

## Preparar una fuente

Pide al administrador una cuenta con SELECT únicamente sobre las vistas o tablas necesarias. En PostgreSQL concede CONNECT a la base, USAGE al esquema y SELECT a la vista; configura default_transaction_read_only=on. En MySQL concede SELECT sobre la vista concreta. No se necesita SHOW VIEW: las columnas se definen en la política. Revoca privilegios heredados y comprueba las restricciones con esa cuenta. No utilices cuentas personales o administrativas para el chat.

Para practicar, crea una base vacía y exclusiva de demostración en cada motor. Ejecuta el esquema datos/aurora_postgresql.sql o datos/aurora_mysql.sql con una cuenta administradora únicamente en esa base nueva. Esos archivos preparan dos tablas relacionadas y una vista. No crean ni cambian usuarios. No los ejecutes sobre una base existente con datos reales.

Crea después un usuario lector y concede SELECT a prestamos_detalle. En MySQL, limita además el host autorizado del usuario a la red del backend. Las pruebas de esta revisión usaron bases nuevas con usuarios lectores separados. Las credenciales generadas quedaron fuera de la distribución.

## Configurar el servidor

`configurar.py` prepara `.env.sources` vacío si no existe. Conserva este archivo privado. La API lo carga mediante `iniciar_api.py`. Este ejemplo usa valores de muestra que debes sustituir por los de tu base y tu cuenta de Open WebUI.

```dotenv
SOURCE_PG_READ_URL=postgresql+psycopg://LECTOR:CLAVE_ESCAPADA@HOST:5432/BASE_DEMO
SOURCE_MYSQL_READ_URL=mysql+pymysql://LECTOR:CLAVE_ESCAPADA@HOST:3306/BASE_DEMO
SOURCE_CONNECTIONS='{"aurora_pg":{"url_env":"SOURCE_PG_READ_URL","allowed_owners":["ID_USUARIO"],"tables":{"prestamos_detalle":["id","usuario_id","nombre","libro","importe","fecha"]}},"aurora_mysql":{"url_env":"SOURCE_MYSQL_READ_URL","allowed_owners":["ID_USUARIO"],"tables":{"prestamos_detalle":["id","usuario_id","nombre","libro","importe","fecha"]}}}'
```

Una contraseña con caracteres reservados debe codificarse para una URL. No pegues una cadena real en el chat ni en capturas. La API se ejecuta en tu Mac; 127.0.0.1 identifica el mismo equipo donde está MAMP. Los ejemplos no habilitan conexiones por sí solos.

allowed_owners contiene IDs de cuentas, no correos. Cada alias se limita a una base por su URL y a las tablas, esquemas y columnas de tables. Para otro esquema PostgreSQL usa "esquema.vista". No se admite que el usuario envíe una URL o SQL. public_demo=true habilita explícitamente un alias para todas las cuentas del servidor: úsalo solo con datos ficticios destinados a todos.

Reinicia la API después de cambiar la política. Dentro del chat, /conectar ALIAS verifica tu autorización y genera un registro privado. Conservar ese ID no permite compartir acceso: se valida el propietario en cada cálculo y se revalida la política. /revocar ID cancela ese registro. Para retirar acceso general elimina el alias, retira allowed_owners o revoca los permisos de la base; reinicia la API. Cambiar la URL o la vista actualiza la fuente sin migrar conversaciones.

## Qué ocurre durante una consulta

/calcular valida la fuente, tabla, columnas, filtros y operación. Abre una transacción de lectura y obtiene como máximo 5001 filas: si hay más de 5000, rechaza el resultado completo en vez de presentar un total parcial. Las operaciones se ejecutan sobre esas filas autorizadas con decimales exactos. Hay límites de conexión y de ejecución SQL de cinco segundos. No es un motor analítico para millones de registros; prepara una vista acotada si hace falta.

El resultado conserva alias, tabla, columnas, identificadores pertinentes y hora UTC. Los números de fila de la base son posiciones del resultado, no una identidad estable: utiliza identifiers.id para localizar el registro. No hay SQL generado por un modelo, credenciales en respuestas ni copia automática al índice vectorial. Un resultado puede cambiar entre consultas; exportar una instantánea y cargarla como archivo es una decisión explícita.

Ante error de credenciales, permisos, servicio o columna, se muestra un mensaje sin la cadena de conexión. El diagnóstico detallado corresponde al administrador local. Los permisos de solo lectura deben existir en la base además del control de la aplicación.

## Permisos mínimos de ejemplo

Estos comandos los ejecuta el administrador dentro de la base nueva. LECTOR representa una cuenta previamente creada con una contraseña privada. No se incluyen contraseñas en el ejemplo.

PostgreSQL:

```sql
GRANT CONNECT ON DATABASE BASE_DEMO TO LECTOR;
GRANT USAGE ON SCHEMA public TO LECTOR;
GRANT SELECT ON public.prestamos_detalle TO LECTOR;
ALTER ROLE LECTOR SET default_transaction_read_only=on;
```

MySQL, sustituyendo HOST_BACKEND por el host autorizado al crear la cuenta:

```sql
GRANT SELECT ON BASE_DEMO.prestamos_detalle TO 'LECTOR'@'HOST_BACKEND';
```

Estos GRANT agregan permisos; no eliminan privilegios que una cuenta ya tuviera. Utiliza una cuenta nueva y comprueba que INSERT y la lectura de tablas no autorizadas fallen. El script de datos no administra usuarios ni amplía permisos automáticamente.
