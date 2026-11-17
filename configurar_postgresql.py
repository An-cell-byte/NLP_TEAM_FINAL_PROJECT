"""Prepara PostgreSQL local y permite retomar una instalación interrumpida."""
from pathlib import Path
import os,secrets,subprocess,tempfile,json,argparse,shutil,socket,re
from dotenv import set_key
from sqlalchemy.engine import URL
import psycopg
from psycopg import sql
D=Path(__file__).resolve().parent
PENDING_NAME='.env.postgresql_setup.json'

def find_bin(configured=None, major=None):
 candidates=[configured or os.getenv('PG_BIN'),D/'.runtime/postgresql-bin']
 for version in ([major] if major else ['17','16']):
  candidates.extend([f'/Library/PostgreSQL/{version}/bin',f'/opt/homebrew/opt/postgresql@{version}/bin',f'/usr/local/opt/postgresql@{version}/bin'])
 path_binary=shutil.which('pg_ctl')
 if path_binary:candidates.append(Path(path_binary).parent)
 for value in candidates:
  if not value:continue
  directory=(D/Path(value).expanduser()).resolve()
  if (directory/'pg_ctl').is_file() and (major is None or binary_major(directory)==major):return directory
 version=major or '16 o 17'
 raise ValueError(f'No encontré PostgreSQL {version}. Revisa la instalación o indica su carpeta bin en PG_BIN.')

def port_busy(port):
 try:
  with socket.create_connection(('127.0.0.1',port),timeout=1):return True
 except ConnectionRefusedError:return False
 except OSError as exc:
  if getattr(exc,'errno',None) in {61,111,10061}:return False
  raise ValueError('No fue posible comprobar el puerto local. Revisa los permisos de red.') from None

def save_pending(path,value,new=False):
 flags=os.O_WRONLY|os.O_CREAT|(os.O_EXCL if new else os.O_TRUNC)
 with os.fdopen(os.open(path,flags,0o600),'w') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
 path.chmod(0o600)

def binary_major(binaries):
 result=subprocess.run([str(binaries/'postgres'),'--version'],capture_output=True,text=True,timeout=10)
 match=re.search(r'PostgreSQL\) (\d+)',result.stdout)
 if result.returncode or not match:raise ValueError('No fue posible comprobar la versión de PostgreSQL.')
 return match[1]

def initialize(binaries,data,password,runtime):
 with tempfile.NamedTemporaryFile(mode='w',dir=runtime,delete=False) as stream:
  stream.write(password);temporary=Path(stream.name);temporary.chmod(0o600)
 try:
  result=subprocess.run([str(binaries/'initdb'),'-D',str(data),'-U','demo_admin','-A','scram-sha-256','--pwfile',str(temporary),'--encoding=UTF8','--locale=C'],capture_output=True,text=True)
  if result.returncode:raise ValueError('No se pudo crear la instancia PostgreSQL. Se conservaron las claves de instalación; revisa PG_BIN, permisos y espacio.')
 finally:temporary.unlink(missing_ok=True)

def configure_port(data,port):
 path=data/'postgresql.conf';lines=path.read_text().splitlines()
 lines=[line for line in lines if not re.match(r'^\s*(port|listen_addresses|unix_socket_directories)\s*=',line)]
 path.write_text('\n'.join(lines)+"\nlisten_addresses = '127.0.0.1'\nport = "+str(port)+"\nunix_socket_directories = ''\n")

def provision(port,pending):
 common={'host':'127.0.0.1','port':port,'connect_timeout':5}
 with psycopg.connect(**common,user='demo_admin',password=pending['admin_password'],dbname='postgres',autocommit=True) as connection:
  exists=connection.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',('demo_webui',)).fetchone()
  if exists:
   try:
    with psycopg.connect(**common,user='demo_webui',password=pending['app_password'],dbname='postgres'):pass
   except psycopg.Error:raise ValueError('La cuenta demo_webui ya existe con otra configuración. Se conserva; revisa la instalación antes de continuar.') from None
  else:connection.execute(sql.SQL('CREATE ROLE demo_webui LOGIN PASSWORD {}').format(sql.Literal(pending['app_password'])))
  owner=connection.execute('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s',('demo_webui',)).fetchone()
  if owner and owner[0]!='demo_webui':raise ValueError('La base demo_webui tiene otro propietario. No se modificó.')
  if not owner:connection.execute('CREATE DATABASE demo_webui OWNER demo_webui')
 with psycopg.connect(**common,user='demo_webui',password=pending['app_password'],dbname='demo_webui') as connection:connection.execute('SELECT 1')

