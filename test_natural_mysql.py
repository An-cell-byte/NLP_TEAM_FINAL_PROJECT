from decimal import Decimal
import pytest
import natural_mysql as n

def table():
 return {'columns':['id','usuario_id','nombre','libro','importe','fecha'],'rows':[{'values':dict(id=str(i),usuario_id=str(u),nombre=name,libro=book,importe=amount,fecha='2026-11-01'),'types':{'id':'decimal','usuario_id':'decimal','nombre':'text','libro':'text','importe':'decimal','fecha':'date'},'location':{'kind':'database','identifiers':{'id':i}}} for i,u,name,book,amount in [(1,10,'Ana','PLN aplicado','12.50'),(2,10,'Ana','Bases de datos','7.50'),(3,20,'Luis','Redes neuronales',None)]]}

@pytest.fixture
def source(monkeypatch):
 monkeypatch.setattr(n.db_sources,'policies',lambda:{'aurora_mamp':{'tables':{'prestamos_detalle':table()['columns']}}})
 monkeypatch.setattr(n.db_sources,'config',lambda a,o:({},'mysql+pymysql://localhost/demo'))
 monkeypatch.setattr(n.db_sources,'read',lambda *args:(table(),'2026-11-04T00:00:00+00:00','mysql'))

@pytest.mark.parametrize('question,expected',[( '¿Cuántos préstamos hay en MySQL?',3),('¿Cuántos préstamos tiene Ana?',2),('¿Cuántos préstamos tiene Luis?',1),('¿Cuál es el importe total de los préstamos?','20.00'),('¿Cuál es el importe promedio de los préstamos?','10.00'),('¿Cuál es el importe máximo de los préstamos?','12.50'),('¿Cuál es el importe mínimo de los préstamos?','7.50')])
def test_known_questions(source,question,expected):
 result=n.answer(question,[],'cuenta');assert result['kind']=='mysql_natural';assert result['database_result']['result']==expected

def test_chat_answer_shows_result_and_keeps_metadata_separately(source):
 result=n.answer('¿Cuántos préstamos tiene Ana?',[],'cuenta')
 assert result['answer']=='Ana tiene 2 préstamos.'
 assert n.render_answer(result['database_result'],variant=1)=='Encontré 2 préstamos de Ana.'
 assert result['database_result']['filters']==[{'column':'nombre','op':'eq','value':'Ana'}]
 assert result['database_result']['source']['dataset']=='prestamos_detalle'

def test_grouping(source):
 r=n.answer('¿Cuántos préstamos tiene cada usuario?',[],'cuenta');assert r['database_result']['groups']==[{'group':'Ana','result':2},{'group':'Luis','result':1}]
 assert r['answer']=='Ana tiene 2 préstamos.\n\nLuis tiene 1 préstamo.'

def test_document_question_stays_documental():assert not n.relevant('¿Cuánto dura el préstamo?',[])

@pytest.mark.parametrize('question',[
 '¿Cuántos préstamos se permiten por persona?',
 '¿Cuántos préstamos están permitidos a cada persona?',
 '¿Cuántos libros puedo pedir prestados?',
])
def test_borrowing_limits_use_documents(question):
 assert not n.relevant(question,[])
 assert 'limite de libros por persona' in n.document_question(question)
 assert not n.relevant('¿Y Luis?',[{'role':'user','content':question}])

def test_explicit_mysql_takes_precedence():
 assert n.relevant('¿Cuántos préstamos se permiten por persona en MySQL?',[])

def test_no_unauthorized_query(source,monkeypatch):
 monkeypatch.setattr(n.db_sources,'config',lambda *args:(_ for _ in ()).throw(ValueError()))
 assert n.answer('¿Cuántos préstamos hay en MySQL?',[],'otra')['abstained']

def test_revoked_source(source):assert n.answer('¿Cuántos préstamos hay en MySQL?',[],'cuenta',['aurora_mamp'])['abstained']

def test_no_write(source):assert n.answer('Elimina los préstamos de MySQL',[],'cuenta')['abstained']

def test_unknown_column_and_sql_rejected():
 with pytest.raises(ValueError):n.validate(n.Plan(operation='sum',column='password'),table(),'total',[])
 with pytest.raises(ValueError):n.Plan.model_validate({'operation':'rows','sql':'DROP TABLE usuarios'})

def test_invented_filter_rejected():
 with pytest.raises(ValueError):n.validate(n.Plan(operation='count',filters=[n.Filter(column='nombre',value='Luis')]),table(),'prestamos de Ana',[])

def test_missing_not_zero(source):
 r=n.answer('¿Cuál es el importe promedio de los préstamos?',[],'cuenta')
 assert r['database_result']['missing_values_excluded']==1
 assert r['answer']=='El importe promedio de los préstamos es de 10.00. Lo calculé con 2 valores disponibles.'
 assert n.render_answer(r['database_result'],variant=1)=='10.00 es el importe promedio de los préstamos. Lo calculé con 2 valores disponibles.'

def test_unknown_person_not_all_rows(source,monkeypatch):
 monkeypatch.setattr(n,'model_plan',lambda *a:n.Plan(operation='count',filters=[n.Filter(column='nombre',value='Pedro')]))
 r=n.answer('¿Cuántos préstamos tiene Pedro en MySQL?',[],'cuenta');assert r['database_result']['result']==0
 assert r['answer']=='No encontré préstamos de Pedro.'

def test_followup_replaces_person(source,monkeypatch):
 monkeypatch.setattr(n,'model_plan',lambda *a:n.Plan(operation='count',filters=[n.Filter(column='nombre',value='Luis')]))
 r=n.answer('¿Y Luis?',[{'role':'user','content':'¿Cuántos préstamos tiene Ana?'}],'cuenta');assert r['database_result']['result']==1
 assert r['answer']=='Luis tiene 1 préstamo.'


def test_list_formats_limited_results_as_a_table():
 from tabular import calculate, render_answer

 result=calculate(table(),'rows',filters=[{'column':'nombre','value':'Ana'}],limit=1)
 result['source']={'dataset':'prestamos_detalle'}
 answer=render_answer(result)
 assert answer.startswith('Encontré 2 préstamos de Ana. Aquí puedes ver 1.')
 assert '| ID | ID de usuario | Nombre | Libro | Importe | Fecha |' in answer
 assert 'PLN aplicado' in answer and 'Bases de datos' not in answer


def test_omitted_person_filter_rejected():
 with pytest.raises(ValueError):n.validate(n.Plan(operation='count'),table(),'¿Cuántos préstamos tiene Ana?',[])

def test_people_not_confused_with_rows():
 with pytest.raises(ValueError):n.validate(n.Plan(operation='count'),table(),'¿Cuántos usuarios hay en MySQL?',[])
