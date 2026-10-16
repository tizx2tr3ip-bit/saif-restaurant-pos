import hashlib
import json
import math
from datetime import timedelta
import re
import secrets
import uuid
from odoo import api, fields, models, Command
from odoo.exceptions import ValidationError

class Config(models.Model):
    _inherit = 'pos.config'
    saif_menu_enabled = fields.Boolean(default=False)
    saif_menu_demo = fields.Boolean(default=True)
    saif_car_key = fields.Char(default=lambda self: secrets.token_urlsafe(32), copy=False, groups='point_of_sale.group_pos_manager')

    def _saif_products(self):
        self.ensure_one()
        domain = [('saif_menu_config_id', '=', self.id), ('active', '=', True), ('sale_ok', '=', True), ('available_in_pos', '=', True), ('self_order_available', '=', True)]
        return self.env['product.product'].sudo().with_company(self.company_id).search(domain, order='id')

    def _saif_context(self, service, token):
        self.ensure_one()
        if not self.active or not self.saif_menu_enabled:
            raise ValidationError('المنيو غير متاح / Menu unavailable')
        if service == 'car' and isinstance(token, str) and secrets.compare_digest(token, self.saif_car_key or ''):
            return self.env['restaurant.table']
        if service == 'table' and isinstance(token, str) and len(token) >= 32:
            table = self.env['restaurant.table'].sudo().search([('saif_qr_key', '=', token), ('floor_id', 'in', self.floor_ids.ids), ('active', '=', True)], limit=1)
            if table and not table.parent_id:
                return table
        raise ValidationError('رابط الطاولة أو الخدمة غير صالح / Invalid service link')

    def _saif_calculate(self, cart):
        if not isinstance(cart, list) or not cart or len(cart) > 50:
            raise ValidationError('السلة فارغة أو كبيرة جداً / Invalid basket')
        allowed = {p.id:p for p in self._saif_products()}
        result=[]
        for item in cart:
            if not isinstance(item, dict):
                raise ValidationError('Invalid item')
            pid=item.get('id')
            if isinstance(pid,bool) or not isinstance(pid,int): raise ValidationError('Invalid product')
            product=allowed.get(pid)
            qty=item.get('qty')
            if not product or isinstance(qty,bool) or not isinstance(qty,int) or not 1 <= qty <= 20:
                raise ValidationError('صنف غير متاح أو كمية غير صالحة / Invalid product or quantity')
            # This first release supports confirmed simple products only. Do not silently ignore options.
            if item.get('options') or product.product_tmpl_id.attribute_line_ids or product.type == 'combo':
                raise ValidationError('خيارات هذا الصنف تحتاج إعداداً / Product options require setup')
            note=item.get('note','')
            if not isinstance(note,str) or len(note)>300:
                raise ValidationError('الملاحظة طويلة / Note too long')
            price=self.pricelist_id._get_product_price(product,1.0,currency=self.currency_id)
            taxes=product.taxes_id._filter_taxes_by_company(self.company_id)
            if self.default_fiscal_position_id:
                taxes=self.default_fiscal_position_id.map_tax(taxes)
            amounts=taxes.compute_all(price,self.currency_id,qty,product=product)
            result.append({'id':product.id,'name':product.display_name,'qty':qty,'note':note.strip(),'unit':price,'total':amounts['total_included'],'tax':amounts['total_included']-amounts['total_excluded']})
        return {'lines':result,'total':self.currency_id.round(sum(l['total'] for l in result)),'tax':self.currency_id.round(sum(l['tax'] for l in result))}

    def _saif_submit(self, payload, visitor):
        self.ensure_one()
        service=payload.get('service'); table=self._saif_context(service,payload.get('token'))
        try:
            request_id=str(uuid.UUID(payload.get('request_id',''), version=4))
            if request_id != payload.get('request_id'): raise ValueError()
        except (ValueError,TypeError,AttributeError):
            raise ValidationError('Invalid request identifier')
        key=hashlib.sha256((str(self.id)+':'+visitor+':'+request_id).encode()).hexdigest()
        digest=hashlib.sha256(json.dumps({k:payload.get(k) for k in ['service','token','cart','car','note']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        # Serialize on this register; a second concurrent submit retries rather than duplicating.
        self.lock_for_update()
        Order=self.env['pos.order'].sudo().with_company(self.company_id)
        existing=Order.search([('saif_request_key','=',key)],limit=1)
        if existing:
            if existing.saif_payload_hash != digest: raise ValidationError('الطلب تغير؛ راجع السلة / Request changed')
            return existing._saif_confirmation()
        self.invalidate_recordset(['current_session_id'])
        since=fields.Datetime.now()-timedelta(minutes=1)
        visitor_hash=hashlib.sha256(visitor.encode()).hexdigest()
        if Order.search_count([('saif_visitor_hash','=',visitor_hash),('create_date','>=',since)]) >= 5 or Order.search_count([('config_id','=',self.id),('saif_request_key','!=',False),('create_date','>=',since)]) >= 60:
            raise ValidationError('طلبات كثيرة؛ انتظر دقيقة / Too many orders; wait one minute')
        session=self.current_session_id
        if not session or session.state != 'opened':
            raise ValidationError('الكاشير مغلق حالياً؛ حاول لاحقاً / Register is currently closed')
        car=payload.get('car') or {}
        if not isinstance(car,dict): raise ValidationError('Invalid car')
        number=car.get('number','').strip() if isinstance(car.get('number',''),str) else ''
        if service=='car' and (not number or len(number)>24 or not re.fullmatch(r'[\w\s\-]+',number)):
            raise ValidationError('أدخل رقم سيارة صحيحاً / Enter a valid car number')
        extras={k:car.get(k,'') for k in ['color','type']}
        if any(not isinstance(v,str) or len(v)>50 for v in extras.values()): raise ValidationError('Invalid car details')
        note=payload.get('note','')
        if not isinstance(note,str) or len(note)>500: raise ValidationError('Invalid note')
        quote=self._saif_calculate(payload.get('cart'))
        expected=payload.get('expected_total')
        if isinstance(expected,bool) or not isinstance(expected,(float,int)) or not math.isfinite(expected) or abs(expected-quote['total'])>=self.currency_id.rounding/2:
            raise ValidationError('تغير السعر؛ حدّث الإجمالي قبل التأكيد / Price changed; review the total')
        label=f'سيارة / Car {number}' if service=='car' else f'طاولة / Table {table.table_number}'
        lines=[]
        for line in quote['lines']:
            p=self.env['product.product'].sudo().browse(line['id'])
            lines.append(Command.create({'product_id':p.id,'qty':line['qty'],'price_unit':line['unit'],'price_subtotal':0,'price_subtotal_incl':0,'full_product_name':p.display_name,'customer_note':line['note'],'tax_ids':[Command.set(p.taxes_id._filter_taxes_by_company(self.company_id).ids)]}))
        preset=self.available_preset_ids.filtered(lambda p:p.service_at==('table' if table else 'counter'))[:1]
        if not preset: raise ValidationError('نوع الخدمة غير مهيأ / Service is not configured')
        order=Order.create({'session_id':session.id,'user_id':session.user_id.id,'uuid':str(uuid.uuid4()),'state':'draft','source':'mobile','amount_total':0,'amount_tax':0,'amount_paid':0,'amount_return':0,'preset_id':preset.id,'pricelist_id':self.pricelist_id.id,'fiscal_position_id':self.default_fiscal_position_id.id,'floating_order_name':label,'general_customer_note':' | '.join(filter(None,[label,extras['type'],extras['color'],note.strip()])),'table_id':table.id if table else False,'self_ordering_table_id':table.id if table else False,'lines':lines,'saif_request_key':key,'saif_payload_hash':digest,'saif_visitor_hash':visitor_hash,'saif_service':service,'saif_car_number':number if service=='car' else False,'saif_car_color':extras['color'] if service=='car' else False,'saif_car_type':extras['type'] if service=='car' else False})
        order.recompute_prices()
        if abs(order.amount_total-quote['total'])>=self.currency_id.rounding/2:
            raise ValidationError('تغير الإجمالي؛ راجع إعدادات الأسعار / Total needs review')
        order._send_order()
        order._send_notification(order)
        return order._saif_confirmation()

class Product(models.Model):
    _inherit='product.template'
    saif_menu_config_id=fields.Many2one('pos.config',index=True)
    saif_dataset_id=fields.Char(index=True)
    saif_review_note=fields.Char()

class Table(models.Model):
    _inherit='restaurant.table'
    saif_qr_key=fields.Char(copy=False,groups='point_of_sale.group_pos_manager')

    def init(self):
        # Existing tables predate the addon: keep NULL during column creation, then
        # initialize separately. A batch field default would reuse one QR key.
        self.env.cr.execute('SELECT id FROM restaurant_table WHERE saif_qr_key IS NULL')
        for (table_id,) in self.env.cr.fetchall():
            self.env.cr.execute('UPDATE restaurant_table SET saif_qr_key=%s WHERE id=%s', (secrets.token_urlsafe(32), table_id))

    _saif_unique_table_qr=models.Constraint('unique(saif_qr_key)','Table QR key must be unique')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('saif_qr_key',secrets.token_urlsafe(32))
        return super().create(vals_list)

class Order(models.Model):
    _inherit='pos.order'
    saif_request_key=fields.Char(copy=False,index=True,groups='base.group_system')
    saif_visitor_hash=fields.Char(copy=False,index=True,groups='base.group_system')
    saif_payload_hash=fields.Char(copy=False,groups='base.group_system')
    saif_service=fields.Selection([('car','Car'),('table','Table')],copy=False)
    saif_car_number=fields.Char(copy=False)
    saif_car_color=fields.Char(copy=False)
    saif_car_type=fields.Char(copy=False)
    _saif_unique_request=models.Constraint('unique(saif_request_key)','Request already processed')

    def _saif_confirmation(self):
        self.ensure_one()
        return {'reference':self.pos_reference,'number':self.tracking_number,'total':self.amount_total,'paid':self.state in ['paid','done'],'service':self.saif_service,'car':self.saif_car_number or '', 'table':self.table_id.table_number if self.table_id else None}

    @api.model
    def _load_pos_data_fields(self,config):
        fields = super()._load_pos_data_fields(config)
        # In Odoo 20 an empty list means all fields, including order lines.
        # Replacing it with our fields alone breaks the POS relation metadata.
        if not fields:
            return fields
        return list(dict.fromkeys(fields + ['saif_service','saif_car_number','saif_car_color','saif_car_type']))
