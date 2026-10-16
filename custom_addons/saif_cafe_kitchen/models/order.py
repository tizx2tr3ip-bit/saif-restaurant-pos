from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Order(models.Model):
    _inherit = 'pos.order'

    saif_kitchen_state = fields.Selection([
        ('new', 'New'), ('preparing', 'Preparing'),
        ('ready', 'Ready'), ('served', 'Handed over')], default='new', copy=False, index=True)

    def _saif_kitchen_transition(self, target):
        self.ensure_one()
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Point of Sale access is required.'))
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset(['saif_kitchen_state', 'state'])
        if self.company_id not in self.env.companies or self.state == 'cancel' or not self.prep_order_ids:
            raise AccessError(_('This order is not available for preparation.'))
        current = self.saif_kitchen_state or 'new'
        # Repeated clicks are harmless. An old screen cannot move an order back.
        if current == target:
            return
        following = {'new': 'preparing', 'preparing': 'ready', 'ready': 'served'}
        if following.get(current) != target:
            raise ValidationError(_('The order changed. Refresh the kitchen screen.'))
        self.saif_kitchen_state = target
