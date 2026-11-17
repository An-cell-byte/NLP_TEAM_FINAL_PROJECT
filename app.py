"""Servicios del curso. Open WebUI administra cuentas e historial; esta API administra evidencia."""
from pathlib import Path
from urllib.parse import unquote
from datetime import datetime, timezone
import os, uuid, json, hashlib, hmac, time, re, logging
import numpy as np
import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, delete as delete_rows, func, text, select, String, Text, Integer, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, mapped_column, Session
from sqlalchemy.dialects.mysql import LONGTEXT
from fastapi.responses import JSONResponse
from storage import make_engine,query_session,mysql_candidates,QueryBusy
from pgvector.sqlalchemy import Vector
from baseline.core import read_document, chunk_pages, evidence_check, content_terms, term_key, support_keys
from exercises import rank_candidates, produce_answer
import readers
from tabular import calculate, render_answer
import db_sources
import natural_mysql
LOG=logging.getLogger('chatbot'); logging.basicConfig(level=logging.INFO)
ENGINE=make_engine()
CONTENT_TEXT=Text().with_variant(LONGTEXT(),'mysql')
EMBEDDING_TYPE=Vector(384).with_variant(JSON(),'mysql')
SECRET=os.environ.get('BRIDGE_SECRET','')
if len(SECRET)<32:raise RuntimeError('BRIDGE_SECRET debe contener al menos 32 caracteres; ejecuta configurar.py.')
class Base(DeclarativeBase):pass
class Document(Base):
 __tablename__='documents'
 id=mapped_column(String(512),primary_key=True);owner=mapped_column(String(128),index=True);name=mapped_column(String(255))
 version=mapped_column(Integer,default=1);status=mapped_column(String(255));error=mapped_column(CONTENT_TEXT,default='');digest=mapped_column(String(255));deleted=mapped_column(Boolean,default=False)
 body=mapped_column(CONTENT_TEXT,default='')
class Chunk(Base):
 __tablename__='chunks'
 id=mapped_column(String(512),primary_key=True);document_id=mapped_column(String(255),index=True);owner=mapped_column(String(128),index=True)
 version=mapped_column(Integer);page=mapped_column(Integer);section=mapped_column(String(255),default='');source=mapped_column(String(255));body=mapped_column(CONTENT_TEXT);digest=mapped_column(String(255));embedding=mapped_column(EMBEDDING_TYPE,nullable=True)
class Turn(Base):
 __tablename__='turns';__table_args__=(UniqueConstraint('owner','request_id'),)
 id=mapped_column(String(512),primary_key=True);owner=mapped_column(String(128),index=True);request_id=mapped_column(String(128));query=mapped_column(CONTENT_TEXT);response=mapped_column(JSON)
class SourceManifest(Base):
 __tablename__='source_manifest'
 document_id=mapped_column(String(512),primary_key=True);version=mapped_column(Integer);chunks=mapped_column(JSON)
class Structure(Base):
 __tablename__=os.getenv('STRUCTURES_TABLE','document_structures')
 document_id=mapped_column(String(512),primary_key=True);version=mapped_column(Integer);data=mapped_column(JSON)
class Location(Base):
 __tablename__=os.getenv('LOCATIONS_TABLE','document_locations')
 id=mapped_column(String(512),primary_key=True);document_id=mapped_column(String(255),index=True);data=mapped_column(JSON)
class DocumentAttachment(Base):
 __tablename__='document_attachments'
 document_id=mapped_column(String(64),primary_key=True)
 version=mapped_column(Integer,primary_key=True)
 file_id=mapped_column(String(64),index=True)
class Connection(Base):
 __tablename__=os.getenv('CONNECTIONS_TABLE','source_connections')
 id=mapped_column(String(512),primary_key=True);owner=mapped_column(String(128),index=True);alias=mapped_column(String(255));revoked=mapped_column(Boolean,default=False)
app=FastAPI(title='Qwerty',version='1.4.0')
encoder=None

def initialize():
 if ENGINE.dialect.name=='postgresql':
  with ENGINE.begin() as c:c.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
 elif ENGINE.dialect.name!='mysql':raise RuntimeError('Motores de persistencia admitidos: MySQL y PostgreSQL.')
 Base.metadata.create_all(ENGINE)
initialize()

@app.exception_handler(QueryBusy)
def query_busy_handler(request,exc):return JSONResponse(status_code=503,content={'detail':str(exc)})

