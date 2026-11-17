"""Comprueba conexión, codificación y permisos sin mostrar las claves."""
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
D=Path(__file__).resolve().parent
load_dotenv(D/'.env');load_dotenv(D/'.env.mysql',override=True);load_dotenv(D/'.env.sources',override=True)
from storage import make_engine

def main():
 try:
  e=make_engine()
  if e.dialect.name!='mysql':raise ValueError('STORAGE_BACKEND debe ser mysql en .env.mysql.')
  with e.connect() as c:
   version=c.execute(text('SELECT VERSION()')).scalar();database=c.execute(text('SELECT DATABASE()')).scalar();encoding=c.execute(text('SELECT @@character_set_connection')).scalar()
  print('MySQL conectado. Base: '+str(database)+'. Versión: '+str(version)+'. Codificación: '+str(encoding)+'.')
  import db_sources
  table,stamp,motor=db_sources.read('aurora_mamp','prestamos_detalle')
  print('Vista ficticia de lectura disponible: '+str(len(table['rows']))+' filas. Consulta UTC: '+stamp+'.')
  e.dispose()
 except Exception as exc:
  if isinstance(exc,ValueError):raise SystemExit(str(exc)) from None
  raise SystemExit('No fue posible verificar MySQL. Revisa MAMP y los valores de .env.mysql sin publicar la contraseña.') from None
if __name__=='__main__':main()
