"""Persistencia del curso: MySQL de MAMP o PostgreSQL, con el mismo contrato de la API."""
from contextlib import contextmanager
import os,hashlib
import numpy as np
from sqlalchemy import create_engine,text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

class QueryBusy(Exception):
 """La misma solicitud sigue en curso en otro proceso."""

def database_url():
 backend=os.getenv('STORAGE_BACKEND','auto').lower()
 if backend=='mysql':
  required=['MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD']
  if any(not os.getenv(k) for k in required):raise RuntimeError('Falta configurar MySQL. Ejecuta configurar_mysql.py; las claves se guardan en .env.mysql.')
  try:port=int(os.getenv('MYSQL_PORT','8889'))
  except ValueError:raise RuntimeError('MYSQL_PORT debe ser un número.') from None
  return URL.create('mysql+pymysql',username=os.environ['MYSQL_USER'],password=os.environ['MYSQL_PASSWORD'],host=os.getenv('MYSQL_HOST','127.0.0.1'),port=port,database=os.environ['MYSQL_DATABASE'],query={'charset':'utf8mb4'})
 url=os.getenv('DATABASE_URL','')
 if not url:raise RuntimeError('Falta DATABASE_URL o STORAGE_BACKEND=mysql. Revisa el README y la configuración privada.')
 return url

def make_engine():
 url=database_url();return create_engine(url,pool_pre_ping=True,pool_recycle=1800,hide_parameters=True)

@contextmanager
def query_session(engine,key):
 if engine.dialect.name=='postgresql':
  with Session(engine) as session:
   session.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':key})
   yield session
 else:
  # GET_LOCK pertenece a la conexión, no a una transacción; se libera también si hay error.
  name='documental:'+hashlib.sha256(key.encode()).hexdigest()[:48]
  with engine.connect() as connection:
   acquired=connection.execute(text('SELECT GET_LOCK(:name, 10)'),{'name':name}).scalar()
   connection.commit()
   if acquired!=1:raise QueryBusy('La solicitud sigue en curso; vuelve a enviarla con el mismo identificador.')
   try:
    with Session(bind=connection) as session:yield session
   finally:
    if connection.in_transaction():connection.rollback()
    connection.execute(text('SELECT RELEASE_LOCK(:name)'),{'name':name});connection.commit()

def mysql_candidates(chunks,vector,limit=50):
 # Los vectores se guardan como JSON en MySQL 8. El cálculo del coseno se hace en Python.
 q=np.asarray(vector,dtype=float);qn=np.linalg.norm(q)
 def score(c):
  if c.embedding is None:return float('-inf')
  v=np.asarray(c.embedding,dtype=float);vn=np.linalg.norm(v)
  return float(np.dot(v,q)/(vn*qn)) if vn and qn else -1.0
 return sorted(chunks,key=score,reverse=True)[:limit]
