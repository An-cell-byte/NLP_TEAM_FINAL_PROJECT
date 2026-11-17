#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Prepara .venv como indica README.md."
  exit 1
fi
exec .venv/bin/python gestionar_demo_mac.py iniciar
