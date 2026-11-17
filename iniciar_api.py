"""Arranque local: lee la configuración privada sin mostrar las claves."""
from pathlib import Path
import os
from dotenv import load_dotenv
D=Path(__file__).resolve().parent
os.chdir(D)
load_dotenv(D/'.env')
load_dotenv(D/'.env.mysql',override=True)
load_dotenv(D/'.env.sources',override=True)
if not os.environ.get('DATABASE_URL') and os.getenv('STORAGE_BACKEND')!='mysql':raise SystemExit('Falta .env; ejecuta configurar.py desde esta carpeta.')
if os.getenv('OLLAMA_URL')=='http://host.docker.internal:11434':os.environ['OLLAMA_URL']='http://127.0.0.1:11434'
import uvicorn
if __name__=='__main__':uvicorn.run('app:app',host='127.0.0.1',port=int(os.getenv('API_PORT','18129')))
