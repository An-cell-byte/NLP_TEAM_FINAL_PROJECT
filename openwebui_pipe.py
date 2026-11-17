"""
title: Qwerty
version: 1.4.0
license: MIT
"""
import asyncio,time,json,hmac,hashlib,uuid,shlex
from pathlib import Path
from urllib.parse import quote
from weakref import WeakValueDictionary
import httpx
from fastapi import HTTPException
from pydantic import BaseModel,Field
class Pipe:
 class Valves(BaseModel):
  API_URL:str=Field(default="http://127.0.0.1:18129")
  BRIDGE_SECRET:str=Field(default="")
  MODE:str=Field(default="extractivo")
  SEARCH:str=Field(default="lexica")
 def __init__(self):
  self.valves=self.Valves()
  self.file_handler=True
  self.attachment_locks=WeakValueDictionary()

 async def purge(self,question,owner,user,request,call):
  args=question.split()
  if len(args)!=2 and (len(args)!=4 or args[2]!='confirmar'):
   return 'Usa /purgar ID. Qwerty te dará el comando para confirmar.'
  try:identifier=str(uuid.UUID(args[1]))
  except ValueError:return 'Usa el ID del documento que aparece en /documentos.'
  path=f'/documents/{identifier}/purge'
  plan=await call('GET',path)
  from open_webui.models.files import Files
  from open_webui.models.knowledge import Knowledges

  files=[]
  for file_id in plan['file_ids']:
   file=await Files.get_file_by_id(file_id)
   if file is None:continue
   if file.user_id!=owner:return 'Un adjunto pertenece a otra cuenta. Se canceló la purga.'
   if await Knowledges.get_knowledges_by_file_id(file_id):
    return 'Un adjunto también está en una base de conocimiento de Open WebUI. Se canceló la purga.'
   files.append(file)

  if len(args)==2:
   return (f"Vas a borrar de forma irreversible «{plan['name']}», sus adjuntos y las respuestas de MySQL que lo citan. "
           f"Para confirmar en los próximos 10 minutos, escribe:\n\n`/purgar {identifier} confirmar {plan['confirmation']}`")
  if request is None:return 'Abre Qwerty en Open WebUI para completar la purga.'
  from open_webui.models.users import UserModel
  from open_webui.routers.files import delete_file_by_id
  from open_webui.storage.provider import Storage

  headers={'Content-Type':'application/json'}
  confirmation={'confirmation':args[3]}
  actor=UserModel.model_validate(user)
  confirmed=await call('POST',path,json.dumps(confirmation).encode(),headers)
  if set(confirmed['file_ids'])!=set(plan['file_ids']):
   return 'Los adjuntos cambiaron. Vuelve a escribir /purgar ID para revisar la operación.'
  try:
   for file in files:
    # Retira primero el archivo físico para que un fallo se pueda reintentar por ID.
    if file.path:await asyncio.to_thread(Storage.delete_file,file.path)
    await delete_file_by_id(request,file.id,actor,db=None)
  except (OSError,HTTPException):
   return 'La purga quedó pendiente. Vuelve a escribir /purgar ID para reintentar con una confirmación nueva.'
  confirmation['removed_files']=confirmed['file_ids']
  await call('POST',path,json.dumps(confirmation).encode(),headers)
  return 'Eliminé el documento, sus adjuntos y las respuestas de MySQL que lo citaban. Las conversaciones ya guardadas pueden conservar el texto.'

 async def pipe(self,body:dict,__user__:dict=None,__event_emitter__=None,__files__=None,__request__=None):
  owner=(__user__ or {}).get("id")
  if not owner:return "Inicia sesión para consultar tus documentos."
  messages=body.get("messages",[]);question=next((m["content"] for m in reversed(messages) if m.get("role")=="user"),"")
  if not isinstance(question,str):return "Escribe una pregunta de texto."
  async def call(method,path,data=b"",headers=None):
   attachment=(headers or {}).get('X-Attachment-ID','')
   signed=b'qwerty-attachment\0'+attachment.encode()+b'\0'+data if attachment else data
   stamp=str(int(time.time()));sig=hmac.new(self.valves.BRIDGE_SECRET.encode(),owner.encode()+b"\n"+stamp.encode()+b"\n"+signed,hashlib.sha256).hexdigest()
   async with httpx.AsyncClient(timeout=120) as client:
    r=await client.request(method,self.valves.API_URL+path,content=data,headers={"X-Owner":owner,"X-Time":stamp,"X-Signature":sig,**(headers or {})})
    r.raise_for_status();return r.json()
  try:
   if question.strip()=='/ayuda':return 'Adjunta TXT, PDF, XLSX, CSV o JSON y escribe /cargar. Para Excel: /cargar hoja=Prestamos. Consulta /documentos y /estructura ID. Usa /purgar ID para solicitar el borrado de un archivo. Las consultas de MySQL se escriben directamente en el chat. La guía docs/USO.md incluye los ejemplos completos.'
   if question.startswith('/estructura '):return json.dumps(await call('GET','/documents/'+question.split()[1]+'/structure'),ensure_ascii=False,indent=2)
   if question.startswith('/calcular '):
    payload=json.loads(question.split(maxsplit=1)[1]);result=await call('POST','/calculate',json.dumps(payload,ensure_ascii=False).encode(),{'Content-Type':'application/json'})
    return result['answer'] if 'answer' in result else json.dumps(result,ensure_ascii=False,indent=2)
   if question.startswith('/conectar '):return json.dumps(await call('POST','/connections',json.dumps({'alias':question.split()[1]}).encode(),{'Content-Type':'application/json'}),ensure_ascii=False,indent=2)
   if question.startswith('/conexiones'):return json.dumps(await call('GET','/connections'),ensure_ascii=False,indent=2)
   if question.startswith('/revocar '):return json.dumps(await call('DELETE','/connections/'+question.split()[1]),ensure_ascii=False)
   if question.startswith("/documentos"):return json.dumps(await call("GET","/documents"),ensure_ascii=False,indent=2)
   if question.startswith("/eliminar "):return json.dumps(await call("DELETE","/documents/"+question.split()[1]),ensure_ascii=False)
   if question.startswith("/fuente "):return json.dumps(await call("GET","/sources/"+question.split(maxsplit=1)[1]),ensure_ascii=False)
   if question.startswith("/auditar"):return json.dumps(await call("GET","/audit"),ensure_ascii=False)
   command=next(iter(question.split(maxsplit=1)), '')
   if command in {'/cargar','/sustituir','/purgar'}:
    lock=self.attachment_locks.setdefault(owner,asyncio.Lock())
    async with lock:
     if command=='/purgar':return await self.purge(question,owner,__user__,__request__,call)
     from open_webui.models.files import Files
     from open_webui.storage.provider import Storage
     attachments=__files__ or body.get("files",[])
     if not attachments:return "Adjunta un TXT, PDF, XLSX, CSV o JSON y escribe /cargar."
     args=shlex.split(question)
     if command=="/sustituir" and len(args)<2:return "Adjunta la versión nueva y escribe /sustituir ID."
     results=[]
     for attachment in attachments:
      fid=attachment.get("id") or attachment.get("file",{}).get("id");file=await Files.get_file_by_id(fid)
      if file is None or file.user_id!=owner:return "El archivo no pertenece a tu cuenta."
      local_file=Path(Storage.get_file(file.path))
      if local_file.stat().st_size>5_000_000:return "El archivo supera el límite de 5 MB."
      raw=local_file.read_bytes()
      headers={"X-Filename":quote(file.meta.get("name","documento.txt")),"X-Attachment-ID":file.id}
      options={}
      for argument in args[1:]:
       if argument.startswith('hoja='):options['sheet']=argument.split('=',1)[1]
       elif argument.startswith('decimal='):options['decimal']=argument.split('=',1)[1]
       elif argument.startswith('separador='):options['delimiter']=argument.split('=',1)[1]
      if options:headers['X-Read-Options']=json.dumps(options,ensure_ascii=True)
      if command=="/sustituir":headers["X-Replace"]=args[1]
      if __event_emitter__:
       await __event_emitter__({"type":"status","data":{"description":"Archivo recibido","done":False}})
       await __event_emitter__({"type":"status","data":{"description":"Procesando documento","done":False}})
      results.append(await call("POST","/documents",raw,headers))
     if __event_emitter__:await __event_emitter__({"type":"status","data":{"description":"Documento disponible","done":True}})
     return json.dumps(results,ensure_ascii=False,indent=2)
   history=[m for m in messages[:-1] if m.get("role")=="user"][-6:]
   payload=json.dumps({"question":question,"history":history,"request_id":body.get("metadata",{}).get("message_id") or str(uuid.uuid4()),"mode":self.valves.MODE,"search":self.valves.SEARCH},ensure_ascii=False).encode()
   result=await call("POST","/query",payload,{"Content-Type":"application/json"})
   if __event_emitter__:
    for ref in result["references"]:
     loc=ref.get('location') or {};kind=loc.get('kind')
     meta={'source':ref['document'],'version':ref['version'],'location':loc}
     if kind=='pdf' or (kind=='legacy' and ref['document'].lower().endswith('.pdf')):
      # Open WebUI muestra page + 1; la API conserva páginas humanas desde 1.
      meta['page']=ref['page']-1;place='Página '+str(ref['page'])
     elif kind=='excel':place='Hoja '+loc['sheet']+', fila '+str(loc['row'])+', celdas '+loc['range']
     elif kind=='csv':place='Fila '+str(loc['row'])+'; columnas en los encabezados del fragmento'
     elif kind=='json':place='Ruta '+loc['path']
     elif kind=='txt':place='Líneas '+str(loc['line_start'])+' a '+str(loc['line_end'])
     else:place='Fuente anterior; consultar el identificador vigente'
     await __event_emitter__({'type':'citation','data':{'document':['Ubicación: '+place+'. Versión '+str(ref['version'])+'.\n\n'+ref['text']],'metadata':[meta],'source':{'name':ref['document']}}})
   return result["answer"]
  except (json.JSONDecodeError,ValueError,KeyError):return 'Revisa la estructura del comando; /calcular requiere un objeto JSON válido.'
  except httpx.HTTPStatusError as exc:
   if __event_emitter__:await __event_emitter__({'type':'status','data':{'description':'Error al procesar la solicitud','done':True}})
   try:message=exc.response.json().get('detail','Solicitud no válida.')
   except ValueError:message='Solicitud no válida.'
   if isinstance(message,dict):message=message.get('message','Revisa los datos de la solicitud.')
   return 'No se pudo completar la operación (HTTP '+str(exc.response.status_code)+'): '+str(message)
  except httpx.RequestError:return "El servicio del curso no está disponible. Comprueba que la API esté encendida."
