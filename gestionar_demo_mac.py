"""Inicia el demo con launchd durante la sesión de macOS."""

import fcntl
import hashlib
import os
import plistlib
import subprocess
import sys
from urllib.parse import urlsplit

import httpx
import psutil
import psycopg
from dotenv import dotenv_values

from configurar_postgresql import find_bin
from gestionar_demo import D, RUN, StartError, model_binary, model_data, probe_api, settings, tcp, wait_for


JOBS = ("postgresql", "modelo", "api", "webui")
NAMES = dict(zip(JOBS, ("PostgreSQL", "Ollama", "FastAPI", "Open WebUI")))
DOMAIN = f"gui/{os.getuid()}"
PREFIX = "local.asistente-documental." + hashlib.sha256(os.fsencode(D)).hexdigest()[:12]


def launchctl(*args):
    return subprocess.run(["/bin/launchctl", *args], capture_output=True, text=True, timeout=45)


def target(name):
    return f"{DOMAIN}/{PREFIX}.{name}"


def plist_path(name):
    return RUN / "launchd" / f"{name}.plist"


def job_info(name):
    result = launchctl("print", target(name))
    if result.returncode:
        return ""
    if not any(line.strip() == f"path = {plist_path(name)}" for line in result.stdout.splitlines()):
        # Una etiqueta ocupada por un trabajo ajeno no autoriza detenerlo.
        raise StartError(f"La etiqueta de {name} está ocupada por otro servicio.")
    return result.stdout


def registered(name):
    return bool(job_info(name))


def unload(name):
    info = job_info(name)
    if not info:
        return
    pid = next((line.strip().removeprefix("pid = ") for line in info.splitlines() if line.strip().startswith("pid = ")), "")
    process = None
    if pid.isdigit() and int(pid) > 0:
        try:
            process = psutil.Process(int(pid))
        except psutil.NoSuchProcess:
            pass
    if launchctl("bootout", target(name)).returncode:
        raise StartError(f"macOS no pudo detener {name}. Revisa ./estado_demo.sh.")
    if process is not None:
        try:
            process.wait(timeout=35)
        except psutil.TimeoutExpired:
            raise StartError(f"{NAMES[name]} todavía está cerrando. Espera antes de volver a iniciar.") from None


def start_job(name, command, port, ready, started, timeout=45, environment=None):
    if not registered(name):
        if tcp("127.0.0.1", port):
            raise StartError(f"El puerto {port} de {name} está ocupado.")
        path = plist_path(name)
        log = RUN / f"{name}.log"
        log.touch(mode=0o600, exist_ok=True)
        path.write_bytes(plistlib.dumps({
            "Label": f"{PREFIX}.{name}",
            "ProgramArguments": [str(value) for value in command],
            "WorkingDirectory": str(D),
            "RunAtLoad": True,
            "ExitTimeOut": 30,
            "StandardOutPath": str(log),
            "StandardErrorPath": str(log),
            "EnvironmentVariables": environment or {},
        }))
        path.chmod(0o600)
        print(f"Iniciando {NAMES[name]}.", flush=True)
        result = launchctl("bootstrap", DOMAIN, str(path))
        if result.returncode:
            raise StartError(f"macOS no pudo iniciar {name}. {result.stderr.strip()}")
        started.append(name)
    if not wait_for(ready, timeout):
        raise StartError(f"{name} no respondió. Revisa .runtime/{name}.log.")


def pg_ready(web):
    try:
        with psycopg.connect(
            host=web["WEBUI_PG_HOST"], port=web["WEBUI_PG_PORT"],
            dbname=web["WEBUI_PG_DATABASE"], user=web["WEBUI_PG_USER"],
            password=web["WEBUI_PG_PASSWORD"], connect_timeout=2,
        ) as connection:
            return connection.execute("SELECT 1").fetchone() == (1,)
    except psycopg.Error:
        return False


