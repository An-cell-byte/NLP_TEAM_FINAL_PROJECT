from pathlib import Path
from types import SimpleNamespace
import json,os,subprocess,sys,threading
import pytest
import gestionar_demo_windows as g
from ejecutar_servicio_windows import watch_stop

@pytest.fixture
def local(tmp_path,monkeypatch):
 monkeypatch.setattr(g,'D',tmp_path);monkeypatch.setattr(g,'RUN',tmp_path/'.runtime/windows');g.RUN.mkdir(parents=True)
 return tmp_path

@pytest.fixture
def cfg():return {'api_port':18129,'ui_port':3187,'secret':'x'*32,'web':{'WEBUI_DATABASE_URL':'postgresql+psycopg://local/demo'},'model_url':'http://127.0.0.1:11434','model':'qwen3:1.7b'}

def record():return {'pid':123,'created':100.0,'argv':['python.exe','ejecutar_servicio_windows.py','api'],'project':str(g.D.resolve())}

@pytest.mark.parametrize('created,argv,expected',[(100.0,['python.exe','ejecutar_servicio_windows.py','api'],True),(101.0,['python.exe','ejecutar_servicio_windows.py','api'],False),(100.0,['python.exe','otro_programa.py'],False)])
def test_process_identity_requires_time_and_command(monkeypatch,created,argv,expected):
 p=SimpleNamespace(is_running=lambda:True,status=lambda:'running',create_time=lambda:created,cmdline=lambda:argv)
 monkeypatch.setattr(g.psutil,'Process',lambda pid:p)
 assert g.owned(record()) is expected

def test_missing_process_not_owned(monkeypatch):
 def missing(pid):raise g.psutil.NoSuchProcess(pid)
 monkeypatch.setattr(g.psutil,'Process',missing);assert not g.owned(record())

def test_repeated_start_reuses_process(local,cfg,monkeypatch):
 state={'api':record()};monkeypatch.setattr(g,'owned',lambda r:bool(r));monkeypatch.setattr(g,'wait_for',lambda check,*args:check());monkeypatch.setattr(g,'probe_api',lambda c:True)
 monkeypatch.setattr(g,'spawn',lambda *args:pytest.fail('No debe duplicar la API'))
 g.start_worker('api',local/'no_es_necesario.exe',cfg,state)

def test_foreign_interface_port_is_preserved(local,cfg,monkeypatch):
 monkeypatch.setattr(g,'owned',lambda r:False);monkeypatch.setattr(g,'tcp',lambda *args:True);monkeypatch.setattr(g,'spawn',lambda *args:pytest.fail('No debe abrir otro proceso'))
 with pytest.raises(g.StartError,match='otro proceso'):g.start_worker('webui',local/'python.exe',cfg,{})

def test_authenticated_external_api_is_borrowed(local,cfg,monkeypatch):
 monkeypatch.setattr(g,'owned',lambda r:False);monkeypatch.setattr(g,'tcp',lambda *args:True);monkeypatch.setattr(g,'probe_api',lambda c:True)
 state={};g.start_worker('api',local/'python.exe',cfg,state);assert not state

def test_missing_environment_is_explained(local,cfg,monkeypatch):
 monkeypatch.setattr(g,'owned',lambda r:False);monkeypatch.setattr(g,'tcp',lambda *args:False)
 with pytest.raises(g.StartError,match='Falta el entorno'):g.start_worker('webui',local/'Scripts/python.exe',cfg,{})

def test_child_exit_is_not_hidden_by_foreign_health(local,cfg,monkeypatch):
 python=local/'python.exe';python.touch();monkeypatch.setattr(g,'owned',lambda r:False);monkeypatch.setattr(g,'tcp',lambda *args:False);monkeypatch.setattr(g,'probe_ui',lambda c:True);monkeypatch.setattr(g,'wait_for',lambda *args:True)
 monkeypatch.setattr(g,'spawn',lambda *args:SimpleNamespace(poll=lambda:1))
 with pytest.raises(g.StartError,match='no inició'):g.start_worker('webui',python,cfg,{})

def test_spawn_detaches_and_never_saves_environment(local,monkeypatch):
 seen={}
 def popen(command,**kwargs):seen.update(kwargs);return SimpleNamespace(pid=123)
 monkeypatch.setattr(g.subprocess,'Popen',popen);monkeypatch.setattr(g,'capture',lambda pid:record());state={}
 g.spawn('api',['python.exe','worker.py'],state,{'PRIVATE_PASSWORD':'no_distribuir'},g.RUN/'parar_api_test')
 assert seen['creationflags'] & 0x8 and seen['creationflags'] & 0x200
 assert seen['stdin']==subprocess.DEVNULL
 assert 'PRIVATE_PASSWORD' not in (g.RUN/'estado.json').read_text()
 assert 'no_distribuir' not in (g.RUN/'estado.json').read_text()

