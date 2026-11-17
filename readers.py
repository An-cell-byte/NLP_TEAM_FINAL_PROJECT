"""Lectores limitados que conservan estructura, tipos y localización de la fuente."""
from pathlib import Path
from io import BytesIO,StringIO
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import csv,json,os,re,zipfile
MAX_BYTES=int(os.getenv('MAX_FILE_BYTES','5000000'));MAX_ROWS=int(os.getenv('MAX_TABLE_ROWS','5000'));MAX_PARTS=int(os.getenv('MAX_FRAGMENTS','1000'));MAX_PAGES=int(os.getenv('MAX_PDF_PAGES','100'));MAX_SHEETS=int(os.getenv('MAX_EXCEL_SHEETS','20'));MAX_DEPTH=int(os.getenv('MAX_JSON_DEPTH','20'))
REGISTRY={}
def reader(suffix):
 def register(fn):REGISTRY[suffix]=fn;return fn
 return register

def typed(v,decimal='.'):
 if v is None or v=='':return None,'null'
 if isinstance(v,bool):return v,'boolean'
 if isinstance(v,(datetime,date)):return v.isoformat(),'date'
 if isinstance(v,(int,float,Decimal)):
  if not Decimal(str(v)).is_finite():raise ValueError('No se admiten números infinitos o NaN.')
  return str(v),'decimal'
 s=str(v).strip()
 if re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T.*)?',s):
  try:return datetime.fromisoformat(s).isoformat() if 'T' in s else date.fromisoformat(s).isoformat(),'date'
  except ValueError:pass
 if re.fullmatch(r'-?\d+(?:[.,]\d+)?',s):
  # Preserve identifiers with leading zeroes instead of treating them as quantities.
  if re.match(r'^0\d',s):return s,'text'
  try:return str(Decimal(s.replace(decimal,'.'))),'decimal'
  except InvalidOperation:pass
 return str(v),'text'

def headers(values):
 h=[str(v).strip() if v is not None else '' for v in values]
 if not h or not any(h) or any(not x for x in h) or len(set(h))!=len(h):raise ValueError('Los encabezados deben ser únicos y no estar vacíos.')
 if len(h)>200:raise ValueError('Máximo 200 columnas.')
 return h

def table(name,heading,source_rows,locations,decimal='.'):
 h=headers(heading);rows=[];parts=[]
 for i,(values,loc) in enumerate(zip(source_rows,locations)):
  if i>=MAX_ROWS:raise ValueError('Se excedió el límite de filas.')
  if len(values)!=len(h):raise ValueError('Una fila no coincide con el número de columnas.')
  if any(len(str(x))>10000 for x in values if x is not None):raise ValueError('Una celda supera el límite de 10000 caracteres.')
  parsed=[typed(x,decimal) for x in values];vals={k:v[0] for k,v in zip(h,parsed)};types={k:v[1] for k,v in zip(h,parsed)}
  row={'values':vals,'types':types,'location':loc};rows.append(row)
  parts.append({'text':name+'. '+ '; '.join(k+': '+('sin dato' if v is None else str(v)) for k,v in vals.items()),'location':loc})
 if not rows:raise ValueError('La tabla no contiene filas de datos.')
 return {'columns':h,'rows':rows},parts

def load(name,data,options=None):
 if not data:raise ValueError('El archivo está vacío.')
 if options is not None and not isinstance(options,dict):raise ValueError('Las opciones de lectura deben ser un objeto.')
 if len(data)>MAX_BYTES:raise ValueError('El archivo supera el límite configurado.')
 suffix=Path(name).suffix.lower()
 if suffix not in REGISTRY:raise ValueError('Formatos admitidos: TXT, PDF, XLSX, CSV y JSON. XLS/XLSM no están habilitados; exporta una copia XLSX sin macros.')
 result=REGISTRY[suffix](data,options or {})
 if any(len(part['text'])>20000 for part in result['parts']):raise ValueError('Un fragmento supera 20000 caracteres; divide el contenido.')
 if not result['parts']:raise ValueError('No se encontró contenido utilizable.')
 if len(result['parts'])>MAX_PARTS:raise ValueError('Se excedió el límite de fragmentos; reduce el archivo o selecciona una hoja.')
 return result

