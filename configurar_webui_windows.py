"""Guarda la conexión a una base PostgreSQL ya preparada desde pgAdmin."""
from pathlib import Path
from getpass import getpass
import os
import psycopg
from sqlalchemy.engine import URL
from dotenv import set_key
D=Path(__file__).resolve().parent

def configure(host,port,database,user,password):
 target=D/'.env.webui'
 if target.exists():raise ValueError('.env.webui ya existe. Se conserva; revisa su configuración antes de continuar.')
 if not host or not database or not user or not password:raise ValueError('Host, base, usuario y contraseña son obligatorios.')
 if not 1<=port<=65535:raise ValueError('El puerto debe estar entre 1 y 65535.')
 with psycopg.connect(host=host,port=port,dbname=database,user=user,password=password,connect_timeout=5) as connection:
  actual=connection.execute('SELECT current_database(), current_user').fetchone()
  if actual!=(database,user):raise ValueError('La conexión no corresponde a la base y la cuenta indicadas.')
 runtime=D/'.runtime';runtime.mkdir(exist_ok=True,mode=0o700)
 values={'WEBUI_DATABASE_URL':URL.create('postgresql+psycopg',username=user,password=password,host=host,port=port,database=database).render_as_string(hide_password=False),'WEBUI_PG_HOST':host,'WEBUI_PG_PORT':str(port),'WEBUI_PG_DATABASE':database,'WEBUI_PG_USER':user,'WEBUI_PG_PASSWORD':password,'MANAGE_LOCAL_POSTGRES':'false','WEBUI_DATA_DIR':'.runtime/webui'}
 descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(descriptor)
 for key,value in values.items():set_key(str(target),key,value)
 target.chmod(0o600)
 return target

def main():
 if (D/'.env.webui').exists():print('.env.webui ya existe y se conserva.');return
 host=input('Host PostgreSQL [127.0.0.1]: ').strip() or '127.0.0.1'
 try:port=int(input('Puerto PostgreSQL [5432]: ').strip() or '5432')
 except ValueError:raise SystemExit('El puerto debe ser numérico.') from None
 database=input('Base creada en pgAdmin [demo_webui]: ').strip() or 'demo_webui'
 user=input('Usuario propietario de la base [demo_webui]: ').strip() or 'demo_webui'
 password=getpass('Contraseña de esa cuenta PostgreSQL: ')
 try:path=configure(host,port,database,user,password)
 except ValueError as exc:raise SystemExit(str(exc)) from None
 except psycopg.Error:raise SystemExit('No fue posible conectar. Revisa el servicio PostgreSQL, puerto, base, usuario y contraseña. No se guardaron claves.') from None
 print('Conexión comprobada y guardada en '+str(path)+'. PostgreSQL permanece administrado por el servicio de Windows.')
if __name__=='__main__':main()
