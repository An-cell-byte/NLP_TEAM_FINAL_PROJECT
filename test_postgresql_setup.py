from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from dotenv import dotenv_values
import configurar_postgresql as p

@pytest.fixture
def local(tmp_path,monkeypatch):
 monkeypatch.setattr(p,'D',tmp_path);monkeypatch.setattr(p,'find_bin',lambda:tmp_path/'bin');monkeypatch.setattr(p,'port_busy',lambda port:False)
 return tmp_path

def pending(root,port=55441):
 data=root/'.runtime/postgresql';data.mkdir(parents=True);(data/'PG_VERSION').write_text('16');(data/'postgresql.conf').write_text("port = 55441\nlisten_addresses = '127.0.0.1'\n")
 value={'project':str(root.resolve()),'data':str(data.resolve()),'pg_bin':str(root/'bin'),'port':port,'admin_password':'privada_admin','app_password':'privada_app'}
 p.save_pending(root/p.PENDING_NAME,value,new=True);return value

def test_occupied_port_does_not_create_instance_or_keys(local,monkeypatch):
 monkeypatch.setattr(p,'port_busy',lambda port:True)
 with pytest.raises(ValueError,match='ocupado'):p.setup(55440)
 assert not (local/'.runtime').exists() and not (local/p.PENDING_NAME).exists()

def test_existing_configuration_preserved(local,monkeypatch):
 target=local/'.env.webui';target.write_text('CONSERVAR=si\n')
 monkeypatch.setattr(p,'port_busy',lambda port:pytest.fail('No debe tocar una instalación existente'))
 assert 'conserva' in p.setup(55442);assert target.read_text()=='CONSERVAR=si\n'

@pytest.mark.parametrize('port',[0,1023,65536])
def test_invalid_port(local,port):
 with pytest.raises(ValueError,match='puerto'):p.setup(port)

def test_legacy_instance_not_deleted_or_reinitialized(local):
 data=local/'.runtime/postgresql';data.mkdir(parents=True);(data/'PG_VERSION').write_text('16')
 with pytest.raises(ValueError,match='sin claves'):p.setup(55441)
 assert (data/'PG_VERSION').read_text()=='16'

def test_other_project_pending_not_used(local):
 value=pending(local);value['project']='otro_proyecto';p.save_pending(local/p.PENDING_NAME,value)
 with pytest.raises(ValueError,match='otra carpeta'):p.setup()

def test_version_mismatch_preserves_data(local,monkeypatch):
 pending(local);monkeypatch.setattr(p,'binary_major',lambda binaries:'17')
 with pytest.raises(ValueError,match='versión'):p.setup()
 assert (local/'.runtime/postgresql/PG_VERSION').read_text()=='16'

def test_retry_keeps_credentials_and_allows_new_port(local,monkeypatch):
 passwords=[];starts=[]
 def initialize(binary,data,password,runtime):
  passwords.append(password);data.mkdir();(data/'PG_VERSION').write_text('16');(data/'postgresql.conf').write_text('port = 55440\n')
 def run(command,**kwargs):
  if command[-1]=='status':return SimpleNamespace(returncode=3)
  starts.append(command);return SimpleNamespace(returncode=1 if len(starts)==1 else 0)
 monkeypatch.setattr(p,'initialize',initialize);monkeypatch.setattr(p.subprocess,'run',run);monkeypatch.setattr(p,'binary_major',lambda binaries:'16')
 monkeypatch.setattr(p,'provision',lambda port,value:None)
 with pytest.raises(ValueError,match='claves'):p.setup(55441)
 saved=json.loads((local/p.PENDING_NAME).read_text());assert saved['admin_password']==passwords[0]
 assert '55442' in p.setup(55442)
 cfg=dotenv_values(local/'.env.webui');assert cfg['PG_ADMIN_PASSWORD']==saved['admin_password'];assert cfg['WEBUI_PG_PASSWORD']==saved['app_password'];assert cfg['PG_PORT']=='55442'
 assert len(passwords)==1 and not (local/p.PENDING_NAME).exists()


def test_pending_ready_instance_resumed_without_restart(local,monkeypatch):
 pending(local);data=local/'.runtime/postgresql';(data/'postmaster.pid').write_text('100\n'+str(data.resolve())+'\n123\n55441\n')
 monkeypatch.setattr(p,'binary_major',lambda binaries:'16')
 def run(command,**kwargs):assert command[-1]=='status';return SimpleNamespace(returncode=0)
 monkeypatch.setattr(p.subprocess,'run',run);monkeypatch.setattr(p,'provision',lambda port,value:None);monkeypatch.setattr(p,'configure_port',lambda *args:pytest.fail('Instancia iniciada'))
 assert '55441' in p.setup()


def test_running_instance_cannot_silently_change_port(local,monkeypatch):
 pending(local);data=local/'.runtime/postgresql';(data/'postmaster.pid').write_text('100\n'+str(data.resolve())+'\n123\n55441\n')
 monkeypatch.setattr(p,'binary_major',lambda binaries:'16');monkeypatch.setattr(p.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=0))
 with pytest.raises(ValueError,match='otro puerto'):p.setup(55442)
 assert (data/'postgresql.conf').read_text().startswith('port = 55441')


def test_publish_does_not_overwrite_existing_file(local):
 value={'admin_password':'admin_privado','app_password':'app_privada'};target=local/'.env.webui';target.write_text('CONSERVAR=si\n')
 with pytest.raises(FileExistsError):p.publish(target,local/'bin',local/'.runtime/postgresql',55441,value)
 assert target.read_text()=='CONSERVAR=si\n'


def test_configure_port_preserves_other_settings(local):
 data=local/'data';data.mkdir();path=data/'postgresql.conf';path.write_text("# port = 5432\nport = 55440\nmax_connections = 50\nport = 55439\n")
 p.configure_port(data,55441);text=path.read_text();assert 'max_connections = 50' in text;assert text.count('\nport = ')==1;assert '\nport = 55441\n' in text
