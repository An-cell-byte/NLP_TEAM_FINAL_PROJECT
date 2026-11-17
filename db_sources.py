"""Conectores controlados: las credenciales se resuelven en el servidor, no desde el chat."""
from datetime import datetime,timezone
import os,json
from sqlalchemy import create_engine,MetaData,Table,Column,select,text
from readers import typed,MAX_ROWS

def policies():
 try:return json.loads(os.environ.get('SOURCE_CONNECTIONS','{}'))
 except ValueError:raise ValueError('La configuración de conexiones no es válida.') from None

def config(alias,owner=None):
 p=policies().get(alias)
 if not p or not p.get('url_env') or not isinstance(p.get('tables'),dict):raise ValueError('Conexión no autorizada por el administrador.')
 if owner is not None and not p.get('public_demo',False) and owner not in p.get('allowed_owners',[]):raise ValueError('Tu cuenta no tiene autorización para esta conexión.')
 url=os.environ.get(p['url_env'],'')
 if not url:raise ValueError('Faltan las credenciales de lectura de esta conexión.')
 if not url.startswith(('postgresql+psycopg://','mysql+pymysql://')):raise ValueError('Solo se admiten PostgreSQL y MySQL con sus controladores fijados.')
 return p,url

def read(alias,dataset,owner=None):
 p,url=config(alias,owner)
 if dataset not in p['tables']:raise ValueError('Tabla o vista no autorizada.')
 allowed=p['tables'][dataset]
 if not isinstance(allowed,list) or not allowed:raise ValueError('No hay columnas autorizadas.')
 engine=create_engine(url,pool_pre_ping=True,hide_parameters=True,connect_args={'connect_timeout':5})
 try:
  with engine.connect() as con:
   if engine.dialect.name=='postgresql':
    con.execute(text('SET TRANSACTION READ ONLY'));con.execute(text("SET LOCAL statement_timeout = '5000ms'"))
   else:
    con.execute(text('SET SESSION MAX_EXECUTION_TIME=5000'));con.execute(text('SET TRANSACTION READ ONLY'))
   # Identificadores solo de una política administrativa, nunca texto libre generado por el modelo.
   if '.' in dataset:schema,name=dataset.split('.',1)
   else:schema,name=None,dataset
   t=Table(name,MetaData(),*(Column(k) for k in allowed),schema=schema)
   records=con.execute(select(*(t.c[k] for k in allowed)).limit(MAX_ROWS+1)).mappings().all()
   if len(records)>MAX_ROWS:raise ValueError('La consulta supera el límite de filas; utiliza una vista administrativa más acotada.')
   rows=[];stamp=datetime.now(timezone.utc).isoformat()
   for i,row in enumerate(records,1):
    cells={k:typed(row[k]) for k in allowed}
    rows.append({'values':{k:v[0] for k,v in cells.items()},'types':{k:v[1] for k,v in cells.items()},'location':{'kind':'database','connection':alias,'table':dataset,'row':i,'identifiers':{k:row[k] for k in allowed if k=='id' or k.endswith('_id')},'queried_at':stamp}})
   return {'columns':allowed,'rows':rows},stamp,engine.dialect.name
 except ValueError:raise
 except Exception:raise ValueError('No fue posible consultar la fuente. Revisa servicio, permisos de solo lectura y configuración del servidor.') from None
 finally:engine.dispose()
