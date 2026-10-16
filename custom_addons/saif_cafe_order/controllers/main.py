import json
import secrets
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError, LockError
from werkzeug.exceptions import NotFound

class Cafe(http.Controller):
    def _config(self,config_id):
        c=request.env['pos.config'].sudo().browse(config_id).exists()
        if not c or not c.active or not c.saif_menu_enabled: raise NotFound()
        return c.with_company(c.company_id)

    @http.route('/cafe/<int:config_id>',type='http',auth='public',methods=['GET'],sitemap=False)
    def page(self,config_id,table=None,service=None,**kw):
        c=self._config(config_id)
        if not request.session.get('saif_visitor'):
            request.session['saif_visitor']=secrets.token_urlsafe(32)
        token=table if table else c.saif_car_key
        mode='table' if table else 'car'
        try: t=c._saif_context(mode,token)
        except ValidationError: raise NotFound()
        boot={'config':c.id,'token':token,'service':mode,'table':t.table_number if t else None,'choose':not table and service!='car','csrf':request.csrf_token(),'demo':c.saif_menu_demo,'name':'كرك الموج','name_en':'Karak Al Mouj'}
        response=request.render('saif_cafe_order.page',{'boot':json.dumps(boot,ensure_ascii=False)})
        response.headers['Cache-Control']='no-store'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    @http.route('/cafe/<int:config_id>/tables',type='http',auth='public',methods=['GET'])
    def tables(self,config_id,**kw):
        c=self._config(config_id)
        tables=request.env['restaurant.table'].sudo().search([
            ('floor_id','in',c.floor_ids.ids),('active','=',True),('parent_id','=',False)
        ],order='floor_id,table_number,id')
        response=request.make_json_response({'tables':[
            {'number':t.table_number,'floor':t.floor_id.name,
             'url':f'/cafe/{c.id}?table={t.saif_qr_key}'}
            for t in tables if t.saif_qr_key
        ]})
        response.headers['Cache-Control']='no-store'
        return response

    @http.route('/cafe/<int:config_id>/catalog',type='http',auth='public',methods=['GET'])
    def catalog(self,config_id,**kw):
        c=self._config(config_id); products=[]
        for p in c._saif_products():
            q=c._saif_calculate([{'id':p.id,'qty':1}]) if not p.attribute_line_ids and p.type!='combo' else None
            products.append({'id':p.id,'name':p.name,'description':p.description_sale or '', 'category':p.pos_categ_ids[:1].name or 'المنيو','price':q['total'] if q else None,'image':f'/cafe/{c.id}/image/{p.id}','available':bool(q),'review':bool(p.saif_review_note)})
        return request.make_json_response({'products':products,'open':bool(c.current_session_id and c.current_session_id.state=='opened'),'demo':c.saif_menu_demo,'currency':'OMR'})

    @http.route('/cafe/<int:config_id>/image/<int:product_id>',type='http',auth='public',methods=['GET'])
    def image(self,config_id,product_id):
        import base64
        c=self._config(config_id); p=c._saif_products().filtered(lambda p:p.id==product_id)
        if not p or not p.image_1024: raise NotFound()
        data=p.image_1024.content
        from odoo.tools.mimetypes import guess_mimetype
        return request.make_response(data,[('Content-Type',guess_mimetype(data)),('Cache-Control','public, max-age=300'),('X-Content-Type-Options','nosniff')])

    @http.route('/cafe/<int:config_id>/<string:action>',type='http',auth='public',methods=['POST'],csrf=True)
    def action(self,config_id,action,**kw):
        if action not in ['quote','submit']:raise NotFound()
        try:
            raw=kw.get('payload','{}')
            if len(raw)>24000: raise ValidationError('Request too large')
            payload=json.loads(raw)
            if not isinstance(payload,dict): raise ValidationError('Invalid request')
            c=self._config(config_id)
            # Validate service capability for quotes as well as submissions.
            c._saif_context(payload.get('service'),payload.get('token'))
            with request.env.cr.savepoint():
                if action=='quote': result=c._saif_calculate(payload.get('cart'))
                else:
                    visitor=request.session.get('saif_visitor')
                    if not visitor: raise ValidationError('افتح المنيو مجدداً / Reload the menu')
                    result=c._saif_submit(payload,visitor)
            return request.make_json_response({'ok':True,'result':result})
        except (ValidationError,ValueError,TypeError) as e:
            return request.make_json_response({'ok':False,'error':str(e)},status=400)
        except LockError:
            return request.make_json_response({'ok':False,'error':'النظام مشغول؛ أعد المحاولة بنفس الطلب / Busy; retry the same order'},status=409)
