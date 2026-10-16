import json,urllib.request,urllib.error,urllib.parse,http.cookiejar,uuid,html,time,concurrent.futures
from pathlib import Path
from html.parser import HTMLParser
root=Path.cwd();base='http://localhost:8071';links=json.loads((root/'runtime/customer-links.json').read_text());checks=[];created=[]
class BootParser(HTMLParser):
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if a.get('id')=='cafe': self.boot=json.loads(a['data-boot'])
def client(url):
 op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 for i in range(15):
  try:
   page=op.open(url,timeout=15).read().decode();break
  except Exception:
   if i==14:raise
   time.sleep(1)
 p=BootParser();p.feed(page);return op,p.boot

def post(op,boot,action,payload,csrf=True):
 data={'payload':json.dumps({'service':boot['service'],'token':boot['token'],**payload})}
 if csrf:data['csrf_token']=boot['csrf']
 req=urllib.request.Request(base+f'/cafe/1/{action}',data=urllib.parse.urlencode(data).encode())
 try:
  with op.open(req,timeout=90) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:
  raw=e.read().decode()
  try:body=json.loads(raw)
  except:body={'error':'non-json response'}
  return e.code,body
op,b=client(links['car'])
with op.open(base+'/cafe/1/catalog') as r:catalog=json.load(r)
assert len(catalog['products'])==62
checks.append('62 dataset products served')
p=catalog['products'][0];cart=[{'id':p['id'],'qty':2,'note':'TEST API بدون إضافات','price_unit':0}]
status,q=post(op,b,'quote',{'cart':cart});assert status==200,(status,q)
assert q['result']['total']==round(p['price']*2,3);checks.append('server ignores forged price and quotes authoritative total')
for label,body in [('invalid product',{'cart':[{'id':99999999,'qty':1}]}),('negative quantity',{'cart':[{'id':p['id'],'qty':-1}]}),('unconfirmed options',{'cart':[{'id':p['id'],'qty':1,'options':[12]}]}),('invalid table capability',{'service':'table','token':'x'*43,'cart':cart})]:
 s,r=post(op,b,'quote',body);assert s==400,(label,s,r);checks.append(label+' rejected')
s,r=post(op,b,'quote',{'cart':cart},csrf=False);assert s==400;checks.append('missing CSRF rejected')
body={'request_id':str(uuid.uuid4()),'cart':cart,'car':{'number':'TEST-100','type':'اختبار','color':''},'note':'TEST API — cancel after verification','expected_total':0}
s,r=post(op,b,'submit',body);assert s==400,(s,r);checks.append('tampered expected total rejected')
body['expected_total']=q['result']['total'];s,r=post(op,b,'submit',body);assert s==200,(s,r);first=r['result'];created.append(first['reference']);checks.append('car order persisted and confirmation returned')
s,r=post(op,b,'submit',body);assert s==200 and r['result']['reference']==first['reference'];checks.append('repeated submission returns same order')
changed={**body,'note':'changed'};s,r=post(op,b,'submit',changed);assert s==400;checks.append('idempotency key reuse with changed payload rejected')
concurrent_body={**body,'request_id':str(uuid.uuid4()),'car':{'number':'TEST-CONCURRENT'}}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    responses=list(pool.map(lambda _:post(op,b,'submit',concurrent_body),range(2)))
s,r=post(op,b,'submit',concurrent_body);assert s==200,(s,r)
concurrent_ref=r['result']['reference'];created.append(concurrent_ref)
assert all(s==409 or (s==200 and r['result']['reference']==concurrent_ref) for s,r in responses),responses
checks.append('simultaneous duplicate requests yield one order, retry resolves same reference')
req=urllib.request.Request(base+'/web/dataset/call_kw/pos.order/search_read',data=json.dumps({'jsonrpc':'2.0','method':'call','params':{'model':'pos.order','method':'search_read','args':[[]],'kwargs':{}},'id':1}).encode(),headers={'Content-Type':'application/json'})
try:
    denied=json.load(op.open(req,timeout=30));assert denied.get('error'), 'Public order listing exposed'
except urllib.error.HTTPError as e:assert e.code in [401,403]
checks.append('anonymous customer cannot list native orders')
other,ob=client(links['car']);otherbody={**body,'request_id':body['request_id']};s,r=post(other,ob,'submit',otherbody);assert s==200 and r['result']['reference']!=first['reference'];created.append(r['result']['reference']);checks.append('another browser cannot retrieve previous customer order using same UUID')
top,tb=client(links['tables'][1]['url']);assert tb['table']==links['tables'][1]['number'];s,tq=post(top,tb,'quote',{'cart':cart});assert s==200
payload={'request_id':str(uuid.uuid4()),'cart':cart,'note':'TEST API table','expected_total':tq['result']['total'],'table_id':999999,'car':{}}
s,r=post(top,tb,'submit',payload);assert s==200 and r['result']['table']==tb['table'];created.append(r['result']['reference']);checks.append('table derived from QR capability, forged table_id ignored')
# Administrative read verifies native pos.order data, then cancels only these synthetic drafts.
pw=next(l.split(': ',1)[1] for l in (root/'runtime/LOCAL-LOGIN.txt').read_text().splitlines() if l.startswith('Password: '))
admin=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def rpc(path,params):
 req=urllib.request.Request(base+path,data=json.dumps({'jsonrpc':'2.0','method':'call','params':params,'id':1}).encode(),headers={'Content-Type':'application/json'})
 d=json.load(admin.open(req,timeout=60));assert not d.get('error'),d.get('error',{}).get('message');return d['result']
rpc('/web/session/authenticate',{'db':'pos_demo20','login':'demo.owner@example.test','password':pw})
orders=rpc('/web/dataset/call_kw/pos.order/search_read',{'model':'pos.order','method':'search_read','args':[[['pos_reference','in',created]]],'kwargs':{'fields':['id','pos_reference','state','amount_total','saif_service','saif_car_number','table_id','general_customer_note','source']}})
assert len(orders)==4 and all(o['state']=='draft' and o['source']=='mobile' for o in orders)
checks.append('four test orders confirmed in native pos.order as unpaid mobile orders')
rpc('/web/dataset/call_kw/pos.order/action_pos_order_cancel',{'model':'pos.order','method':'action_pos_order_cancel','args':[[o['id'] for o in orders]],'kwargs':{}})
checks.append('synthetic test orders cancelled, retained for audit')
with op.open(base+p['image']) as r:assert r.headers['Content-Type'].startswith('image/') and len(r.read())>1000
checks.append('product image served from Odoo')
report={'checks':checks,'test_order_references':created,'test_orders_cancelled':True,'physical_devices_tested':False,'physical_printing_tested':False}
(root/'analysis/CUSTOMER-API-TESTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
