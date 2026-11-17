"""Mantiene un servicio del demo y atiende su solicitud local de cierre."""
from pathlib import Path
import os,sys,threading,_thread
D=Path(__file__).resolve().parent
RUN=D/'.runtime/windows'

def watch_stop(path,finished):
 while not finished.wait(.25):
  if path.exists():
   _thread.interrupt_main()
   return

def serve(role):
 if role=='api':
  import iniciar_api
  iniciar_api.uvicorn.run('app:app',host='127.0.0.1',port=int(os.getenv('API_PORT','18129')))
 elif role=='webui':
  from iniciar_webui import configure_chat,environment,relocate_uploads
  env=environment()
  relocate_uploads(env)
  configure_chat(env)
  os.environ.update(env)
  os.environ['UVICORN_WORKERS']='1'
  from open_webui import serve as open_webui_serve
  open_webui_serve(host='127.0.0.1',port=int(os.getenv('UI_PORT','3187')))
 else:raise ValueError('Servicio no reconocido.')

def main():
 if len(sys.argv)!=3:raise ValueError('Indica el servicio y su archivo de control.')
 role=sys.argv[1];path=Path(sys.argv[2]).resolve()
 if path.parent!=RUN.resolve() or not path.name.startswith('parar_'):raise ValueError('El archivo de control no pertenece al demo.')
 os.chdir(D);finished=threading.Event();threading.Thread(target=watch_stop,args=(path,finished),daemon=True).start()
 try:serve(role)
 except KeyboardInterrupt:pass
 finally:finished.set();path.unlink(missing_ok=True)
if __name__=='__main__':main()
