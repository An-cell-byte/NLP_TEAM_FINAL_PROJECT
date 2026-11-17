from types import SimpleNamespace
from sqlalchemy.engine import make_url
import pytest
from storage import database_url,mysql_candidates
from migrar_desde_postgresql import equivalent

def test_password_special_characters(monkeypatch):
 for k,v in {'STORAGE_BACKEND':'mysql','MYSQL_HOST':'127.0.0.1','MYSQL_PORT':'8889','MYSQL_DATABASE':'demo_prueba','MYSQL_USER':'lector','MYSQL_PASSWORD':'p@ss:/#% con espacios'}.items():monkeypatch.setenv(k,v)
 url=database_url();assert make_url(url).password=='p@ss:/#% con espacios'
 assert make_url(url).database=='demo_prueba'

def test_missing_password(monkeypatch):
 monkeypatch.setenv('STORAGE_BACKEND','mysql');monkeypatch.delenv('MYSQL_PASSWORD',raising=False)
 with pytest.raises(RuntimeError,match='configurar MySQL'):database_url()

def test_cosine_order_and_limit():
 rows=[SimpleNamespace(id='opuesto',embedding=[-1,0]),SimpleNamespace(id='similar',embedding=[1,1]),SimpleNamespace(id='igual',embedding=[2,0])]
 assert [r.id for r in mysql_candidates(rows,[1,0],2)]==['igual','similar']

def test_zero_and_missing_vectors():
 rows=[SimpleNamespace(id='ausente',embedding=None),SimpleNamespace(id='cero',embedding=[0,0]),SimpleNamespace(id='valido',embedding=[1,0])]
 assert [r.id for r in mysql_candidates(rows,[1,0])]==['valido','cero','ausente']

def test_json_float_rounding_does_not_change_identity():
 assert equivalent({'score':0.1234567890123456},{'score':0.12345678901234561})
 assert not equivalent({'id':'001'},{'id':'1'})
 assert not equivalent({'importe':'12.50'},{'importe':'12.51'})
 assert not equivalent({'owner':'A'},{'owner':'a'})

def test_real_numeric_difference_is_rejected():
 assert not equivalent({'score':0.5},{'score':0.5001})
