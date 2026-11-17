"""Prepara los archivos de Open WebUI y arranca la interfaz."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


D = Path(__file__).resolve().parent


def environment():
    base = dotenv_values(D / '.env')
    config = dotenv_values(D / '.env.webui')
    if not config.get('WEBUI_DATABASE_URL'):
        raise RuntimeError('Prepara PostgreSQL antes de iniciar Open WebUI. Consulta docs/INSTALACION.md.')
    package = importlib.util.find_spec('open_webui')
    if package is None or package.origin is None:
        raise RuntimeError('Instala requirements-webui.txt en el entorno de Open WebUI.')

    data = (D / (config.get('WEBUI_DATA_DIR') or '.runtime/webui')).resolve()
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    port = base.get('UI_PORT', '3187')
    url = 'http://127.0.0.1:' + port
    return {
        **os.environ,
        'DATABASE_URL': config['WEBUI_DATABASE_URL'],
        'WEBUI_SECRET_KEY': base['WEBUI_SECRET_KEY'],
        'DATA_DIR': str(data),
        'STATIC_DIR': str(data / 'static'),
        'FRONTEND_BUILD_DIR': str(Path(package.origin).parent / 'frontend'),
        'OLLAMA_BASE_URL': base.get('OLLAMA_URL', 'http://127.0.0.1:11434'),
        'ENABLE_OLLAMA_API': 'false',
        'DEFAULT_MODELS': 'pln_documental',
        'ENABLE_OPENAI_API': 'false',
        'ENABLE_VERSION_UPDATE_CHECK': 'false',
        'RAG_EMBEDDING_MODEL_AUTO_UPDATE': 'false',
        'ENABLE_EVALUATION_ARENA_MODELS': 'false',
        'DO_NOT_TRACK': 'true',
        'ANONYMIZED_TELEMETRY': 'false',
        'SCARF_NO_ANALYTICS': 'true',
        'HF_HOME': os.getenv('HF_HOME', str(D / '.runtime/huggingface')),
        'ENV': 'prod',
        'CORS_ALLOW_ORIGIN': url + ';http://localhost:' + port,
        'WEBUI_URL': url,
    }


def relocate_uploads(env):
    """Recupera adjuntos locales guardados con la ruta anterior del demo."""
    from sqlalchemy import create_engine, inspect, text

    uploads = (Path(env['DATA_DIR']) / 'uploads').resolve()
    if env.get('STORAGE_PROVIDER', 'local') != 'local' or not uploads.is_relative_to(D) or not uploads.is_dir():
        return
    relative_uploads = uploads.relative_to(D)
    prefix_length = len(relative_uploads.parts)
    engine = create_engine(env['DATABASE_URL'], hide_parameters=True)
    try:
        with engine.begin() as connection:
            if not inspect(connection).has_table('file'):
                return
            rows = connection.execute(text('SELECT id, path FROM "file" WHERE path IS NOT NULL')).all()
            for file_id, stored_path in rows:
                previous = Path(stored_path)
                if not previous.is_absolute() or previous.parts[-prefix_length - 1:-1] != relative_uploads.parts:
                    continue
                current = uploads / previous.name
                if not current.is_file() or not current.resolve().is_relative_to(uploads):
                    continue
                connection.execute(
                    text('UPDATE "file" SET path = :current WHERE id = :id AND path = :previous'),
                    {'current': current.relative_to(D).as_posix(), 'id': file_id, 'previous': stored_path},
                )
    finally:
        engine.dispose()


def configure_chat(env):
    """Aplica la selección del demo a una instalación que ya guarda ajustes."""
    from sqlalchemy import JSON, column, create_engine, inspect, table, update

    engine = create_engine(env['DATABASE_URL'], hide_parameters=True)
    try:
        with engine.begin() as connection:
            schema = inspect(connection)
            if not schema.has_table('config'):
                return
            if not {'key', 'value'} <= {item['name'] for item in schema.get_columns('config')}:
                return
            settings = table('config', column('key'), column('value', JSON))
            preferences = {'ollama.enable': False, 'ui.default_models': env['DEFAULT_MODELS']}
            for key, value in preferences.items():
                connection.execute(update(settings).where(settings.c.key == key).values(value=value))
    finally:
        engine.dispose()


def command():
    port = os.getenv('UI_PORT', dotenv_values(D / '.env').get('UI_PORT', '3187'))
    return [sys.executable, '-c', 'from open_webui import app; app()', 'serve', '--host', '127.0.0.1', '--port', port]


if __name__ == '__main__':
    os.chdir(D)
    env = environment()
    relocate_uploads(env)
    configure_chat(env)
    args = command()
    if sys.platform == 'win32':
        try:
            raise SystemExit(subprocess.call(args, env=env))
        except KeyboardInterrupt:
            raise SystemExit(0)
    os.execve(args[0], args, env)
