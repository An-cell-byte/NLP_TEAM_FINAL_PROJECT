"""Inicia y detiene el demo local y conserva sus datos persistentes."""
from pathlib import Path
import os,sys,json,time,socket,shutil,subprocess,signal,fcntl,hashlib,hmac
from dotenv import load_dotenv,dotenv_values
import httpx
from urllib.parse import urlsplit
D=Path(__file__).resolve().parent;RUN=D/'.runtime'
class StartError(Exception):pass

def settings():
 for name in ['.env','.env.mysql','.env.sources']:load_dotenv(D/name,override=True)
 if os.getenv('OLLAMA_URL')=='http://host.docker.internal:11434':os.environ['OLLAMA_URL']='http://127.0.0.1:11434'
 if not (D/'.env').exists() or not (D/'.env.mysql').exists():raise StartError('Primera instalación: ejecuta configurar.py y configurar_mysql.py.')
 web=dotenv_values(D/'.env.webui')
 if not web.get('WEBUI_DATABASE_URL'):raise StartError('Falta PostgreSQL para la interfaz. Ejecuta configurar_postgresql.py.')
 return {'api_port':int(os.getenv('API_PORT','18129')),'ui_port':int(os.getenv('UI_PORT','3187')),'secret':os.getenv('BRIDGE_SECRET',''),'web':web}

def run(command,**kwargs):return subprocess.run(command,cwd=D,capture_output=True,text=True,timeout=120,**kwargs)

def tcp(host,port):
 try:
  with socket.create_connection((host,port),timeout=2):return True
 except OSError:return False

def probe_api(cfg):
 try:
  url='http://127.0.0.1:'+str(cfg['api_port']);stamp=str(int(time.time()));owner='inicio_demo';signature=hmac.new(cfg['secret'].encode(),owner.encode()+b'\n'+stamp.encode()+b'\n',hashlib.sha256).hexdigest()
  with httpx.Client(timeout=3) as c:
   h=c.get(url+'/health');r=c.get(url+'/documents',headers={'X-Owner':owner,'X-Time':stamp,'X-Signature':signature})
  return h.status_code==200 and h.json().get('storage')=='mysql' and r.status_code==200
 except (httpx.HTTPError,ValueError):return False

def wait_for(check,seconds=90):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if check():return True
  time.sleep(.5)
 return False

def model_data(url):
 try:
  response=httpx.get(url+'/api/tags',timeout=3)
  response.raise_for_status();data=response.json()
  return data if isinstance(data,dict) and isinstance(data.get('models'),list) else None
 except (httpx.HTTPError,ValueError):return None

def model_binary():
 candidates=[os.getenv('DEMO_OLLAMA_BINARY'),RUN/'ollama/ollama',shutil.which('ollama'),'/Applications/Ollama.app/Contents/Resources/ollama','/opt/homebrew/bin/ollama','/usr/local/bin/ollama']
 paths=(D/Path(value).expanduser() for value in candidates if value)
 return next((str(path) for path in paths if path.is_file() and os.access(path,os.X_OK)),None)

def start_model(state):
 url=os.getenv('OLLAMA_URL','http://127.0.0.1:11434').rstrip('/');model=os.getenv('GENERATION_MODEL','qwen3:1.7b')
 address=urlsplit(url)
 if address.scheme not in {'http','https'} or not address.hostname or address.username or address.password:raise StartError('Revisa OLLAMA_URL en .env; usa una dirección HTTP sin claves.')
 data=model_data(url)
 if data is None:
  if address.scheme!='http' or address.hostname not in {'127.0.0.1','localhost'}:raise StartError('Ollama no responde. Inicia el servicio indicado en OLLAMA_URL.')
  port=address.port or 80
  if tcp(address.hostname,port):raise StartError('El puerto de Ollama está ocupado, pero su API no responde. Se conserva el proceso existente.')
  executable=model_binary()
  if not executable:raise StartError('Ollama no está disponible. Instala o abre Ollama en tu Mac y vuelve a ejecutar ./iniciar_demo.sh. Si está en otra ubicación, define DEMO_OLLAMA_BINARY en .env.')
  if owned(state.get('modelo')):raise StartError('Ollama sigue iniciando. Revisa .runtime/modelo.log.')
  env=dict(os.environ);env['OLLAMA_HOST']='127.0.0.1:'+str(port)
  print('Iniciando Ollama...',flush=True);child=spawn('modelo',[executable,'serve'],executable,state,env)
  if not wait_for(lambda:model_data(url) is not None or child.poll() is not None,30):raise StartError('Ollama no respondió a tiempo. Revisa .runtime/modelo.log.')
  data=model_data(url)
  if data is None:raise StartError('Ollama no inició. Revisa .runtime/modelo.log.')
 names={item.get('name',item.get('model')) for item in data['models'] if isinstance(item,dict)}
 if model not in names and (':' in model or model+':latest' not in names):raise StartError('Ollama responde, pero falta '+model+'. Descárgalo una vez con ollama pull '+model+' usando el mismo OLLAMA_MODELS del demo. No se descargan modelos automáticamente.')
 print('Ollama disponible: '+model,flush=True)

