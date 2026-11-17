"""Ejecutar con Python 3.12 y RAGParity instalado; recibe un export privado como archivo."""
import json,sys
from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import Record
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.sources import MemorySource
payload=json.load(open(sys.argv[1]))
result=ConsistencyChecker().check(MemorySource([Record(**r) for r in payload['source']]),MemoryIndex([Record(**r) for r in payload['index']]))
print(result.model_dump_json(indent=2))
