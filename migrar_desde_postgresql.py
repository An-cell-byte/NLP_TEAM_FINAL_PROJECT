"""Copia reversible de la persistencia del curso. El origen nunca se modifica."""
from pathlib import Path
import os,json,hashlib,argparse,math
import numpy as np
from dotenv import dotenv_values,load_dotenv
from sqlalchemy import create_engine,select,func

D=Path(__file__).resolve().parent
def plain(value):
 if hasattr(value,'tolist'):return value.tolist()
 if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
 if isinstance(value,(tuple,list)):return [plain(v) for v in value]
 return value

def equivalent(a,b):
 if isinstance(a,float) and isinstance(b,float):return math.isclose(a,b,rel_tol=1e-14,abs_tol=1e-15)
 if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(equivalent(a[k],b[k]) for k in a)
 if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
 return type(a)==type(b) and a==b

def migrate(execute=False):
 source_url=dotenv_values(D/'.env').get('DATABASE_URL','')
 if not source_url.startswith('postgresql+psycopg://'):raise ValueError('El DATABASE_URL original de .env no es PostgreSQL. No se copiará nada.')
 load_dotenv(D/'.env');load_dotenv(D/'.env.mysql',override=True)
 if os.getenv('STORAGE_BACKEND')!='mysql':raise ValueError('Configura primero .env.mysql para MySQL.')
 from app import Base,ENGINE,Document,Chunk,Turn,SourceManifest,Structure,Location,Connection
 TABLES=[model.__tablename__ for model in [Document,Chunk,Turn,SourceManifest,Structure,Location,Connection]]
 source=create_engine(source_url,hide_parameters=True);counts={};source_rows={}
 try:
  with source.connect() as con:
   for name in TABLES:
    table=Base.metadata.tables[name];rows=[plain(dict(r)) for r in con.execute(select(table)).mappings()];source_rows[name]=rows;counts[name]=len(rows)
  with ENGINE.begin() as target:
   if any(target.execute(select(func.count()).select_from(Base.metadata.tables[n])).scalar() for n in TABLES):raise ValueError('La base de destino contiene datos; no se sobrescribió. La migración requiere un destino vacío.')
   if execute:
    for name in TABLES:
     rows=source_rows[name];table=Base.metadata.tables[name]
     for start in range(0,len(rows),100):target.execute(table.insert(),rows[start:start+100])
    for name in TABLES:
     actual=[plain(dict(r)) for r in target.execute(select(Base.metadata.tables[name])).mappings()]
     ordered=lambda rs:sorted(rs,key=lambda r:str(r.get('id',r.get('document_id'))))
     canonical=lambda rs:json.dumps(ordered(rs),sort_keys=True,ensure_ascii=False,separators=(',',':'))
     a=ordered(actual);b=ordered(source_rows[name])
     if name=='chunks':
      for left,right in zip(a,b):
       if left['embedding'] is not None or right['embedding'] is not None:
        if not np.array_equal(np.asarray(left['embedding'],dtype='float32'),np.asarray(right['embedding'],dtype='float32')):raise ValueError('Los vectores no coinciden; se revierte la transacción.')
     if not equivalent(a,b):raise ValueError('La copia no coincide en '+name+'; se revierte la transacción.')
  return {'executed':execute,'counts':counts,'validated':'Filas, identificadores, vectores, versiones, propietarios y respuestas coinciden.' if execute else 'Solo revisión; no se insertaron filas.','source_unchanged':True,'numeric_validation':'Vectores idénticos a precisión float32; flotantes JSON con tolerancia de redondeo binario 1e-14 relativa y 1e-15 absoluta. Texto, identificadores, enteros y decimales textuales se comparan exactamente.'}
 finally:source.dispose();ENGINE.dispose()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--ejecutar',action='store_true');args=parser.parse_args()
 try:print(json.dumps(migrate(args.ejecutar),ensure_ascii=False,indent=2))
 except ValueError as exc:raise SystemExit(str(exc)) from None
 except Exception:raise SystemExit('No se pudo completar la copia. Revisa las conexiones locales. El origen se conserva.') from None