def ps(pid,field):
 r=run(['/bin/ps','-p',str(pid),'-o',field+'=']);return r.stdout.strip() if r.returncode==0 else ''

def owned(record):return bool(record and record.get('started') and ps(record['pid'],'lstart')==record['started'] and record['needle'] in ps(record['pid'],'command'))

def save(state):
 p=RUN/'state.json';p.write_text(json.dumps(state,indent=2));p.chmod(0o600)

def spawn(key,command,needle,state,env=None):
 pth=RUN/(key+'.log')
 with pth.open('a') as log:p=subprocess.Popen(command,cwd=D,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 pth.chmod(0o600);state[key]={'pid':p.pid,'needle':needle,'started':ps(p.pid,'lstart')};save(state);return p

def postgres(cfg,action):
 from configurar_postgresql import find_bin
 w=cfg['web']
 if w.get('MANAGE_LOCAL_POSTGRES')!='true':return
 data=(D/w.get('PG_DATA_DIR','.runtime/postgresql')).resolve();expected=(RUN/'postgresql').resolve()
 if data!=expected or not (data/'PG_VERSION').exists():raise StartError('La instancia PostgreSQL no pertenece a este demo. Se conserva; revisa .env.webui.')
 binary=find_bin(w.get('PG_BIN'),(data/'PG_VERSION').read_text().strip())/'pg_ctl'
 active=run([str(binary),'-D',str(data),'status']).returncode==0
 if (action=='start' and not active) or (action=='stop' and active):
  command=[str(binary),'-D',str(data),'-w']
  command+=['-l',str(RUN/'postgresql.log'),'start'] if action=='start' else ['-m','fast','stop']
  if run(command).returncode:raise StartError('No se pudo '+action+' PostgreSQL. Revisa .runtime/postgresql.log.')

def start(cfg,state):
 if not tcp(os.getenv('MYSQL_HOST','127.0.0.1'),int(os.getenv('MYSQL_PORT','8889'))):raise StartError('Abre MAMP y pulsa Start. Revisa el puerto de .env.mysql.')
 print('MySQL disponible.',flush=True);postgres(cfg,'start');print('PostgreSQL local preparado.',flush=True)
 start_model(state)
 env=dict(os.environ);cache=RUN/'huggingface'
 if 'HF_HOME' not in env and (cache/'hub').exists():env['HF_HOME']=str(cache)
 if not probe_api(cfg):
  if tcp('127.0.0.1',cfg['api_port']):raise StartError('El puerto de la API está ocupado por otra configuración.')
  print('Iniciando la API...',flush=True);p=spawn('api',[sys.executable,str(D/'iniciar_api.py')],str(D/'iniciar_api.py'),state,env)
  if not wait_for(lambda:probe_api(cfg) or p.poll() is not None,45) or not probe_api(cfg):raise StartError('La API no inició. Revisa .runtime/api.log.')
 else:print('API ya disponible.',flush=True)
 if not owned(state.get('webui')):
  if tcp('127.0.0.1',cfg['ui_port']):raise StartError('El puerto de la interfaz está ocupado. Conservamos el servicio existente; revisa el cambio de instalación.')
  python=D/'.venv_webui/bin/python'
  if not python.is_file():raise StartError('Prepara el entorno de Open WebUI como indica docs/INSTALACION.md.')
  print('Iniciando Open WebUI local...',flush=True)
  spawn('webui',[str(python),str(D/'iniciar_webui.py')],'open-webui serve',state,env)
 def ui_ready():
  try:return httpx.get('http://127.0.0.1:'+str(cfg['ui_port'])+'/health',timeout=3).status_code==200
  except httpx.HTTPError:return False
 if not wait_for(ui_ready,120):raise StartError('La interfaz no respondió a tiempo. Revisa .runtime/webui.log.')
 print('Qwerty listo: http://127.0.0.1:'+str(cfg['ui_port']),flush=True)
 print('Para detenerlo: ./detener_demo.sh',flush=True)

def stop(cfg,state):
 for key in ['webui','api','modelo']:
  record=state.get(key)
  if not owned(record):state.pop(key,None);continue
  os.kill(record['pid'],signal.SIGTERM)
  if wait_for(lambda:not owned(record),15):state.pop(key,None)
  else:raise StartError('El proceso '+key+' todavía está terminando. No se detuvo PostgreSQL.')
 save(state);postgres(cfg,'stop');print('Demo detenido. MySQL, cuentas e historial se conservan.',flush=True)

def main():
 os.chdir(D);RUN.mkdir(mode=0o700,exist_ok=True);RUN.chmod(0o700);action=sys.argv[1] if len(sys.argv)>1 else 'iniciar'
 if action not in {'iniciar','detener'}:raise StartError('Acciones disponibles: iniciar o detener.')
 with (RUN/'control.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);cfg=settings();p=RUN/'state.json';state=json.loads(p.read_text()) if p.exists() else {}
  if action=='iniciar':start(cfg,state)
  else:stop(cfg,state)
if __name__=='__main__':
 try:main()
 except (StartError,ValueError,subprocess.TimeoutExpired) as exc:print('No se completó el comando: '+str(exc),file=sys.stderr);sys.exit(1)
