"""Copia una instantánea SQLite de Open WebUI a una base PostgreSQL vacía."""
from pathlib import Path
import argparse,json,sqlite3,hashlib
from sqlalchemy import create_engine,MetaData,select,func,JSON,Boolean,Text,String
from dotenv import dotenv_values
D=Path(__file__).resolve().parent

def migrate(snapshot,old_root='/app/backend/data'):
 cfg=dotenv_values(D/'.env.webui');url=cfg.get('WEBUI_DATABASE_URL','')
 if not url.startswith('postgresql+psycopg://'):raise ValueError('Falta WEBUI_DATABASE_URL PostgreSQL en .env.webui.')
 snapshot=Path(snapshot).resolve()
 source=sqlite3.connect('file:'+str(snapshot)+'?mode=ro',uri=True);source.row_factory=sqlite3.Row
 engine=create_engine(url,hide_parameters=True);meta=MetaData();meta.reflect(engine);report={}
 try:
  names={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")} - {'alembic_version','sqlite_sequence'}
  if names-set(meta.tables):raise ValueError('El destino no contiene el mismo esquema. Inicializa Open WebUI con la misma versión y detenlo antes de copiar.')
  with engine.begin() as con:
   for name in names:
    if con.scalar(select(func.count()).select_from(meta.tables[name])):raise ValueError('La tabla destino '+name+' contiene datos. Se conserva; utiliza una base vacía.')
   for table in meta.sorted_tables:
    if table.name not in names:continue
    rows=[dict(r) for r in source.execute('SELECT * FROM "'+table.name+'"')];adapted=[]
    for row in rows:
     out={}
     for col in table.columns:
      if col.name not in row:continue
      value=row[col.name]
      if isinstance(col.type,JSON) and isinstance(value,str):value=json.loads(value)
      elif isinstance(col.type,Boolean) and value is not None:value=bool(value)
      if table.name=='file' and col.name=='path' and isinstance(value,str) and value.startswith(old_root+'/'):
       value=str(Path(cfg['WEBUI_DATA_DIR'])/value[len(old_root)+1:])
      out[col.name]=value
     adapted.append(out)
    if adapted:con.execute(table.insert(),adapted)
    actual=list(con.execute(select(table)).mappings())
    if len(actual)!=len(adapted):raise ValueError('No coincide el número de filas de '+table.name)
    # Cada campo se contrasta antes de confirmar la transacción.
    keys=[col.name for col in table.primary_key]
    def key(r):return tuple(str(r[k]) for k in keys)
    expected={key(r):r for r in adapted}
    for row in actual:
     record=expected[key(row)]
     for k,v in record.items():
      if row[k]!=v:raise ValueError('No coincide el campo '+table.name+'.'+k)
    report[table.name]=len(rows)
  return {'estado':'PASS','tablas':report,'comparacion':'Campos, cuentas, hashes de acceso, mensajes y permisos iguales; solo rutas de adjuntos adaptadas.','origen_modificado':False}
 finally:source.close();engine.dispose()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('snapshot');p.add_argument('--informe',default='');args=p.parse_args()
 try:report=migrate(args.snapshot)
 except ValueError as exc:raise SystemExit(str(exc)) from None
 if args.informe:Path(args.informe).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('Copia comprobada: '+str(sum(report['tablas'].values()))+' filas. Origen conservado.')