def publish(target,binaries,data,port,pending):
 url=URL.create('postgresql+psycopg',username='demo_webui',password=pending['app_password'],host='127.0.0.1',port=port,database='demo_webui').render_as_string(hide_password=False)
 bin_path=binaries.relative_to(D).as_posix() if binaries.is_relative_to(D) else str(binaries)
 values={'WEBUI_DATABASE_URL':url,'PG_BIN':bin_path,'PG_DATA_DIR':data.relative_to(D).as_posix(),'PG_PORT':str(port),'PG_ADMIN_USER':'demo_admin','PG_ADMIN_PASSWORD':pending['admin_password'],'MANAGE_LOCAL_POSTGRES':'true','WEBUI_DATA_DIR':(data.parent/'webui').relative_to(D).as_posix(),'WEBUI_PG_HOST':'127.0.0.1','WEBUI_PG_PORT':str(port),'WEBUI_PG_DATABASE':'demo_webui','WEBUI_PG_USER':'demo_webui','WEBUI_PG_PASSWORD':pending['app_password']}
 with tempfile.NamedTemporaryFile(mode='w',dir=D,delete=False,prefix='.env.webui_') as stream:temporary=Path(stream.name)
 temporary.chmod(0o600)
 try:
  for key,value in values.items():set_key(str(temporary),key,value)
  os.link(temporary,target)
 finally:temporary.unlink(missing_ok=True)

def setup(port=None):
 target=D/'.env.webui';pending_path=D/PENDING_NAME;runtime=D/'.runtime';data=(runtime/'postgresql').resolve()
 if target.exists():return 'La configuración de PostgreSQL ya existe y se conserva.'
 pending=json.loads(pending_path.read_text()) if pending_path.exists() else None
 if pending and (pending.get('project')!=str(D.resolve()) or pending.get('data')!=str(data)):raise ValueError('El archivo de instalación pertenece a otra carpeta. Se conservó; revisa su origen.')
 if data.exists() and not pending:raise ValueError('Existe una instancia incompleta sin claves de recuperación. No la borres ni cambies pg_hba.conf; revisa el registro y recupera esa instancia desde un respaldo.')
 port=int(port if port is not None else pending['port'] if pending else 55440)
 if not 1024<=port<=65535:raise ValueError('El puerto debe estar entre 1024 y 65535.')
 binaries=Path(pending['pg_bin']) if pending else find_bin()
 active=False
 if (data/'PG_VERSION').exists():
  if (data/'PG_VERSION').read_text().strip()!=binary_major(binaries):raise ValueError('Los programas PostgreSQL no corresponden a la versión de esta instancia. Se conservaron sus datos.')
  active=subprocess.run([str(binaries/'pg_ctl'),'-D',str(data),'status'],capture_output=True,text=True).returncode==0
 if active:
  pid=(data/'postmaster.pid').read_text().splitlines()
  if len(pid)<4 or Path(pid[1]).resolve()!=data or int(pid[3])!=port:raise ValueError('Esta instancia ya está iniciada en otro puerto. Se conserva; utiliza su configuración actual.')
 elif port_busy(port):raise ValueError('El puerto '+str(port)+' está ocupado. Elige otro libre: configurar_postgresql.py --port '+str(port+1)+'. No se detuvo ningún servicio ni se descartaron claves.')
 runtime.mkdir(exist_ok=True,mode=0o700)
 if not pending:
  pending={'project':str(D.resolve()),'data':str(data),'pg_bin':str(binaries),'port':port,'admin_password':secrets.token_urlsafe(32),'app_password':secrets.token_urlsafe(32)}
  save_pending(pending_path,pending,new=True)
 if not (data/'PG_VERSION').exists():
  if data.exists() and any(data.iterdir()):raise ValueError('La inicialización quedó incompleta. Se conservan su carpeta y sus claves; revisa el registro antes de continuar.')
  initialize(binaries,data,pending['admin_password'],runtime)
 if not active:
  configure_port(data,port);pending['port']=port;save_pending(pending_path,pending)
  result=subprocess.run([str(binaries/'pg_ctl'),'-D',str(data),'-l',str(runtime/'postgresql.log'),'-w','start'],capture_output=True,text=True)
  if result.returncode:raise ValueError('La instancia no inició en el puerto '+str(port)+'. Revisa .runtime/postgresql.log. Las claves quedaron guardadas para reintentar con --port OTRO_PUERTO.')
 provision(port,pending);publish(target,binaries,data,port,pending);pending_path.unlink()
 return 'PostgreSQL preparado: 127.0.0.1:'+str(port)+', base demo_webui, usuario demo_webui. Configuración privada en .env.webui.'

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=None);args=parser.parse_args()
 try:print(setup(args.port))
 except ValueError as exc:raise SystemExit(str(exc)) from None
 except psycopg.Error:raise SystemExit('No se pudo completar la preparación. Revisa PostgreSQL y el registro; las claves pendientes se conservan en '+PENDING_NAME+'.') from None
