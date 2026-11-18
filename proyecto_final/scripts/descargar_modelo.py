"""Descarga MiniLM multilingüe (revisión fijada) a models/minilm. Solo se necesita una vez.

Uso:
    python scripts/descargar_modelo.py               # descarga desde Hugging Face
    python scripts/descargar_modelo.py --desde RUTA  # copia una carpeta local ya descargada
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from soporte_pln.encoder import DEFAULT_PATH, MODEL_ID, REVISION  # noqa: E402

FILES = ["modules.json", "config.json", "config_sentence_transformers.json", "sentence_bert_config.json",
         "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
         "sentencepiece.bpe.model", "unigram.json", "1_Pooling/config.json"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", help="carpeta local con el mismo modelo")
    parser.add_argument("--destino", default=str(DEFAULT_PATH))
    args = parser.parse_args()
    target = Path(args.destino)
    if args.desde:
        for name in FILES:
            source = Path(args.desde) / name
            if source.is_file():
                (target / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target / name)
    else:
        from huggingface_hub import snapshot_download
        snapshot_download(MODEL_ID, revision=REVISION, local_dir=target, allow_patterns=FILES)
    missing = [n for n in ["modules.json", "model.safetensors", "tokenizer.json"] if not (target / n).is_file()]
    if missing:
        raise SystemExit(f"Faltan archivos del modelo: {missing}")
    print(f"Modelo listo en {target} (revisión {REVISION[:10]})")


if __name__ == "__main__":
    main()
