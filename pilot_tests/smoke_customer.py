"""Exercise real quote, table/car submits and retry in a disposable local pilot.
Creates two unpaid draft orders. No payments, messages, deletion or cancellation.
"""
import argparse,http.cookiejar,json,urllib.request,urllib.parse,uuid
from html.parser import HTMLParser
class Boot(HTMLParser):
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if values.get('id')=='cafe':self.data=json.loads(values['data-boot'])
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://localhost:8072');parser.add_argument('--config',type=int,required=True);parser.add_argument('--allow-disposable-orders',action='store_true');args=parser.parse_args()
    url=urllib.parse.urlsplit(args.base)
    if url.scheme!='http' or url.hostname not in ['localhost','127.0.0.1'] or url.port in [8070,8071,8069] or url.username or url.password:raise SystemExit('Only isolated localhost pilot ports; Saif/Windows demo ports are blocked.')
    if not args.allow_disposable_orders:raise SystemExit('Read script and pass --allow-disposable-orders on your own disposable pilot.')
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def get(path):return client.open(args.base+path,timeout=30)
    def boot(path):
        p=Boot();p.feed(get(path).read().decode());return p.data
    def post(b,action,values):
        data=urllib.parse.urlencode({'csrf_token':b['csrf'],'payload':json.dumps({'service':b['service'],'token':b['token'],**values})}).encode()
        req=urllib.request.Request(args.base+f'/cafe/{args.config}/{action}',data=data)
        r=json.load(client.open(req,timeout=30))
        assert r['ok'],r
        return r['result']
    start=f'/cafe/{args.config}';b=boot(start+'?service=car')
    assert b['demo'] is True,'Pilot only: demo flag required'
    catalog=json.load(get(start+'/catalog'));assert catalog['open'] is True
    product=next(p for p in catalog['products'] if p['available'])
    cart=[{'id':product['id'],'qty':1,'note':'TEST ONLY — no sugar'}]
    q=post(b,'quote',{'cart':cart});assert abs(q['total']-product['price'])<0.0005
    values={'request_id':str(uuid.uuid4()),'cart':cart,'car':{'number':'TEAM-TEST'},'note':'Disposable pilot smoke test','expected_total':q['total']}
    first=post(b,'submit',values);retry=post(b,'submit',values);assert first['reference']==retry['reference'];assert first['service']=='car' and first['paid'] is False
    tables=json.load(get(start+'/tables'))['tables'];assert tables
    bt=boot(tables[0]['url']);assert bt['service']=='table' and bt['table']==tables[0]['number']
    qt=post(bt,'quote',{'cart':cart});second=post(bt,'submit',{**values,'request_id':str(uuid.uuid4()),'car':{},'expected_total':qt['total']})
    assert second['service']=='table' and second['table']==bt['table'] and second['paid'] is False
    print(json.dumps({'result':'passed','config':args.config,'car_order':first['reference'],'table_order':second['reference'],'quote':q['total'],'idempotent_retry':True,'note':'Two unpaid draft test orders retained; POS visibility/printing not proven.'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
