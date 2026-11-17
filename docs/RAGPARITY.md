# Auditoría independiente

El endpoint privado GET /audit/export devuelve el manifiesto esperado y el inventario actual para el usuario autenticado. Conserva ese JSON localmente y no lo envíes a otros usuarios.

Con Python 3.12 o posterior, instala RAGParity desde una distribución verificada o su repositorio oficial. No lo añadas a ciegas al entorno Python 3.11 del chatbot. Ejecuta:

```sh
python audit_ragparity.py audit_export.json
```

Se comprobó la biblioteca real con revisión 838ab2845c8c5209427922867e32d581cb070db1. El inventario válido dio PASS y una copia con desfase deliberado dio FAIL. Los hashes se calculan desde las fuentes antes de la ingestión y se recalculan al exportar los fragmentos almacenados. Esa comparación no certifica la verdad ni la relevancia de una respuesta.
