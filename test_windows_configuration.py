from pathlib import Path
from contextlib import contextmanager
import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
import configurar_webui_windows as config
import iniciar_webui

@pytest.fixture
def destination(tmp_path,monkeypatch):
 monkeypatch.setattr(config,'D',tmp_path)
 @contextmanager
 def connect(**kwargs):
  class Cursor:
   def fetchone(self):return (kwargs['dbname'],kwargs['user'])
  class Connection:
   def execute(self,query):assert query=='SELECT current_database(), current_user';return Cursor()
  yield Connection()
 monkeypatch.setattr(config.psycopg,'connect',connect)
 return tmp_path

def test_windows_configuration_preserves_special_password(destination):
 password='p@ss:/#% con espacios'
 path=config.configure('127.0.0.1',5432,'demo_webui','demo_webui',password)
 values=dotenv_values(path);url=make_url(values['WEBUI_DATABASE_URL'])
 assert url.password==password and values['WEBUI_PG_PASSWORD']==password
 assert values['MANAGE_LOCAL_POSTGRES']=='false'
 assert Path(values['WEBUI_DATA_DIR'])==Path('.runtime/webui')
 assert url.port==5432 and url.database=='demo_webui'

def test_existing_config_is_not_overwritten(destination):
 path=destination/'.env.webui';path.write_text('CONSERVAR=si\n')
 with pytest.raises(ValueError,match='ya existe'):config.configure('127.0.0.1',5432,'demo_webui','demo_webui','clave')
 assert path.read_text()=='CONSERVAR=si\n'

def test_failed_connection_does_not_save_password(destination,monkeypatch):
 def fail(**kwargs):raise config.psycopg.OperationalError('fallo de conexión')
 monkeypatch.setattr(config.psycopg,'connect',fail)
 with pytest.raises(config.psycopg.OperationalError):config.configure('127.0.0.1',5432,'demo_webui','demo_webui','privada')
 assert not (destination/'.env.webui').exists()

@pytest.mark.parametrize('port',[0,65536])
def test_invalid_port(destination,port):
 with pytest.raises(ValueError,match='puerto'):config.configure('127.0.0.1',port,'demo_webui','demo_webui','clave')

def test_empty_password(destination):
 with pytest.raises(ValueError,match='obligatorios'):config.configure('127.0.0.1',5432,'demo_webui','demo_webui','')

def test_mismatched_identity_does_not_save(destination,monkeypatch):
 @contextmanager
 def wrong(**kwargs):
  class Cursor:
   def fetchone(self):return ('otra_base','otro_usuario')
  class Connection:
   def execute(self,query):return Cursor()
  yield Connection()
 monkeypatch.setattr(config.psycopg,'connect',wrong)
 with pytest.raises(ValueError,match='no corresponde'):config.configure('127.0.0.1',5432,'demo_webui','demo_webui','clave')
 assert not (destination/'.env.webui').exists()

def test_interface_runs_with_current_python(tmp_path,monkeypatch):
 monkeypatch.setattr(iniciar_webui.sys,'executable',str(tmp_path/'Scripts/python.exe'))
 command=iniciar_webui.command()
 assert command[0]==str(tmp_path/'Scripts/python.exe')
 assert command[3:6]==['serve','--host','127.0.0.1']


def test_old_ollama_setting_cannot_bypass_the_demo(tmp_path):
 from sqlalchemy import JSON, Column, MetaData, String, Table, create_engine, select

 url = 'sqlite:///' + str(tmp_path / 'settings.sqlite')
 engine = create_engine(url)
 metadata = MetaData()
 config = Table('config', metadata, Column('key', String, primary_key=True), Column('value', JSON))
 metadata.create_all(engine)
 with engine.begin() as connection:
  connection.execute(config.insert(), [
   {'key': 'ollama.enable', 'value': True},
   {'key': 'ui.default_models', 'value': 'qwen3:1.7b'},
   {'key': 'ui.default_locale', 'value': 'es'},
  ])
 iniciar_webui.configure_chat({'DATABASE_URL': url, 'DEFAULT_MODELS': 'pln_documental'})
 with engine.connect() as connection:
  settings = dict(connection.execute(select(config)).all())
 assert settings == {'ollama.enable': False, 'ui.default_models': 'pln_documental', 'ui.default_locale': 'es'}
 engine.dispose()