def signature(owner,stamp,body,attachment=''):
 if attachment:body=b'qwerty-attachment\0'+attachment.encode()+b'\0'+body
 return hmac.new(SECRET.encode(),owner.encode()+b'\n'+stamp.encode()+b'\n'+body,hashlib.sha256).hexdigest()
async def identity(request:Request):
 owner=request.headers.get('X-Owner','');stamp=request.headers.get('X-Time','');sig=request.headers.get('X-Signature','')
 attachment=request.headers.get('X-Attachment-ID','')
 try:valid=bool(owner) and abs(time.time()-int(stamp))<90 and hmac.compare_digest(sig,signature(owner,stamp,await request.body(),attachment))
 except ValueError:valid=False
 if not valid:raise HTTPException(401,'La solicitud debe proceder del puente autenticado de Open WebUI.')
 return owner

def embed(texts):
 global encoder
 if encoder is None:
  from sentence_transformers import SentenceTransformer
  encoder=SentenceTransformer(os.environ.get('EMBEDDING_MODEL','sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'),revision=os.environ.get('EMBEDDING_REVISION','e8f8c211226b894fcb81acc59f3b34ba3efd5f42'),device='cpu',local_files_only=os.environ.get('HF_HUB_OFFLINE')=='1')
 return encoder.encode(texts,normalize_embeddings=True).tolist()

def owned(session,identifier,owner,*,lock=False,include_deleted=False):
 d=session.get(Document,identifier,with_for_update=lock,populate_existing=lock)
 if d is None or d.owner!=owner or (d.deleted and not include_deleted):raise HTTPException(404,'Documento no disponible.')
 return d

@app.get('/health')
def health():
 with ENGINE.connect() as c:c.execute(text('SELECT 1'))
 return {'status':'ok','storage':ENGINE.dialect.name,'generation_model':os.environ.get('GENERATION_MODEL','qwen3:1.7b')}
@app.get('/documents')
def documents(owner=Depends(identity)):
 with Session(ENGINE) as s:return [{'id':d.id,'name':d.name,'version':d.version,'status':d.status,'error':d.error} for d in s.scalars(select(Document).where(Document.owner==owner,Document.deleted==False))]
@app.post('/documents')
async def upload(request:Request,owner=Depends(identity)):
 data=await request.body()
 if len(data)>readers.MAX_BYTES:raise HTTPException(413,'El archivo supera el límite configurado.')
 name=Path(unquote(request.headers.get('X-Filename','documento.txt'))).name
 replace=request.headers.get('X-Replace','')
 attachment=request.headers.get('X-Attachment-ID','')
 if attachment:
  try:attachment=str(uuid.UUID(attachment))
  except ValueError:raise HTTPException(422,'El identificador del adjunto no es válido.') from None
 with Session(ENGINE) as s:
  if replace:
   identifier=replace;previous_version=owned(s,identifier,owner).version
   s.rollback()
  else:
   identifier=str(uuid.uuid4())
   s.add(Document(id=identifier,owner=owner,name=name,version=0,status='procesando',digest=''))
   s.commit()
  try:
   options=json.loads(request.headers.get('X-Read-Options','{}'))
   parsed=readers.load(name,data,options);pieces=parsed['parts']
   vectors=embed([part['text'] for part in pieces])
   if len(vectors)!=len(pieces):raise ValueError('El índice quedó incompleto. Vuelve a intentar la carga.')
   # La versión anterior sigue disponible mientras se prepara el reemplazo.
   d=owned(s,identifier,owner,lock=True)
   if replace and d.version!=previous_version:
    raise HTTPException(409,'Otra carga actualizó el documento. Revisa /documentos antes de sustituirlo.')
   if attachment and s.scalar(select(DocumentAttachment.file_id).join(Document,Document.id==DocumentAttachment.document_id).where(DocumentAttachment.file_id==attachment,Document.status=='purgando').limit(1)):
    raise HTTPException(409,'Ese adjunto tiene una purga en curso.')
   # El manifiesto se construye desde la fuente antes de escribir el índice.
   version=d.version+1;expected=[];new=[]
   for c,vector in zip(pieces,vectors):
    digest=hashlib.sha256(c['text'].encode()).hexdigest();cid=f'{identifier}:v{version}:part{len(new)+1}'
    expected.append({'id':cid,'hash':digest})
    new.append(Chunk(id=cid,document_id=identifier,owner=owner,version=version,page=c['location'].get('page',1),section='',source=name,body=c['text'],digest=digest,embedding=vector))
   s.query(Chunk).filter(Chunk.document_id==identifier).delete()
   s.query(Location).filter(Location.document_id==identifier).delete()
   for c,part in zip(new,pieces):
    s.add(c);s.add(Location(id=c.id,document_id=identifier,data=part['location']))
   structure=s.get(Structure,identifier)
   if structure:structure.version=version;structure.data=parsed
   else:s.add(Structure(document_id=identifier,version=version,data=parsed))
   manifest=s.get(SourceManifest,identifier)
   if manifest:manifest.version=version;manifest.chunks=expected
   else:s.add(SourceManifest(document_id=identifier,version=version,chunks=expected))
   if attachment:s.add(DocumentAttachment(document_id=identifier,version=version,file_id=attachment))
   d.name=name;d.version=version;d.digest=hashlib.sha256(data).hexdigest();d.body='\n'.join(part['text'] for part in pieces);d.status='disponible';d.error='';s.commit()
   return {'id':identifier,'status':d.status,'version':version,'chunks':len(new),'datasets':list(parsed['tables']),'warnings':parsed['warnings']}
  except HTTPException:
   raise
  except Exception as exc:
   s.rollback()
   if isinstance(exc,ValueError):message=str(exc)[:300]
   else:
    LOG.warning('No se completó la carga del documento %s (%s).',identifier,type(exc).__name__)
    message='No pude procesar el archivo. Revisa el estado del servicio y vuelve a intentarlo.'
   d=owned(s,identifier,owner,lock=not replace)
   if not replace:
    d.status='error';d.error=message;s.commit()
   elif d.status=='disponible':
    message+=' Puedes seguir consultando la versión disponible.'
   raise HTTPException(422,{'id':identifier,'status':'error','message':message}) from None
