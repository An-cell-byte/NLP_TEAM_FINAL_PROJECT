from pathlib import Path
import secrets
sources=Path('.env.sources')
if not sources.exists():sources.write_text('# Fuentes de lectura opcionales. Consulta docs/BASES_DE_DATOS.md.\n');sources.chmod(0o600)
p=Path('.env')
if p.exists():
 print('.env ya existe. Conservamos tu configuración. Para MySQL ejecuta configurar_mysql.py.')
 raise SystemExit(0)
text=Path('.env.example').read_text();password=secrets.token_hex(24)
text=text.replace('DB_PASSWORD=','DB_PASSWORD='+password).replace('BRIDGE_SECRET=','BRIDGE_SECRET='+secrets.token_hex(32)).replace('WEBUI_SECRET_KEY=','WEBUI_SECRET_KEY='+secrets.token_hex(32)).replace('CAMBIAR',password)
p.write_text(text);p.chmod(0o600)
print('Configuración creada en .env. Las claves no se muestran. Para MAMP continúa con configurar_mysql.py.')
