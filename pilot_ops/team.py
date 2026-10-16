"""Cross-platform isolated pilot launcher; stdlib only. Never manages Saif's existing stack."""
import argparse,json,os,re,secrets,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCK=json.loads((ROOT/'source.lock.json').read_text())
ENV=ROOT/'pilot_ops/.env'
def run(args,**kw):return subprocess.run(args,check=True,cwd=ROOT,**kw)
def read_env():
 if not ENV.exists():raise SystemExit('Run init first.')
 return dict(line.split('=',1) for line in ENV.read_text().splitlines() if line and not line.startswith('#'))
def compose(*args,**kw):
 e=read_env()
 if not re.fullmatch(r'saif_team_[a-z0-9_]+',e.get('COMPOSE_PROJECT_NAME','')):raise SystemExit('Refusing unscoped project name.')
 if e.get('PILOT_DB_NAME')!='saif_pilot':raise SystemExit('This launcher only manages saif_pilot in its own containers.')
 return run(['docker','compose','--env-file',str(ENV),'-f',str(ROOT/'pilot_ops/compose.yaml'),'-p',e['COMPOSE_PROJECT_NAME'],*args],**kw)
def init(name,port):
 if not re.fullmatch(r'[a-z0-9_]{1,24}',name):raise SystemExit('Name: lowercase letters, digits, underscore.')
 if not 1024<=port<=65535:raise SystemExit('Invalid port.')
 if ENV.exists() or (ROOT/'.runtime/odoo.conf').exists():raise SystemExit('Local configuration exists; not overwriting.')
 e={'COMPOSE_PROJECT_NAME':'saif_team_'+name,'PILOT_HTTP_PORT':str(port),'PILOT_DB_NAME':'saif_pilot','PILOT_DB_PASSWORD':secrets.token_urlsafe(32),'PILOT_ADMIN_PASSWORD':secrets.token_urlsafe(24),'ODOO_RUNTIME_IMAGE':LOCK['runtime_image']}
 d=ROOT/'.runtime';d.mkdir(mode=0o700,exist_ok=True)
 ENV.write_text(''.join(f'{k}={v}\n' for k,v in e.items()));ENV.chmod(0o600)
 cfg=d/'odoo.conf'
 cfg.write_text('[options]\naddons_path = /opt/odoo-source/odoo/addons,/opt/odoo-source/addons,/opt/custom-addons\ndata_dir = /var/lib/odoo\ndb_host = db\ndb_port = 5432\ndb_user = saif_pilot\ndb_password = '+e['PILOT_DB_PASSWORD']+'\ndb_name = saif_pilot\ndbfilter = ^saif_pilot$\nlist_db = False\nadmin_passwd = '+secrets.token_urlsafe(32)+'\nhttp_port = 8069\nhttp_interface = 0.0.0.0\nworkers = 0\nproxy_mode = False\n')
 cfg.chmod(0o600)
 print('Created local secrets; do not commit them. Pilot admin password is in pilot_ops/.env.')
def source():
 p=ROOT/LOCK['source_checkout']
 if p.exists() and any(p.iterdir()):
  if not (p/'.git').exists():raise SystemExit('Source path exists but is not a Git checkout; not touching it.')
  actual=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
  if actual!=LOCK['commit']:raise SystemExit('Source commit differs; refusing to reset developer work.')
  print('Source already pinned.');return
 p.mkdir(parents=True,exist_ok=True)
 run(['git','init',str(p)])
 run(['git','-C',str(p),'remote','add','origin',LOCK['repository']])
 run(['git','-C',str(p),'fetch','--depth=1','origin',LOCK['commit']])
 run(['git','-C',str(p),'checkout','--detach','FETCH_HEAD'])
 print('Official source pinned; local project code remains separate.')
def bootstrap():
 e=read_env();p=ROOT/LOCK['source_checkout']
 if not (p/'odoo/cli').exists():raise SystemExit('Run source first.')
 actual=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
 if actual!=LOCK['commit']:raise SystemExit('Source commit differs; refusing bootstrap.')
 compose('up','-d','db')
 compose('run','--rm','-T','app','--config=/etc/odoo/odoo.conf','-d',e['PILOT_DB_NAME'],'-i','l10n_om,pos_restaurant,pos_self_order,saif_cafe_order,saif_cafe_kitchen,lab_login_branding','--without-demo=True','--stop-after-init','--no-http')
 compose('run','--rm','-T','app','shell','--config=/etc/odoo/odoo.conf','-d',e['PILOT_DB_NAME'],'--no-http',input="exec(open('/opt/seed_demo.py').read())\n",text=True)
 compose('up','-d','--wait','app')
 print(f"Pilot: http://localhost:{e['PILOT_HTTP_PORT']}/cafe/1 (check the seed output for actual config id).")
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['init','source','bootstrap','up','stop','status']);p.add_argument('--name',default='developer');p.add_argument('--port',type=int,default=8072);a=p.parse_args()
 if a.action=='init':init(a.name,a.port)
 elif a.action=='source':source()
 elif a.action=='bootstrap':bootstrap()
 else:compose(*{'up':['up','-d','--wait','db','app'],'stop':['stop'],'status':['ps']}[a.action])
if __name__=='__main__':main()