@app.delete('/documents/{identifier}')
def delete(identifier:str,owner=Depends(identity)):
 with Session(ENGINE) as s:
  d=owned(s,identifier,owner,lock=True);d.deleted=True;s.query(Chunk).filter(Chunk.document_id==identifier).delete();s.commit()
 return {'status':'eliminado'}


def purge_attachments(session, document):
 links=session.scalars(select(DocumentAttachment).where(DocumentAttachment.document_id==document.id)).all()
 if not links or len(links)!=document.version:
  raise HTTPException(409,'No se conocen los adjuntos de todas las versiones. Usa el procedimiento manual de la guía.')
 file_ids=sorted({link.file_id for link in links})
 shared=session.scalar(select(DocumentAttachment.file_id).where(DocumentAttachment.file_id.in_(file_ids),DocumentAttachment.document_id!=document.id).limit(1))
 if shared:raise HTTPException(409,'Un adjunto también pertenece a otro documento de Qwerty. Se conservaron ambos.')
 return file_ids


def purge_code(document,expires):
 payload=json.dumps(['qwerty-purga',document.owner,document.id,document.version,expires]).encode()
 return f'{expires}.'+hmac.new(SECRET.encode(),payload,hashlib.sha256).hexdigest()[:24]


class PurgeConfirmation(BaseModel):
 confirmation:str=Field(max_length=80)
 removed_files:list[uuid.UUID]|None=None


@app.get('/documents/{identifier}/purge')
def preview_purge(identifier:str,owner=Depends(identity)):
 with Session(ENGINE) as s:
  document=owned(s,identifier,owner,include_deleted=True)
  return {'name':document.name,'file_ids':purge_attachments(s,document),'confirmation':purge_code(document,int(time.time())+600)}


