"""Prepara dos bases nuevas y cuentas limitadas. No modifica bases existentes."""
from pathlib import Path
from getpass import getpass
import json,re,secrets,os
import pymysql
from dotenv import dotenv_values,set_key
from sqlalchemy.engine import URL

D=Path(__file__).resolve().parent

def provision(host,port,admin_user,admin_password,database,app_user):
 if (D/'.env.mysql').exists():raise ValueError('.env.mysql ya existe. Se conserva; verifica la configuración antes de crear otra.')
 if 'aurora_mamp' in json.loads(dotenv_values(D/'.env.sources').get('SOURCE_CONNECTIONS') or '{}'):raise ValueError('El alias aurora_mamp ya existe; se conserva.')
 if not re.fullmatch(r'demo_[a-z0-9_]{1,40}',database):raise ValueError('La base debe comenzar con demo_ y usar letras minúsculas, números o guion bajo.')
 if not re.fullmatch(r'demo_[a-z0-9_]{1,22}',app_user):raise ValueError('El usuario debe comenzar con demo_ y medir como máximo 27 caracteres.')
 demo=database+'_aurora';reader=app_user+'_lect';password=secrets.token_urlsafe(32);read_password=secrets.token_urlsafe(32)
 if len(reader)>32:raise ValueError('El usuario lector supera 32 caracteres.')
 connection=pymysql.connect(host=host,port=port,user=admin_user,password=admin_password,charset='utf8mb4',connect_timeout=5,autocommit=True)
 try:
  with connection.cursor() as cur:
   cur.execute('SELECT VERSION()');version=cur.fetchone()[0]
   if not version.startswith('8.'):raise ValueError('Esta ruta requiere MySQL 8 de MAMP; revisa la versión seleccionada en MAMP.')
   for name in [database,demo]:
    cur.execute('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s',(name,))
    if cur.fetchone():raise ValueError('La base '+name+' ya existe. No se modificó. Elige otro nombre nuevo o utiliza la configuración existente.')
   for user in [app_user,reader]:
    cur.execute('SELECT 1 FROM mysql.user WHERE User=%s',(user,))
    if cur.fetchone():raise ValueError('El usuario '+user+' ya existe. No se modificó; elige otro nombre.')
   # Los identificadores se validan antes de citarlos; los valores siempre son parámetros.
   for name in [database,demo]:cur.execute('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
   cur.execute('CREATE USER %s@localhost IDENTIFIED BY %s',(app_user,password))
   cur.execute('GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX ON `'+database+'`.* TO %s@localhost',(app_user,))
   cur.execute('USE `'+demo+'`')
   for statement in (D/'datos/aurora_mysql.sql').read_text().split(';'):
    if statement.strip():cur.execute(statement)
   cur.execute('CREATE USER %s@localhost IDENTIFIED BY %s',(reader,read_password))
   cur.execute('GRANT SELECT ON `'+demo+'`.prestamos_detalle TO %s@localhost',(reader,))
 finally:connection.close()
 config=D/'.env.mysql'
 if config.exists():raise ValueError('Se prepararon las bases, pero .env.mysql apareció durante la configuración; no se sobrescribió.')
 config.write_text('STORAGE_BACKEND=mysql\nMYSQL_HOST='+host+'\nMYSQL_PORT='+str(port)+'\nMYSQL_DATABASE='+database+'\nMYSQL_USER='+app_user+'\nMYSQL_PASSWORD='+password+'\nMAX_MYSQL_SEARCH_CHUNKS=5000\n');config.chmod(0o600)
 sources=D/'.env.sources'
 if not sources.exists():sources.touch(mode=0o600)
 old=dotenv_values(sources);policy=json.loads(old.get('SOURCE_CONNECTIONS') or '{}')
 if 'aurora_mamp' in policy:raise ValueError('Las bases se prepararon; el alias aurora_mamp ya existe y se conservó. Revisa .env.sources.')
 policy['aurora_mamp']={'url_env':'SOURCE_MYSQL_MAMP_URL','public_demo':True,'tables':{'prestamos_detalle':['id','usuario_id','nombre','libro','importe','fecha']}}
 url=URL.create('mysql+pymysql',username=reader,password=read_password,host=host,port=port,database=demo,query={'charset':'utf8mb4'}).render_as_string(hide_password=False)
 set_key(str(sources),'SOURCE_MYSQL_MAMP_URL',url);set_key(str(sources),'SOURCE_CONNECTIONS',json.dumps(policy,ensure_ascii=False));sources.chmod(0o600)
 return {'mysql_version':version,'host':host,'port':port,'database':database,'demo_database':demo,'app_user':app_user,'reader_user':reader}

def main():
 os.chdir(D)
 if (D/'.env.mysql').exists():
  print('.env.mysql ya existe. Se conserva. Ejecuta verificar_mysql.py para comprobarla.');return
 host=input('Host de MAMP [127.0.0.1]: ').strip() or '127.0.0.1'
 try:port=int(input('Puerto MySQL de MAMP [8889]: ').strip() or '8889')
 except ValueError:raise SystemExit('El puerto debe ser numérico.')
 admin=input('Usuario administrador de MAMP [root]: ').strip() or 'root'
 password=getpass('Contraseña actual de ese administrador (no se guarda): ')
 default='demo_documental'
 database=input('Base nueva ['+default+']: ').strip() or default
 user=input('Usuario nuevo de la aplicación ['+default+']: ').strip() or default
 try:result=provision(host,port,admin,password,database,user)
 except ValueError as exc:raise SystemExit(str(exc)) from None
 except Exception:raise SystemExit('No se completó la configuración. Revisa MAMP, puerto, credenciales y permisos. No vuelvas a ejecutar sobre bases existentes sin revisarlas.') from None
 print('Configuración preparada en .env.mysql y .env.sources. Bases nuevas: '+result['database']+' y '+result['demo_database']+'. Las contraseñas no se muestran. Aurora usa datos ficticios compartidos solo dentro del demo.')
if __name__=='__main__':main()
