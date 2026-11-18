"""Responde una solicitud desde la terminal.

Uso:
    python scripts/responder.py "¿Cuántas sesiones puedo tener abiertas al mismo tiempo?"
    python scripts/responder.py "texto" --json
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore", category=FutureWarning)

from soporte_pln.api import cargar_sistema  # noqa: E402
from soporte_pln.sistema import format_result  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Mesa de ayuda con evidencia")
    parser.add_argument("texto", nargs="+", help="solicitud del usuario")
    parser.add_argument("--json", action="store_true", help="imprimir el resultado completo en JSON")
    parser.add_argument("--sin-registro", action="store_true", help="no escribir registros/consultas.jsonl")
    args = parser.parse_args()
    registro = None if args.sin_registro else ROOT / "registros" / "consultas.jsonl"
    result = cargar_sistema(registro=registro).responder(" ".join(args.texto))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_result(result))


if __name__ == "__main__":
    main()