@app.post('/documents/{identifier}/purge')
def purge(identifier:str,body:PurgeConfirmation,owner=Depends(identity)):
 with Session(ENGINE) as s:
  document=owned(s,identifier,owner,lock=True,include_deleted=True)
  expires,_,_=body.confirmation.partition('.')
  if not body.confirmation.isascii() or not expires.isdigit() or int(expires)<time.time() or not hmac.compare_digest(body.confirmation,purge_code(document,int(expires))):
   raise HTTPException(409,'La confirmación no es válida, venció o el documento cambió. Vuelve a escribir /purgar ID.')
  file_ids=purge_attachments(s,document)
  if body.removed_files is None:
   document.deleted=True;document.status='purgando';s.commit()
   return {'file_ids':file_ids}
  if document.status!='purgando' or {str(file_id) for file_id in body.removed_files}!=set(file_ids):
   raise HTTPException(409,'Primero confirma la retirada de todos los adjuntos de este documento.')

  if ENGINE.dialect.name=='mysql':
   citations=func.json_search(Turn.response,'one',f'{identifier}:v%:part%',None,'$.references[*].id').is_not(None)
   s.execute(delete_rows(Turn).where(Turn.owner==owner,citations))
  else:
   rows=s.execute(select(Turn.id,Turn.response).where(Turn.owner==owner)).yield_per(100)
   cited_ids=[turn_id for turn_id,response in rows if any(isinstance(ref,dict) and str(ref.get('id','')).startswith(identifier+':v') for ref in ((response or {}).get('references') or []))]
   if cited_ids:s.execute(delete_rows(Turn).where(Turn.owner==owner,Turn.id.in_(cited_ids)))
  for table in (Chunk,Location,Structure,SourceManifest,DocumentAttachment):
   s.execute(delete_rows(table).where(table.document_id==identifier))
  s.delete(document);s.commit()
  return {'status':'purgado'}


@app.get('/sources/{identifier:path}')
def source(identifier:str,owner=Depends(identity)):
 with Session(ENGINE) as s:
  c=s.get(Chunk,identifier)
  if c is None or c.owner!=owner:raise HTTPException(404,'Fuente no disponible.')
  d=owned(s,c.document_id,owner)
  if d.status!='disponible' or d.version!=c.version:raise HTTPException(404,'Fuente sustituida.')
  return {'id':c.id,'document':c.source,'page':c.page,'version':c.version,'text':c.body,'location':(s.get(Location,c.id).data if s.get(Location,c.id) else {'kind':'legacy','page':c.page})}
class Query(BaseModel):
 question:str=Field(min_length=1,max_length=2000);request_id:str=Field(default_factory=lambda:str(uuid.uuid4()),max_length=100)
 history:list[dict]=Field(default_factory=list,max_length=12);mode:str='extractivo';search:str='hibrida'

def next_answer_variant(session, owner, question):
    previous = select(func.count()).select_from(Turn).where(Turn.owner == owner, Turn.query == question)
    return session.scalar(previous) % 2


