"""Read and exercise kitchen transitions inside a rolled-back Odoo transaction."""
from odoo.exceptions import AccessError, ValidationError
order = env['pos.order'].search([('saif_car_number', '=', 'TEST-1610'), ('state', '=', 'draft')], limit=1)
assert order, 'Create the labelled disposable TEST-1610 order first'
# Reset only in this rolled-back test transaction, leaving the visible pilot state intact.
order.saif_kitchen_state = 'new'
assert order.prep_order_ids.prep_line_ids
original = (order.state, order.amount_paid, order.amount_total, order.lines.ids)
try:
    order._saif_kitchen_transition('ready')
    raise AssertionError('Kitchen state skip was accepted')
except ValidationError:
    pass
public = env.ref('base.public_user')
try:
    order.with_user(public)._saif_kitchen_transition('preparing')
    raise AssertionError('Public user changed a kitchen order')
except AccessError:
    pass
for target in ('preparing', 'preparing', 'ready', 'served'):
    order._saif_kitchen_transition(target)
assert order.saif_kitchen_state == 'served'
assert (order.state, order.amount_paid, order.amount_total, order.lines.ids) == original
print('PASS: preparation record, authorised transitions, repeat click, invalid skip, public denial, payment unchanged')
env.cr.rollback()