def decode(data):
 try:s=data.decode('utf-8-sig')
 except UnicodeError:raise ValueError('Guarda el texto con codificación UTF-8.') from None
 if any(ord(c)<32 and c not in '\n\r\t' for c in s) or s.startswith('%PDF-'):raise ValueError('El contenido no es texto plano.')
 return s

@reader('.txt')
def txt(data,options):
 lines=decode(data).splitlines();parts=[]
 for start in range(0,len(lines),15):
  block='\n'.join(lines[start:start+15]).strip()
  words=block.split()
  for offset in range(0,len(words),120):
   parts.append({'text':' '.join(words[offset:offset+120]),'location':{'kind':'txt','line_start':start+1,'line_end':min(start+15,len(lines)),'word_start':offset}})
 return {'parts':parts,'tables':{},'warnings':[]}

@reader('.pdf')
def pdf(data,options):
 import fitz
 if not data.startswith(b'%PDF-'):raise ValueError('El contenido no corresponde a un PDF.')
 try:
  with fitz.open(stream=data,filetype='pdf') as doc:
   if doc.is_encrypted:raise ValueError('El PDF está cifrado.')
   if len(doc)>MAX_PAGES:raise ValueError('Se excedió el límite de páginas.')
   parts=[]
   for i,page in enumerate(doc,1):
    words=page.get_text().split()
    for start in range(0,len(words),100):parts.append({'text':' '.join(words[start:start+120]),'location':{'kind':'pdf','page':i,'word_start':start}})
 except ValueError:raise
 except Exception:raise ValueError('El PDF no es válido.') from None
 if not parts:raise ValueError('El PDF no contiene texto extraíble. Requiere OCR previo.')
 return {'parts':parts,'tables':{},'warnings':[]}

@reader('.csv')
def csv_reader(data,options):
 if options.get('decimal','.') not in ['.',',']:raise ValueError('El separador decimal debe ser punto o coma.')
 s=decode(data);delimiter=options.get('delimiter')
 if delimiter is None:
  try:delimiter=csv.Sniffer().sniff(s[:8192],delimiters=',;\t|').delimiter
  except csv.Error:delimiter=','
 if delimiter not in [',',';','\t','|']:raise ValueError('Separador CSV no admitido.')
 stream=csv.reader(StringIO(s),delimiter=delimiter,strict=True)
 try:h=next(stream)
 except StopIteration:raise ValueError('El CSV está vacío.') from None
 rows=[];loc=[]
 try:
  for i,row in enumerate(stream,2):
   if i>MAX_ROWS+1:raise ValueError('Se excedió el límite de filas.')
   rows.append(row);loc.append({'kind':'csv','row':i,'line_end':stream.line_num,'columns':h})
 except csv.Error:raise ValueError('El CSV tiene una estructura inválida.') from None
 t,parts=table('datos',h,rows,loc,options.get('decimal','.'))
 return {'parts':parts,'tables':{'datos':t},'warnings':[],'options':{'delimiter':delimiter,'decimal':options.get('decimal','.')}}