@app.post('/query')
def query(body:Query,owner=Depends(identity)):
 start=time.perf_counter()
 with query_session(ENGINE,owner+body.request_id) as s:
  previous=s.scalar(select(Turn).where(Turn.owner==owner,Turn.request_id==body.request_id))
  if previous:
   if previous.query!=body.question:raise HTTPException(409,'El identificador de envío ya corresponde a otra pregunta.')
   saved=dict(previous.response);saved.pop('role',None)
   if saved.get('kind')=='mysql_natural' and saved.get('database_result') and 'answer_variant' not in saved:
    saved['answer']=render_answer(saved['database_result'],group_by=(saved.get('plan') or {}).get('group_by'))
   if str(saved.get('generation','')).startswith('base_lexica'):saved['generation']='base_lexica'
   return saved
  revoked=[c.alias for c in s.scalars(select(Connection).where(Connection.owner==owner,Connection.revoked==True))]
  natural=natural_mysql.answer(body.question,body.history,owner,revoked)
  if natural is not None:
   if natural.get('kind')=='mysql_natural':
    variant=next_answer_variant(s,owner,body.question)
    natural['answer_variant']=variant
    if variant:
     natural['answer']=render_answer(natural['database_result'],group_by=natural['plan'].get('group_by'),variant=variant)
   natural.update(request_id=body.request_id,query=body.question,latency_ms=round((time.perf_counter()-start)*1000))
   s.add(Turn(id=str(uuid.uuid4()),owner=owner,request_id=body.request_id,query=body.question,response=natural));s.commit();return natural
  permitted=select(Chunk).join(Document,Chunk.document_id==Document.id).where(Chunk.owner==owner,Document.deleted==False,Document.status=='disponible',Chunk.version==Document.version)
  maximum=int(os.getenv('MAX_MYSQL_SEARCH_CHUNKS','5000'))
  chunks=list(s.scalars(permitted.limit(maximum+1) if ENGINE.dialect.name=='mysql' else permitted))
  if ENGINE.dialect.name=='mysql' and len(chunks)>maximum:raise HTTPException(413,'El corpus supera el límite de búsqueda del demo MySQL. Reduce las fuentes o utiliza la ruta PostgreSQL con pgvector.')
  if body.search in ['semantica','hibrida'] and chunks:
   query_vector=embed([body.question])[0]
   candidates=mysql_candidates(chunks,query_vector) if ENGINE.dialect.name=='mysql' else list(s.scalars(permitted.order_by(Chunk.embedding.cosine_distance(query_vector)).limit(50)))
   if body.search=='semantica':chunks=candidates
   # Híbrida conserva los candidatos léxicos y semánticos; el conjunto pequeño se fusiona después.
  q=natural_mysql.document_question(body.question.strip())
  # Historial aportado por Open WebUI. Solo utilizamos la pregunta previa, no respuestas como evidencia.
  if re.match(r'^(y\b|¿?y\b|¿?por cu[aá]ntos|¿?y por)',q.lower()):
   prior=next((m.get('content','') for m in reversed(body.history) if m.get('role')=='user'), '')
   q=(prior+' '+q)[-2500:]
  rows=[{'id':c.id,'document_id':c.document_id,'document':c.source,'page':c.page,'version':c.version,'text':c.body,'vector':c.embedding,'location':(s.get(Location,c.id).data if s.get(Location,c.id) else {'kind':'legacy','page':c.page})} for c in chunks]
  # Las cifras agregadas se obtienen del cálculo, nunca de la redacción del modelo.
  wants_calculation=re.search(r'\b(suma|sumar|promedio|media|máximo|mínimo|total|conteo|contar|mayor|menor)\b|cu[aá]nt[oa]s? (registros|filas|casos|préstamos|prestamos|usuarios|libros)',q.lower())
  tables_available=any((s.get(Structure,c.document_id) and s.get(Structure,c.document_id).data.get('tables')) for c in chunks)
  if wants_calculation and tables_available:
   result={'answer':'Para calcular esa cifra, consulta /documentos y /estructura ID. Después utiliza /calcular con el documento, la tabla, la operación, la columna y los filtros. No calcularé un total a partir de fragmentos parciales.','references':[],'abstained':True,'kind':'requiere_calculo_determinista','request_id':body.request_id,'query':q}
   s.add(Turn(id=str(uuid.uuid4()),owner=owner,request_id=body.request_id,query=body.question,response=result));s.commit();return result
  hits=rank_candidates(q,rows,body.search,embed)
  selected=[]
  for hit in hits[:4]:
   check=evidence_check(q,{'text':hit['text'],'score':hit['lexical']},threshold=0.0)
   # No convertimos una similitud semántica en una certeza de respuesta.
   if check['accepted']:selected.append(hit)
  if not selected and hits:
   joined=' '.join(h['text'] for h in hits[:4]);check=evidence_check(q,{'text':joined,'score':max(h['lexical'] for h in hits)},threshold=0.0)
   if check['accepted']:selected=hits[:4]
  variant=next_answer_variant(s,owner,body.question)
  result=produce_answer(q,selected,body.mode,variant=variant)
  # Una respuesta que terminó durante una sustitución o purga no debe guardar una cita obsoleta.
  for document_id,version in sorted({(hit['document_id'],hit['version']) for hit in selected}):
   current=owned(s,document_id,owner,lock=True,include_deleted=True)
   if current.deleted or current.version!=version:
    raise HTTPException(409,'El documento cambió durante la consulta. Vuelve a hacer la pregunta.')
  result['answer_variant']=variant
  result.update(request_id=body.request_id,query=q,latency_ms=round((time.perf_counter()-start)*1000),search=body.search)
  s.add(Turn(id=str(uuid.uuid4()),owner=owner,request_id=body.request_id,query=body.question,response=result));s.commit()
  LOG.info(json.dumps({'request_id':body.request_id,'latency_ms':result['latency_ms'],'sources':[h['id'] for h in selected]}))
  return result
@app.get('/audit')
def audit(owner=Depends(identity)):
 with Session(ENGINE) as s:
  findings=[]
  for d in s.scalars(select(Document).where(Document.owner==owner)):
   current=list(s.scalars(select(Chunk).where(Chunk.document_id==d.id)));m=s.get(SourceManifest,d.id)
   actual={c.id:hashlib.sha256(c.body.encode()).hexdigest() for c in current}
   expected={x['id']:x['hash'] for x in m.chunks} if m and not d.deleted else {}
   if actual!=expected:findings.append({'document':d.id,'reason':'inventario_o_contenido_inconsistente'})
  return {'status':'FAIL' if findings else 'PASS','findings':findings,'scope':'Compara inventario de fuente e índice; no acredita la veracidad de respuestas.'}

