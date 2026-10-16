from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
from werkzeug.exceptions import Forbidden, NotFound


class Kitchen(http.Controller):
    def _config(self, config_id):
        if not request.env.user.has_group('point_of_sale.group_pos_user'):
            raise Forbidden()
        config = request.env['pos.config'].browse(config_id).exists()
        if not config:
            raise NotFound()
        config.check_access('read')
        if config.company_id not in request.env.companies:
            raise Forbidden()
        return config

    @http.route('/cafe/kitchen/<int:config_id>', type='http', auth='user', methods=['GET'])
    def board(self, config_id, **kw):
        config = self._config(config_id)
        domain = [('config_id', '=', config.id), ('state', '!=', 'cancel'),
                  ('prep_order_ids', '!=', False), ('saif_kitchen_state', '!=', 'served')]
        orders = request.env['pos.order'].search(domain, order='date_order asc, id asc', limit=101)
        response = request.render('saif_cafe_kitchen.board', {
            'config': config, 'orders': orders[:100], 'truncated': len(orders) > 100,
            'rtl': request.env.lang.startswith(('ar', 'fa', 'he', 'ur')),
            'notice': bool(kw.get('changed')), 'error': bool(kw.get('error')),
            'next_states': {'new': 'preparing', 'preparing': 'ready', 'ready': 'served'},
        })
        response.headers['Cache-Control'] = 'no-store'
        return response

    @http.route('/cafe/kitchen/<int:config_id>/state', type='http', auth='user', methods=['POST'], csrf=True)
    def change(self, config_id, order_id='', target='', **kw):
        config = self._config(config_id)
        if not str(order_id).isdigit():
            raise NotFound()
        order = request.env['pos.order'].browse(int(order_id)).exists()
        if not order or order.config_id != config:
            raise NotFound()
        try:
            order._saif_kitchen_transition(target)
        except AccessError:
            raise Forbidden()
        except ValidationError:
            return request.redirect(f'/cafe/kitchen/{config.id}?error=1', code=303)
        return request.redirect(f'/cafe/kitchen/{config.id}?changed=1', code=303)