def ui_ready(port):
    try:
        response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=3)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def start(cfg):
    mysql_port = int(os.getenv("MYSQL_PORT", "8889"))
    if not tcp(os.getenv("MYSQL_HOST", "127.0.0.1"), mysql_port):
        raise StartError(f"MySQL no responde en el puerto {mysql_port}. Abre MAMP y pulsa Start.")
    web = cfg["web"]
    data = (RUN / "postgresql").resolve()
    if (D / web.get("PG_DATA_DIR", ".runtime/postgresql")).resolve() != data or not (data / "PG_VERSION").is_file():
        raise StartError("Revisa .env.webui. La instancia PostgreSQL debe pertenecer a esta carpeta.")
    postgres = find_bin(web.get("PG_BIN"), (data / "PG_VERSION").read_text().strip()) / "postgres"
    ui_python = D / ".venv_webui/bin/python"
    if not postgres.is_file() or not ui_python.is_file():
        raise StartError("Falta PostgreSQL o el entorno de Open WebUI. Consulta README.md.")
    model_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11435").rstrip("/")
    address = urlsplit(model_url)
    if address.scheme != "http" or address.hostname != "127.0.0.1" or not address.port:
        raise StartError("Configura OLLAMA_URL con 127.0.0.1 y el puerto local en .env.")
    model = os.getenv("GENERATION_MODEL", "qwen3:1.7b")
    cache = {"HF_HOME": str(RUN / "huggingface")}
    if os.getenv("HF_HUB_OFFLINE") == "1":
        cache["HF_HUB_OFFLINE"] = "1"
    model_env = {"OLLAMA_HOST": address.netloc, "OLLAMA_NO_CLOUD": "1"}
    if (RUN / "modelos").is_dir():
        model_env["OLLAMA_MODELS"] = str(RUN / "modelos")

    started = []
    try:
        start_job("postgresql", [postgres, "-D", data.relative_to(D)], int(web["PG_PORT"]), lambda: pg_ready(web), started)
        models = model_data(model_url)
        if models is None:
            executable = model_binary()
            if not executable:
                raise StartError("Instala Ollama o abre su aplicación y revisa OLLAMA_URL en .env.")
            start_job("modelo", [executable, "serve"], address.port, lambda: model_data(model_url) is not None, started, environment=model_env)
            models = model_data(model_url) or {"models": []}
        names = {entry.get("name", entry.get("model")) for entry in models["models"] if isinstance(entry, dict)}
        if model not in names and f"{model}:latest" not in names:
            raise StartError(f"Ollama responde, pero falta {model}. En la instancia configurada ejecuta ollama pull {model}.")
        start_job("api", [sys.executable, D / "iniciar_api.py"], cfg["api_port"], lambda: probe_api(cfg), started, environment=cache)
        start_job("webui", [ui_python, D / "iniciar_webui.py"], cfg["ui_port"], lambda: ui_ready(cfg["ui_port"]), started, timeout=110, environment=cache)
    except (StartError, OSError, subprocess.TimeoutExpired):
        for name in reversed(started):
            try:
                unload(name)
            except StartError as exc:
                print(str(exc), file=sys.stderr)
        raise
    print(f"Qwerty disponible en http://127.0.0.1:{cfg['ui_port']}")


def main():
    if sys.platform != "darwin":
        raise StartError("Este comando usa launchd de macOS. En Windows consulta docs/WINDOWS.md.")
    if launchctl("print", DOMAIN).returncode:
        raise StartError("Abre Terminal en tu sesión de macOS y ejecuta el comando allí.")
    action = sys.argv[1]
    (RUN / "launchd").mkdir(parents=True, exist_ok=True, mode=0o700)
    with (RUN / "control.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if action == "iniciar":
            start(settings())
        elif action == "detener":
            for name in reversed(JOBS):
                unload(name)
            print("Demo detenido. MAMP sigue disponible.")
        elif action == "estado":
            for name in JOBS:
                result = launchctl("print", target(name))
                running = any(line.strip() == "state = running" for line in result.stdout.splitlines())
                state = "en marcha" if running else "sin proceso propio" if name == "modelo" else "detenido"
                print(f"{NAMES[name]} {state}.")
            mysql = dotenv_mysql()
            print("MySQL de MAMP " + ("disponible." if tcp(*mysql) else "detenido."))
        else:
            raise StartError("Usa iniciar, detener o estado.")


def dotenv_mysql():
    config = dotenv_values(D / ".env.mysql")
    return config.get("MYSQL_HOST", "127.0.0.1"), int(config.get("MYSQL_PORT", "8889"))


if __name__ == "__main__":
    try:
        main()
    except (StartError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(str(exc)) from None
