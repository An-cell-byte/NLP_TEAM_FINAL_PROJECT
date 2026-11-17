"""Administra los procesos propios del demo en Windows, sin detener bases compartidas."""
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import urlsplit
import os,sys,json,time,socket,shutil,subprocess,uuid,hmac,hashlib
try:
 import httpx,psutil
 from dotenv import load_dotenv,dotenv_values
 from sqlalchemy import create_engine,text
except ImportError:raise SystemExit('Actualiza las dependencias: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt') from None
D=Path(__file__).resolve().parent
RUN=D/'.runtime/windows'
class StartError(Exception):pass

def settings():
 for name in ['.env','.env.mysql','.env.sources']:load_dotenv(D/name,override=True)
 if not all((D/name).exists() for name in ['.env','.env.mysql','.env.webui']):raise StartError('Falta la primera instalación. Consulta docs/WINDOWS.md.')
 web=dotenv_values(D/'.env.webui')
 if not web.get('WEBUI_DATABASE_URL') or web.get('MANAGE_LOCAL_POSTGRES')!='false':raise StartError('Configura la base de Windows con configurar_webui_windows.py. No copies la configuración del Mac.')
 secret=os.getenv('BRIDGE_SECRET','')
 if len(secret)<32:raise StartError('Falta BRIDGE_SECRET. Conserva las claves existentes y revisa .env.')
 return {'api_port':int(os.getenv('API_PORT','18129')),'ui_port':int(os.getenv('UI_PORT','3187')),'secret':secret,'web':web,'model_url':os.getenv('OLLAMA_URL','http://127.0.0.1:11434').rstrip('/'),'model':os.getenv('GENERATION_MODEL','qwen3:1.7b')}

def tcp(host,port):
 try:
  with socket.create_connection((host,port),timeout=2):return True
 except OSError:return False

def check_databases(cfg):
 if not tcp(os.getenv('MYSQL_HOST','127.0.0.1'),int(os.getenv('MYSQL_PORT','3306'))):raise StartError('Inicia tu servicio MySQL 8 y revisa MYSQL_PORT en .env.mysql.')
 engine=None
 try:
  engine=create_engine(cfg['web']['WEBUI_DATABASE_URL'],hide_parameters=True,connect_args={'connect_timeout':5})
  with engine.connect() as connection:connection.execute(text('SELECT 1'))
 except Exception:raise StartError('PostgreSQL no responde con la cuenta configurada. Inicia su servicio y revisa .env.webui.') from None
 finally:
  if engine is not None:engine.dispose()

@contextmanager
def command_lock():
 import msvcrt
 RUN.mkdir(parents=True,exist_ok=True)
 with (RUN/'control.lock').open('a+b') as lock:
  lock.seek(0,2)
  if not lock.tell():lock.write(b'0');lock.flush()
  lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:raise StartError('Ya hay otro comando de inicio o detención en curso.') from None
  try:yield
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def save(state):
 path=RUN/'estado.json';temp=RUN/('estado_'+uuid.uuid4().hex+'.tmp')
 temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');temp.chmod(0o600);temp.replace(path)

def normalize(command):return [os.path.normcase(str(value)) for value in command]

def capture(pid):
 p=psutil.Process(pid)
 return {'pid':pid,'created':p.create_time(),'argv':p.cmdline()}

def owned(record):
 if not record or not record.get('argv') or record.get('project')!=str(D.resolve()):return False
 try:
  p=psutil.Process(record['pid'])
  return p.is_running() and p.status()!=psutil.STATUS_ZOMBIE and abs(p.create_time()-record['created'])<.001 and normalize(p.cmdline())==normalize(record['argv'])
 except (psutil.Error,KeyError,TypeError):return False

def launch_options():
 return {'creationflags':getattr(subprocess,'DETACHED_PROCESS',0x00000008)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0x00000200)}

