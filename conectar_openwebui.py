"""Conecta una instalación local ya iniciada, sin guardar la contraseña del administrador."""
from pathlib import Path
from getpass import getpass
import httpx
from dotenv import dotenv_values
from openwebui_pipe import Pipe
config=dotenv_values('.env')
default_ui='http://127.0.0.1:'+(config.get('UI_PORT') or '3187')
url=input('URL de Open WebUI ['+default_ui+']: ').strip() or default_ui
if not url.startswith(('http://127.0.0.1:','http://localhost:')):raise SystemExit('Este instalador está preparado para el servicio local.')
config=dotenv_values('.env')
if not config.get('BRIDGE_SECRET'):raise SystemExit('Primero ejecuta configurar.py.')
with httpx.Client(base_url=url,timeout=60) as c:
 r=c.post('/api/v1/auths/signin',json={'email':input('Correo administrador local: ').strip(),'password':getpass('Contraseña local: ')});r.raise_for_status();token=r.json()['token'];headers={'Authorization':'Bearer '+token}
 fid='pln_documental';form={'id':fid,'name':'Qwerty','content':Path('openwebui_pipe.py').read_text(encoding='utf-8'),'meta':{'description':'Backend documental del curso de PLN.'}}
 listed=c.get('/api/v1/functions/',headers=headers);listed.raise_for_status()
 existing_function=any(item['id']==fid for item in listed.json())
 if existing_function:
  current=c.get('/api/v1/functions/id/'+fid,headers=headers);current.raise_for_status()
  if current.json()['content']!=form['content']:
   if input('La función existente tiene otro contenido. ¿Conservaste una exportación y revisaste la actualización? [si/no]: ').strip().lower()!='si':raise SystemExit('Se conserva la función existente.')
 endpoint='/api/v1/functions/id/'+fid+'/update' if existing_function else '/api/v1/functions/create'
 r=c.post(endpoint,headers=headers,json=form);r.raise_for_status()
 if not r.json()['is_active']:c.post('/api/v1/functions/id/'+fid+'/toggle',headers=headers,json={}).raise_for_status()
 previous_valves=c.get('/api/v1/functions/id/'+fid+'/valves',headers=headers)
 valves=previous_valves.json() if previous_valves.status_code==200 else {}
 default_api=valves.get('API_URL') or 'http://127.0.0.1:'+(config.get('API_PORT') or '18129')
 api=input('URL del backend local ['+default_api+']: ').strip() or default_api
 c.post('/api/v1/functions/id/'+fid+'/valves/update',headers=headers,json={**{'MODE':'extractivo','SEARCH':Pipe.Valves().SEARCH},**valves,'API_URL':api,'BRIDGE_SECRET':config['BRIDGE_SECRET']}).raise_for_status()
 existing_model=c.get('/api/v1/models/model',headers=headers,params={'id':fid})
 if existing_model.status_code!=404:existing_model.raise_for_status()
 previous=existing_model.json() if existing_model.status_code==200 else None
 ids=[] if previous else [x.strip() for x in input('IDs de usuarios autorizados, separados por coma (vacío: solo administrador): ').split(',') if x.strip()]
 model={'id':fid,'base_model_id':None,'name':'Qwerty','meta':{'description':'Documentos y cálculos con fuentes verificables.','profile_image_url':'/static/favicon.png','capabilities':{'file_context':False}},'params':{},'is_active':True,'access_grants':[{'principal_type':'user','principal_id':i,'permission':'read'} for i in ids]}
 if previous:
  model['access_grants']=previous.get('access_grants',[]);model['params']=previous.get('params',{});model['meta']={**previous.get('meta',{}),**model['meta']}
 endpoint='/api/v1/models/model/update' if previous else '/api/v1/models/create'
 c.post(endpoint,headers=headers,json=model).raise_for_status()
 defaults=c.get('/api/v1/configs/models',headers=headers);defaults.raise_for_status()
 values=defaults.json();values['DEFAULT_MODELS']=fid
 c.post('/api/v1/configs/models',headers=headers,json=values).raise_for_status()
 print('Qwerty conectado y seleccionado como modelo inicial. Abre un chat nuevo y confirma ese nombre en el selector superior. qwen3:1.7b por sí solo no consulta los datos del proyecto. Las claves permanecen en la configuración privada del administrador.')