def test_stop_requests_orderly_shutdown(local,monkeypatch):
 path=g.RUN/'parar_api_test';r={**record(),'stop_file':str(path)};state={'api':r};active={'value':True}
 monkeypatch.setattr(g,'owned',lambda r:bool(r) and active['value'])
 def wait(check,*args):
  assert path.read_text()=='detener';active['value']=False;return check()
 monkeypatch.setattr(g,'wait_for',wait);monkeypatch.setattr(g,'terminate_tree',lambda r:pytest.fail('Debe cerrar sin terminar a la fuerza'))
 g.stop(state);assert not state

def test_recycled_pid_is_not_stopped(local,monkeypatch):
 monkeypatch.setattr(g,'owned',lambda r:False);monkeypatch.setattr(g,'terminate_tree',lambda r:pytest.fail('PID ajeno'))
 path=g.RUN/'parar_api_test';state={'api':{**record(),'stop_file':str(path)}};g.stop(state);assert not path.exists()

def test_control_file_must_belong_to_project(local,monkeypatch):
 monkeypatch.setattr(g,'owned',lambda r:bool(r));path=local/'parar_api_fuera';state={'api':{**record(),'stop_file':str(path)}}
 with pytest.raises(g.StartError,match='no corresponde'):g.stop(state)
 assert not path.exists()

def test_fallback_terminates_only_verified_tree(local,monkeypatch):
 stopped=[];root=record();old_child={'pid':456,'created':1,'argv':['antes']}
 class Process:
  def __init__(self,pid):self.pid=pid
  def children(self,recursive):return [SimpleNamespace(pid=456)]
  def terminate(self):stopped.append(self.pid)
 monkeypatch.setattr(g.psutil,'Process',Process);monkeypatch.setattr(g,'capture',lambda pid:old_child);monkeypatch.setattr(g,'owned',lambda r:r['pid']==123)
 g.terminate_tree(root);assert stopped==[123]

def test_external_model_not_recorded_or_stopped(local,cfg,monkeypatch):
 monkeypatch.setattr(g,'model_data',lambda cfg:{'models':[{'name':'qwen3:1.7b'}]});monkeypatch.setattr(g,'spawn',lambda *args:pytest.fail('Servidor ya disponible'))
 state={};g.start_model(cfg,state);g.stop(state);assert not state

def test_missing_model_does_not_download_it(local,cfg,monkeypatch):
 monkeypatch.setattr(g,'model_data',lambda cfg:{'models':[]});monkeypatch.setattr(g,'spawn',lambda *args:pytest.fail('No debe descargar modelos'))
 with pytest.raises(g.StartError,match='ollama pull'):g.start_model(cfg,{})

def test_new_ollama_binds_to_the_configured_port(local,cfg,monkeypatch):
 cfg['model_url']='http://127.0.0.1:11438'
 executable=local/'ollama.exe';executable.touch()
 monkeypatch.setenv('DEMO_OLLAMA_BINARY',str(executable))
 variables={}
 monkeypatch.setattr(g,'model_data',lambda config:{'models':[{'name':cfg['model']}]} if variables else None)
 monkeypatch.setattr(g,'tcp',lambda *args:False)
 monkeypatch.setattr(g,'owned',lambda record:False)
 monkeypatch.setattr(g,'wait_for',lambda check,seconds:check())
 def spawn(role,args,state,env):
  variables.update(env)
  return SimpleNamespace(poll=lambda:None)
 monkeypatch.setattr(g,'spawn',spawn)
 g.start_model(cfg,{})
 assert variables['OLLAMA_HOST']=='127.0.0.1:11438'
 assert variables['OLLAMA_NO_CLOUD']=='1'

def test_databases_only_checked_not_started(cfg,monkeypatch):
 queries=[];disposed=[]
 class Connection:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def execute(self,sql):queries.append(str(sql))
 monkeypatch.setattr(g,'tcp',lambda *args:True);monkeypatch.setattr(g,'create_engine',lambda *args,**kwargs:SimpleNamespace(connect=Connection,dispose=lambda:disposed.append(True)))
 g.check_databases(cfg);assert queries==['SELECT 1'] and disposed==[True]

def test_invalid_database_url_is_sanitized(cfg,monkeypatch):
 def fail(*args,**kwargs):raise ValueError('clave_superprivada')
 monkeypatch.setattr(g,'tcp',lambda *args:True);monkeypatch.setattr(g,'create_engine',fail)
 with pytest.raises(g.StartError) as e:g.check_databases(cfg)
 assert 'clave_superprivada' not in str(e.value)

def test_lock_released_after_failure(local,monkeypatch):
 calls=[]
 def locking(fd,mode,count):assert os.fstat(fd).st_size>=1;calls.append(mode)
 monkeypatch.setitem(sys.modules,'msvcrt',SimpleNamespace(LK_NBLCK=2,LK_UNLCK=0,locking=locking))
 with pytest.raises(RuntimeError):
  with g.command_lock():raise RuntimeError('fin')
 assert calls==[2,0]

def test_busy_lock_does_not_continue(local,monkeypatch):
 def busy(*args):raise OSError('ocupado')
 monkeypatch.setitem(sys.modules,'msvcrt',SimpleNamespace(LK_NBLCK=2,LK_UNLCK=0,locking=busy))
 with pytest.raises(g.StartError,match='otro comando'):
  with g.command_lock():pytest.fail('No debe entrar')