def spawn(key,command,state,env=None,stop_file=None):
 path=RUN/(key+'.log')
 with path.open('ab') as log:
  child=subprocess.Popen(command,cwd=D,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,**launch_options())
 path.chmod(0o600)
 try:
  record=capture(child.pid);record.update(role=key,project=str(D.resolve()))
  if stop_file is not None:record['stop_file']=str(stop_file)
  state[key]=record;save(state)
 except (psutil.Error,OSError):
  state.pop(key,None)
  if child.poll() is None:child.terminate();child.wait(timeout=5)
  raise StartError('No se pudo registrar el proceso '+key+'. Se cerró el proceso recién creado; revisa '+str(path)+'.') from None
 return child

def wait_for(check,seconds=120):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if check():return True
  time.sleep(.5)
 return False

def probe_api(cfg):
 try:
  stamp=str(int(time.time()));owner='inicio_demo_windows';signature=hmac.new(cfg['secret'].encode(),owner.encode()+b'\n'+stamp.encode()+b'\n',hashlib.sha256).hexdigest();url='http://127.0.0.1:'+str(cfg['api_port'])
  with httpx.Client(timeout=3) as c:
   health=c.get(url+'/health');response=c.get(url+'/documents',headers={'X-Owner':owner,'X-Time':stamp,'X-Signature':signature})
  return health.status_code==200 and health.json().get('storage')=='mysql' and response.status_code==200
 except (httpx.HTTPError,ValueError):return False

def probe_ui(cfg):
 try:return httpx.get('http://127.0.0.1:'+str(cfg['ui_port'])+'/health',timeout=3).status_code==200
 except httpx.HTTPError:return False

def model_data(cfg):
 try:
  r=httpx.get(cfg['model_url']+'/api/tags',timeout=3);r.raise_for_status();return r.json()
 except (httpx.HTTPError,ValueError):return None

def start_model(cfg,state):
 data=model_data(cfg)
 if data is None:
  address=urlsplit(cfg['model_url'])
  if address.scheme!='http' or address.hostname not in {'127.0.0.1','localhost'}:
   raise StartError('Ollama no responde. Inicia el servicio configurado en OLLAMA_URL.')
  port=address.port or 80
  if tcp(address.hostname,port):raise StartError(f'El puerto {port} está ocupado y no responde como Ollama.')
  candidates=[os.getenv('DEMO_OLLAMA_BINARY'),shutil.which('ollama'),str(Path(os.getenv('LOCALAPPDATA',''))/'Programs/Ollama/ollama.exe')]
  executable=next((p for p in candidates if p and Path(p).is_file()),None)
  if not executable:raise StartError('Abre Ollama o instala su aplicación. No se encontró ollama.exe.')
  if owned(state.get('modelo')):raise StartError('Ollama sigue iniciando. Revisa .runtime/windows/modelo.log.')
  environment={**os.environ,'OLLAMA_HOST':f'127.0.0.1:{port}','OLLAMA_NO_CLOUD':'1'}
  print('Iniciando Ollama...',flush=True);child=spawn('modelo',[executable,'serve'],state,environment)
  if not wait_for(lambda:model_data(cfg) is not None or child.poll() is not None,30) or model_data(cfg) is None:raise StartError('Ollama no respondió. Revisa .runtime/windows/modelo.log.')
  data=model_data(cfg)
 names={m.get('name',m.get('model')) for m in data.get('models',[])}
 if cfg['model'] not in names:raise StartError('Falta el modelo. Ejecuta una vez: ollama pull '+cfg['model'])

