# Ficha de datos

Todos los datos son **ficticios**, sin información personal real, y su uso está autorizado.

| Archivo | Origen y autorización | IDs | Particiones | Uso |
|---|---|---|---|---|
| `solicitudes.csv` | Material del curso (Clases 7-10 y Actividad 3), copiado **sin cambios**. SHA-256 `923d4fd2…eb099f`. | `S001`-`S144`, 48 familias | train 96 / validation 24 / test 24 (8/2/2 familias por clase) | Clasificación (4 clases) |
| `fuera_de_alcance.csv` | Redactado por el equipo (CC0-1.0, `origin = sintético equipo`). Usa las mismas tres plantillas de redacción que el CSV original. | `F001`-`F036`, 12 familias `fuera_XX` | train 24 / validation 6 / test 6 | Quinta clase `fuera_de_alcance` |
| `base_conocimiento/*.md` | 15 artículos de la mesa de ayuda ficticia *Cumbre Digital*, redactados por el equipo (CC0-1.0). Cada uno lleva metadatos `id`, `titulo`, `categoria`, `version`, `fecha`, `autoria` y `licencia`. | Pasaje = sección `##`, con ID `DOC-ID#sN` (80 pasajes) | No se divide; es el corpus de búsqueda | Recuperación y citas |
| `consultas_dev.json` | Redactado por el equipo. | `dev-01`…`dev-32` | Desarrollo (24 con respuesta y 8 sin evidencia) | Elegir el recuperador y calibrar la puerta |
| `consultas_test_v1.json` | Redactado por el equipo. Fue la primera prueba, se usó **una vez** y quedó retirada. | `test-01`…`test-20` | Desarrollo desde su retiro (15/5) | Calibración de la iteración 2 |
| `consultas_test.json` | Redactado por el equipo **antes** de diseñar la iteración 2. Su huella está en `registro_particiones.json`. | `test2-01`…`test2-20` | **Prueba vigente** (15 con respuesta y 5 sin evidencia) | Reporte final |
| `sinonimos.json` | Equivalencias del dominio construidas solo con fallos de desarrollo. | — | — | Intento de mejora descartado (iteración 2) |

## Reglas

* Una familia de solicitudes, es decir, una misma petición en tres redacciones, aparece en una sola partición. `validate_splits` comprueba que no haya fugas por familia ni por texto idéntico.
* Cada consulta indica `relevant`, la lista de pasajes que la responden, y `answerable`. Las consultas sin evidencia tienen `relevant = []`.
* Ninguna consulta de prueba se repite en desarrollo ni en la prueba retirada (lo comprueba `tests/test_datos.py`).
* El tamaño de la base es de 4,412 palabras en el cuerpo de los pasajes, o 5,050 contando títulos y encabezados.
