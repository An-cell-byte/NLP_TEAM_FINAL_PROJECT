from types import SimpleNamespace
import pytest

pytest.importorskip('fcntl', reason='El lanzador de macOS usa fcntl.')
import gestionar_demo as g

@pytest.fixture
def local(monkeypatch):
 monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:11434')
 monkeypatch.setenv('GENERATION_MODEL','qwen3:1.7b')
 monkeypatch.setattr(g,'tcp',lambda *args:False)
 monkeypatch.setattr(g,'owned',lambda record:False)
 monkeypatch.setattr(g,'model_binary',lambda:'/custom/ollama')
 monkeypatch.setattr(g,'wait_for',lambda check,seconds:check())

def test_existing_service_is_reused(local,monkeypatch):
 monkeypatch.setattr(g,'model_data',lambda url:{'models':[{'name':'qwen3:1.7b'}]})
 monkeypatch.setattr(g,'spawn',lambda *a,**kw:pytest.fail('No debe iniciar otro servicio'))
 state={};g.start_model(state);assert state=={}

def test_service_starts_with_same_model_directory(local,monkeypatch):
 monkeypatch.setenv('OLLAMA_MODELS','/models/existing')
 count={'value':0};calls=[]
 def data(url):
  count['value']+=1
  return None if count['value']==1 else {'models':[{'model':'qwen3:1.7b'}]}
 monkeypatch.setattr(g,'model_data',data)
 monkeypatch.setattr(g,'spawn',lambda *args:(calls.append(args) or SimpleNamespace(poll=lambda:None)))
 g.start_model({})
 assert calls[0][1]==['/custom/ollama','serve']
 assert calls[0][-1]['OLLAMA_HOST']=='127.0.0.1:11434'
 assert calls[0][-1]['OLLAMA_MODELS']=='/models/existing'

def test_missing_binary_has_actionable_message(local,monkeypatch):
 monkeypatch.setattr(g,'model_data',lambda url:None)
 monkeypatch.setattr(g,'model_binary',lambda:None)
 with pytest.raises(g.StartError,match='Instala o abre Ollama'):g.start_model({})

def test_busy_port_is_preserved(local,monkeypatch):
 monkeypatch.setattr(g,'model_data',lambda url:None)
 monkeypatch.setattr(g,'tcp',lambda *args:True)
 monkeypatch.setattr(g,'spawn',lambda *a:pytest.fail('No debe tocar el puerto ocupado'))
 with pytest.raises(g.StartError,match='ocupado'):g.start_model({})

def test_remote_service_is_not_started_locally(local,monkeypatch):
 monkeypatch.setenv('OLLAMA_URL','https://example.invalid:11434')
 monkeypatch.setattr(g,'model_data',lambda url:None)
 with pytest.raises(g.StartError,match='Inicia el servicio indicado'):g.start_model({})

def test_missing_model_does_not_download(local,monkeypatch):
 monkeypatch.setattr(g,'model_data',lambda url:{'models':[]})
 with pytest.raises(g.StartError,match='ollama pull qwen3:1.7b'):g.start_model({})

def test_failed_process_never_reports_ready(local,monkeypatch):
 monkeypatch.setattr(g,'model_data',lambda url:None)
 monkeypatch.setattr(g,'spawn',lambda *a:SimpleNamespace(poll=lambda:1))
 with pytest.raises(g.StartError,match='Ollama no inició'):g.start_model({})

def test_unresponsive_process_has_timeout(local,monkeypatch):
 monkeypatch.setattr(g,'model_data',lambda url:None)
 monkeypatch.setattr(g,'spawn',lambda *a:SimpleNamespace(poll=lambda:None))
 with pytest.raises(g.StartError,match='a tiempo'):g.start_model({})


def test_launchd_reuses_a_running_local_ollama(tmp_path,monkeypatch):
 import gestionar_demo_mac as mac

 runtime=tmp_path/'.runtime'
 (runtime/'postgresql').mkdir(parents=True)
 (runtime/'postgresql/PG_VERSION').write_text('16')
 (tmp_path/'.venv_webui/bin').mkdir(parents=True)
 (tmp_path/'.venv_webui/bin/python').touch()
 (tmp_path/'postgres').touch()
 monkeypatch.setattr(mac,'D',tmp_path)
 monkeypatch.setattr(mac,'RUN',runtime)
 monkeypatch.setattr(mac,'find_bin',lambda *args:tmp_path)
 monkeypatch.setattr(mac,'tcp',lambda *args:True)
 monkeypatch.setattr(mac,'model_data',lambda url:{'models':[{'name':'qwen3:1.7b'}]})
 monkeypatch.setattr(mac,'model_binary',lambda:pytest.fail('Ollama ya está en ejecución'))
 monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:11434')
 monkeypatch.setenv('GENERATION_MODEL','qwen3:1.7b')
 started=[]
 monkeypatch.setattr(mac,'start_job',lambda name,*args,**kwargs:started.append(name))
 mac.start({'web':{'PG_PORT':'55442'},'api_port':18129,'ui_port':3187})
 assert started==['postgresql','api','webui']


def test_launchd_waits_for_its_process_to_exit(monkeypatch):
 import gestionar_demo_mac as mac

 calls=[]
 monkeypatch.setattr(mac,'job_info',lambda name:'state = running\n    pid = 123\n')
 monkeypatch.setattr(mac,'launchctl',lambda action,target:calls.append(action) or SimpleNamespace(returncode=0))
 def process(pid):
  assert pid==123
  return SimpleNamespace(wait=lambda timeout:calls.append('wait'))
 monkeypatch.setattr(mac.psutil,'Process',process)
 mac.unload('api')
 assert calls==['bootout','wait']
