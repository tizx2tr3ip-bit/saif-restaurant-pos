"""Run in an Odoo shell with this addon installed; read-only regression check.

exec(open('/path/to/pilot_tests/check_pos_order_loading.py').read())
"""
Order = env['pos.order']
config = env['pos.config'].search([], limit=1)
assert config, 'Create a pilot register before running this check'
selected = Order._load_pos_data_fields(config)
relations = Order._load_data_relations(selected)
required = {'lines', 'payment_ids', 'session_id', 'config_id', 'uuid',
            'saif_service', 'saif_car_number', 'saif_car_color', 'saif_car_type'}
assert required <= relations.keys(), f'Missing POS fields: {required - relations.keys()}'
assert relations['lines']['relation'] == 'pos.order.line'
order = Order.search([('config_id', '=', config.id), ('state', '=', 'draft')], limit=1)
if order:
    loaded = Order._load_pos_data_read(order, config)[0]
    assert required <= loaded.keys(), f'Missing order data: {required - loaded.keys()}'
    assert loaded['lines'] == order.lines.ids
print('PASS: native order relations and customer fields are loaded together')