def test_worker_monitor_does_not_interrupt_without_request(tmp_path,monkeypatch):
 calls=[];finished=threading.Event();monkeypatch.setattr('ejecutar_servicio_windows._thread.interrupt_main',lambda:calls.append(True))
 thread=threading.Thread(target=watch_stop,args=(tmp_path/'sin_solicitud',finished));thread.start();finished.set();thread.join(2);assert not calls

def test_cmd_files_use_project_directory_and_keep_exit_code():
 root=Path(__file__).resolve().parent
 for name,action in [('iniciar_demo.cmd','iniciar'),('detener_demo.cmd','detener')]:
  data=(root/name).read_bytes();assert b'pushd "%~dp0"' in data;assert ('gestionar_demo_windows.py '+action).encode() in data;assert b'exit /b %DEMO_EXIT%' in data;assert b'\r\n' in data

def test_real_child_receives_orderly_close_request(tmp_path):
 # Protocolo real de cierre en un proceso nuevo; no ejecuta servicios ni simula Windows.
 source=Path(__file__).resolve().parent;path=tmp_path/'solicitud';script=tmp_path/'worker_prueba.py'
 script.write_text('''import sys,threading,signal\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nfrom ejecutar_servicio_windows import watch_stop\nfinished=threading.Event()\ndef close(*args):\n print('cierre_ordenado',flush=True);finished.set()\nsignal.signal(signal.SIGINT,close)\nthreading.Thread(target=watch_stop,args=(Path(sys.argv[2]),finished),daemon=True).start()\nprint('listo',flush=True)\nwhile not finished.wait(.1):pass\n''')
 child=subprocess.Popen([sys.executable,str(script),str(source),str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  assert child.stdout.readline().strip()=='listo';path.write_text('detener');stdout,stderr=child.communicate(timeout=10);assert child.returncode==0 and 'cierre_ordenado' in stdout
 finally:
  if child.poll() is None:child.terminate();child.wait(timeout=5)

def test_failed_state_save_closes_new_child(local,monkeypatch):
 calls=[]
 class Child:
  pid=123
  def poll(self):return None
  def terminate(self):calls.append('terminate')
  def wait(self,timeout):calls.append('wait')
 monkeypatch.setattr(g.subprocess,'Popen',lambda *args,**kwargs:Child());monkeypatch.setattr(g,'capture',lambda pid:record())
 def fail(state):raise OSError('sin espacio')
 monkeypatch.setattr(g,'save',fail);state={}
 with pytest.raises(g.StartError,match='No se pudo registrar'):g.spawn('api',['python.exe'],state)
 assert calls==['terminate','wait'] and not state

def test_stop_does_not_load_database_config(local,monkeypatch):
 monkeypatch.setattr(g.sys,'platform','win32');monkeypatch.setattr(g.sys,'argv',['gestionar_demo_windows.py','detener'])
 from contextlib import nullcontext
 monkeypatch.setattr(g,'command_lock',nullcontext);monkeypatch.setattr(g,'settings',lambda:pytest.fail('La detención no depende de las bases'))
 g.main();assert json.loads((g.RUN/'estado.json').read_text())=={}

def test_windows_launcher_does_not_run_on_mac(local,monkeypatch):
 monkeypatch.setattr(g.sys,'platform','darwin')
 with pytest.raises(g.StartError,match='corresponde a Windows'):g.main()

def test_webui_worker_uses_its_environment_and_single_process(monkeypatch):
 from ejecutar_servicio_windows import serve
 calls=[];monkeypatch.setenv('UVICORN_WORKERS','3');monkeypatch.setenv('UI_PORT','3187');monkeypatch.setenv('TEST_WEBUI_ENV','antes')
 monkeypatch.setitem(sys.modules,'iniciar_webui',SimpleNamespace(environment=lambda:{'TEST_WEBUI_ENV':'cargado'},relocate_uploads=lambda env:None,configure_chat=lambda env:None))
 monkeypatch.setitem(sys.modules,'open_webui',SimpleNamespace(serve=lambda **kwargs:calls.append(kwargs)))
 serve('webui');assert calls==[{'host':'127.0.0.1','port':3187}];assert os.environ['UVICORN_WORKERS']=='1';assert os.environ['TEST_WEBUI_ENV']=='cargado'

def test_api_worker_uses_configured_port(monkeypatch):
 from ejecutar_servicio_windows import serve
 calls=[];monkeypatch.setenv('API_PORT','18129')
 monkeypatch.setitem(sys.modules,'iniciar_api',SimpleNamespace(uvicorn=SimpleNamespace(run=lambda *args,**kwargs:calls.append((args,kwargs)))))
 serve('api');assert calls==[(('app:app',),{'host':'127.0.0.1','port':18129})]


def test_state_from_another_project_is_not_owned(monkeypatch):
 p=SimpleNamespace(is_running=lambda:True,status=lambda:'running',create_time=lambda:100.0,cmdline=lambda:record()['argv'])
 monkeypatch.setattr(g.psutil,'Process',lambda pid:p)
 value=record();value['project']='otro_proyecto';assert not g.owned(value)
