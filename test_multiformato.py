from pathlib import Path
from decimal import Decimal
import pytest,readers
from tabular import calculate
D=Path(__file__).parent/'datos'
@pytest.mark.parametrize('name',['politicas.txt','politicas.pdf','prestamos.csv','biblioteca.xlsx','biblioteca.json'])
def test_formatos(name):
 result=readers.load(name,(D/name).read_bytes());assert result['parts'];assert all(p['location'] and p['text'] for p in result['parts'])
@pytest.mark.parametrize('name',['x.txt','x.pdf','x.csv','x.xlsx','x.json'])
def test_vacios(name):
 with pytest.raises(ValueError):readers.load(name,b'')
@pytest.mark.parametrize('name,raw',[('x.pdf',b'no pdf'),('x.xlsx',b'no excel'),('x.json',b'{invalid'),('x.csv',b'a,a\n1,2'),('x.txt',b'\xff'),('x.xls',b'legacy'),('x.xlsm',b'macros')])
def test_invalidos(name,raw):
 with pytest.raises(ValueError):readers.load(name,raw)
def test_totales():
 t=readers.load('prestamos.csv',(D/'prestamos.csv').read_bytes())['tables']['datos']
 assert Decimal(calculate(t,'sum','importe')['result'])==20
 assert Decimal(calculate(t,'mean','importe')['result'])==10
 assert calculate(t,'count')['result']==3
 assert calculate(t,'sum','importe')['missing_values_excluded']==1
 assert calculate(t,'rows',filters=[{'column':'id','op':'eq','value':2}])['result'][0]['libro']=='Bases de datos'
def test_formula():
 data=readers.load('biblioteca.xlsx',(D/'biblioteca.xlsx').read_bytes(),{'sheet':'Formulas'});assert data['tables']['Formulas']['rows'][0]['values']['resultado'] is None;assert any('sin resultado' in w for w in data['warnings'])
def test_json():
 data=readers.load('biblioteca.json',(D/'biblioteca.json').read_bytes());assert any('duracion_dias' in p['location']['path'] for p in data['parts']);assert '$["prestamos"]' in data['tables']
def test_limite(monkeypatch):
 monkeypatch.setattr(readers,'MAX_BYTES',2)
 with pytest.raises(ValueError):readers.load('x.txt',b'tres')
def test_decimales():
 t=readers.load('x.csv',b'codigo;importe\n001;12,50',{'decimal':','})['tables']['datos'];assert t['rows'][0]['values']['codigo']=='001';assert calculate(t,'sum','importe')['result']=='12.50'
def test_json_invalido():
 for raw in [b'{"a":1,"a":2}',('['*25+'1'+']'*25).encode()]:
  with pytest.raises(ValueError):readers.load('x.json',raw)
def test_operacion_invalida():
 t=readers.load('prestamos.csv',(D/'prestamos.csv').read_bytes())['tables']['datos']
 with pytest.raises(ValueError):calculate(t,'DROP TABLE prestamos')
 with pytest.raises(ValueError):calculate(t,'sum','inexistente')

@pytest.mark.parametrize('name',['politicas.txt','politicas.pdf','biblioteca.xlsx','prestamos.csv','biblioteca.json'])
def test_limite_bytes_cada_formato(monkeypatch,name):
 monkeypatch.setattr(readers,'MAX_BYTES',1)
 with pytest.raises(ValueError):readers.load(name,((Path(__file__).resolve().parent/'datos')/name).read_bytes())

def test_limites_estructura(monkeypatch):
 monkeypatch.setattr(readers,'MAX_ROWS',1)
 for name in ['prestamos.csv','biblioteca.xlsx','biblioteca.json']:
  with pytest.raises(ValueError):readers.load(name,((Path(__file__).resolve().parent/'datos')/name).read_bytes())

def test_limite_paginas(monkeypatch):
 monkeypatch.setattr(readers,'MAX_PAGES',1)
 with pytest.raises(ValueError):readers.load('x.pdf',(Path(__file__).resolve().parent/'datos/politicas.pdf').read_bytes())

def test_limite_hojas(monkeypatch):
 monkeypatch.setattr(readers,'MAX_SHEETS',1)
 with pytest.raises(ValueError):readers.load('x.xlsx',(Path(__file__).resolve().parent/'datos/biblioteca.xlsx').read_bytes())

def test_seleccion_hoja():
 parsed=readers.load('x.xlsx',(Path(__file__).resolve().parent/'datos/biblioteca.xlsx').read_bytes(),{'sheet':'Usuarios'})
 assert list(parsed['tables'])==['Usuarios']
 with pytest.raises(ValueError):readers.load('x.xlsx',(Path(__file__).resolve().parent/'datos/biblioteca.xlsx').read_bytes(),{'sheet':'No existe'})