@app.get('/audit/export')
def audit_export(owner=Depends(identity)):
 with Session(ENGINE) as s:
  source=[];index=[]
  for d in s.scalars(select(Document).where(Document.owner==owner)):
   m=s.get(SourceManifest,d.id)
   if not d.deleted and m:
    source += [{'source_id':'curso','document_id':x['id'],'source_version':str(m.version),'content_hash':x['hash'],'collection':owner,'is_deleted':False} for x in m.chunks]
   for c in s.scalars(select(Chunk).where(Chunk.document_id==d.id)):
    index.append({'source_id':'curso','document_id':c.id,'source_version':str(c.version),'content_hash':hashlib.sha256(c.body.encode()).hexdigest(),'collection':owner,'is_deleted':False})
  return {'source':source,'index':index}

@app.get('/documents/{identifier}/structure')
def structure(identifier:str,owner=Depends(identity)):
 with Session(ENGINE) as s:
  d=owned(s,identifier,owner);data=s.get(Structure,identifier)
  if d.status!='disponible' or not data or data.version!=d.version:raise HTTPException(404,'La estructura no está disponible para esta versión.')
  parsed=data.data
  return {'id':d.id,'name':d.name,'version':d.version,'datasets':{name:{'columns':t['columns'],'rows':len(t['rows'])} for name,t in parsed['tables'].items()},'warnings':parsed['warnings'],'sheets':parsed.get('sheets',[])}
class Calculation(BaseModel):
 document_id:str|None=None
 connection_id:str|None=None
 dataset:str
 operation:str
 column:str|None=None
 filters:list[dict]=Field(default_factory=list,max_length=10)
 limit:int=Field(default=100,ge=1,le=100)
@app.post('/calculate')
def calculation(body:Calculation,owner=Depends(identity)):
 if bool(body.document_id)==bool(body.connection_id):raise HTTPException(422,'Indica un documento o una conexión, pero no ambos.')
 with Session(ENGINE) as s:
  try:
   if body.document_id:
    d=owned(s,body.document_id,owner);structure=s.get(Structure,d.id)
    if d.status!='disponible' or not structure or structure.version!=d.version:raise HTTPException(404,'La versión del documento no está disponible.')
    table=structure.data['tables'].get(body.dataset)
    if table is None:raise ValueError('La hoja o tabla no existe; consulta /estructura.')
    source={'document':d.name,'version':d.version,'dataset':body.dataset,'mode':'instantanea_indexada'}
   else:
    connection=s.get(Connection,body.connection_id)
    if connection is None or connection.owner!=owner or connection.revoked:raise HTTPException(404,'Conexión no disponible.')
    table,stamp,engine=db_sources.read(connection.alias,body.dataset,owner)
    source={'connection':connection.alias,'dataset':body.dataset,'queried_at':stamp,'mode':'consulta_en_vivo','engine':engine}
   result=calculate(table,body.operation,body.column,body.filters,body.limit);result['source']=source
   result['answer']=render_answer(result)
   return result
  except ValueError as exc:raise HTTPException(422,str(exc)) from None
class Registration(BaseModel):
 alias:str
 model_config={'extra':'forbid'}
@app.post('/connections')
def register_connection(body:Registration,owner=Depends(identity)):
 try:policy,_=db_sources.config(body.alias,owner)
 except ValueError as exc:raise HTTPException(422,str(exc)) from None
 with Session(ENGINE) as s:
  existing=s.scalar(select(Connection).where(Connection.owner==owner,Connection.alias==body.alias,Connection.revoked==False))
  if existing:return {'id':existing.id,'alias':existing.alias,'datasets':policy['tables']}
  c=Connection(id=str(uuid.uuid4()),owner=owner,alias=body.alias);s.add(c);s.commit()
  return {'id':c.id,'alias':c.alias,'datasets':policy['tables']}
@app.get('/connections')
def list_connections(owner=Depends(identity)):
 with Session(ENGINE) as s:return [{'id':c.id,'alias':c.alias,'datasets':db_sources.policies().get(c.alias,{}).get('tables',{})} for c in s.scalars(select(Connection).where(Connection.owner==owner,Connection.revoked==False))]
@app.delete('/connections/{identifier}')
def revoke_connection(identifier:str,owner=Depends(identity)):
 with Session(ENGINE) as s:
  c=s.get(Connection,identifier)
  if c is None or c.owner!=owner or c.revoked:raise HTTPException(404,'Conexión no disponible.')
  c.revoked=True;s.commit()
 return {'status':'revocada'}