@reader('.xlsx')
def excel(data,options):
 from openpyxl import load_workbook
 from openpyxl.utils import get_column_letter
 try:
  with zipfile.ZipFile(BytesIO(data)) as z:
   if sum(f.file_size for f in z.infolist())>40_000_000:raise ValueError('El libro expandido es demasiado grande.')
   if any('vbaproject' in f.lower() for f in z.namelist()):raise ValueError('No se aceptan macros. Exporta una copia XLSX sin macros.')
   merged=any(b'<mergeCell ' in z.read(f) for f in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',f))
  wb=load_workbook(BytesIO(data),read_only=True,data_only=False,keep_links=False);cached=load_workbook(BytesIO(data),read_only=True,data_only=True,keep_links=False)
 except ValueError:raise
 except Exception:raise ValueError('El contenido no corresponde a un libro XLSX válido.') from None
 try:
  if len(wb.sheetnames)>MAX_SHEETS:raise ValueError('Se excedió el límite de hojas.')
  selected=options.get('sheet');names=[selected] if selected else wb.sheetnames
  if any(n not in wb.sheetnames for n in names):raise ValueError('La hoja seleccionada no existe.')
  parts=[];tables={};warnings=['Hay celdas combinadas; revisa la interpretación de encabezados y filas.'] if merged else []
  for name in names:
   ws=wb[name]
   if (ws.max_row or 0)>MAX_ROWS+1 or (ws.max_column or 0)>200:raise ValueError('La hoja supera el límite de filas o columnas.')
   data_rows=list(ws.iter_rows());cache_rows=list(cached[name].iter_rows(values_only=True))
   if not data_rows or all(c.value is None for c in data_rows[0]):warnings.append('Hoja vacía: '+name);continue
   h=[c.value for c in data_rows[0]];values=[];locations=[]
   for number,row in enumerate(data_rows[1:],2):
    vals=[];formula_meta={}
    for j,c in enumerate(row):
     value=c.value
     if c.data_type=='f':
      value=cache_rows[number-1][j];formula_meta[c.coordinate]={'formula':c.value,'cached':value is not None};warnings.append('Fórmula '+name+'!'+c.coordinate+(': se utiliza el valor calculado disponible.' if value is not None else ': sin resultado calculado; se conserva como ausente.'))
     vals.append(value)
    if all(v is None for v in vals) and not formula_meta:continue
    values.append(vals);locations.append({'kind':'excel','sheet':name,'row':number,'range':f'A{number}:{get_column_letter(len(h))}{number}','formulas':formula_meta})
   if values:
    t,ps=table(name,h,values,locations);tables[name]=t;parts+=ps
  if sum(len(t['rows']) for t in tables.values())>MAX_ROWS:raise ValueError('El libro supera el límite total de filas.')
  return {'parts':parts,'tables':tables,'warnings':warnings,'sheets':wb.sheetnames}
 finally:wb.close();cached.close()

@reader('.json')
def json_reader(data,options):
 def unique(pairs):
  d={}
  for k,v in pairs:
   if k in d:raise ValueError('El JSON contiene claves duplicadas.')
   d[k]=v
  return d
 try:root=json.loads(decode(data),object_pairs_hook=unique,parse_float=Decimal,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Número JSON no válido.')))
 except (json.JSONDecodeError,RecursionError):raise ValueError('El JSON es inválido o demasiado profundo.') from None
 parts=[];tables={};nodes=0
 def visit(value,path='$',depth=0):
  nonlocal nodes
  nodes+=1
  if depth>MAX_DEPTH or nodes>MAX_ROWS*20:raise ValueError('El JSON supera el límite de profundidad o elementos.')
  if isinstance(value,list):
   if len(value)>MAX_ROWS:raise ValueError('El JSON supera el límite de filas.')
   if value and all(isinstance(r,dict) and all(not isinstance(x,(dict,list)) for x in r.values()) for r in value):
    h=list(dict.fromkeys(k for row in value for k in row));loc=[{'kind':'json','path':path+f'[{i}]'} for i in range(len(value))]
    t,_=table(path,h,[[r.get(k) for k in h] for r in value],loc);tables[path]=t
   for i,v in enumerate(value):visit(v,path+f'[{i}]',depth+1)
  elif isinstance(value,dict):
   for k,v in value.items():visit(v,path+'['+json.dumps(k,ensure_ascii=False)+']',depth+1)
  else:parts.append({'text':path+': '+json.dumps(value,ensure_ascii=False,default=str),'location':{'kind':'json','path':path,'type':typed(value)[1]}})
 visit(root)
 return {'parts':parts,'tables':tables,'warnings':[]}
