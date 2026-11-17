from pathlib import Path
import importlib.util,sys
from dotenv import dotenv_values
required=['fastapi','psycopg','pgvector','sentence_transformers','fitz','httpx','pymysql','cryptography','openpyxl']
missing=[m for m in required if importlib.util.find_spec(m) is None]
if missing:raise SystemExit('Instala requirements.txt. Faltan: '+', '.join(missing))
config={**dotenv_values('.env'),**dotenv_values('.env.mysql')}
if (not config.get('DATABASE_URL') and config.get('STORAGE_BACKEND')!='mysql') or len(config.get('BRIDGE_SECRET',''))<32:raise SystemExit('Ejecuta configurar.py y revisa .env.')
print('Bibliotecas y configuración presentes. Esta prueba no acredita que los servicios estén encendidos.')