def start_worker(role,python,cfg,state):
 port=cfg['api_port'] if role=='api' else cfg['ui_port'];ready=probe_api if role=='api' else probe_ui
 if owned(state.get(role)):
  if not wait_for(lambda:ready(cfg),120):raise StartError('El proceso '+role+' sigue activo, pero no responde. Revisa su registro antes de reiniciarlo.')
  print(role+' ya disponible.',flush=True);return
 if tcp('127.0.0.1',port):
  if role=='api' and ready(cfg):print('API autenticada ya disponible; se conserva como proceso externo.',flush=True);return
  raise StartError('El puerto '+str(port)+' pertenece a otro proceso. Se conserva ese servicio.')
 if not python.is_file():raise StartError('Falta el entorno '+str(python.parent.parent.name)+'. Sigue Primera instalación en docs/WINDOWS.md.')
 stop_file=RUN/('parar_'+role+'_'+uuid.uuid4().hex)
 command=[str(python),str(D/'ejecutar_servicio_windows.py'),role,str(stop_file)]
 print('Iniciando '+role+'...',flush=True);env=dict(os.environ);env['PYTHONUNBUFFERED']='1';env['PYTHONIOENCODING']='utf-8'
 child=spawn(role,command,state,env,stop_file)
 if not wait_for(lambda:ready(cfg) or child.poll() is not None,120) or child.poll() is not None or not ready(cfg):raise StartError('El servicio '+role+' no inició. Revisa .runtime/windows/'+role+'.log. Puedes ejecutar detener_demo.cmd y volver a intentar.')

def start(cfg,state):
 check_databases(cfg);print('MySQL y PostgreSQL disponibles.',flush=True)
 start_model(cfg,state)
 start_worker('api',D/'.venv/Scripts/python.exe',cfg,state)
 start_worker('webui',D/'.venv_webui/Scripts/python.exe',cfg,state)
 print('Qwerty listo: http://127.0.0.1:'+str(cfg['ui_port']),flush=True)
 print('Puedes cerrar esta terminal. Para detenerlo: .\\detener_demo.cmd',flush=True)

def terminate_tree(record):
 if not owned(record):return
 parent=psutil.Process(record['pid']);children=[]
 try:children=[{**capture(p.pid),'project':record['project']} for p in parent.children(recursive=True)]
 except psutil.NoSuchProcess:return
 # Cada PID se contrasta otra vez antes de detenerlo; no se busca por nombre de programa.
 for item in list(reversed(children))+[record]:
  if owned(item):
   try:psutil.Process(item['pid']).terminate()
   except psutil.NoSuchProcess:pass


def stop(state):
 for role in ['webui','api','modelo']:
  record=state.get(role)
  if not owned(record):state.pop(role,None);continue
  stop_path=record.get('stop_file')
  if stop_path:
   path=Path(stop_path).resolve()
   if path.parent!=RUN.resolve() or not path.name.startswith('parar_'+role+'_'):raise StartError('El archivo de control de '+role+' no corresponde al demo. Se conserva el proceso.')
   path.write_text('detener',encoding='utf-8');path.chmod(0o600)
   if not wait_for(lambda:not owned(record),30):
    print('El cierre de '+role+' agotó su espera; terminando únicamente su proceso verificado.',flush=True);terminate_tree(record)
  else:terminate_tree(record)
  if not wait_for(lambda:not owned(record),10):save(state);raise StartError('El proceso '+role+' todavía está terminando. Revisa su registro.')
  state.pop(role,None);save(state)
 save(state);print('Demo detenido. MySQL, PostgreSQL, cuentas, archivos e historial se conservan.',flush=True)

def main():
 if sys.platform!='win32':raise StartError('Este lanzador corresponde a Windows. En macOS utiliza iniciar_demo.sh o detener_demo.sh.')
 os.chdir(D)
 action=sys.argv[1] if len(sys.argv)>1 else 'iniciar'
 if action not in {'iniciar','detener'}:raise StartError('Acciones disponibles: iniciar o detener.')
 with command_lock():
  p=RUN/'estado.json';state=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
  if action=='iniciar':start(settings(),state)
  else:stop(state)
if __name__=='__main__':
 try:main()
 except (StartError,ValueError,OSError,psutil.Error) as exc:print('No se completó el comando: '+str(exc),file=sys.stderr);sys.exit(1)
