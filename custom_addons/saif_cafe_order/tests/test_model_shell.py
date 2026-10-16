# Run in odoo shell. All test mutations roll back; no live session is closed.
import uuid
from odoo.exceptions import ValidationError
class Undo(Exception):pass
c=env['pos.config'].browse(1);product=c._saif_products()[0]
checks=[]
try:
 with env.cr.savepoint():
  c.current_session_id.state='closed'
  body={'service':'car','token':c.saif_car_key,'request_id':str(uuid.uuid4()),'car':{'number':'TEST'},'cart':[{'id':product.id,'qty':1}],'expected_total':0}
  try:c._saif_submit(body,'closed-test')
  except ValidationError as e:
   assert 'closed' in str(e);checks.append('closed register rejects order')
  else:raise AssertionError('closed register accepted')
  raise Undo()
except Undo:pass
assert c.current_session_id.state=='opened'
try:
 with env.cr.savepoint():
  product.self_order_available=False
  try:c._saif_calculate([{'id':product.id,'qty':1}])
  except ValidationError:checks.append('withdrawn product rejected')
  else:raise AssertionError('unavailable product accepted')
  raise Undo()
except Undo:pass
try:
 with env.cr.savepoint():
  product.list_price=10
  tax=env['account.tax'].create({'name':'TEST 5% fictional tax','amount':5,'amount_type':'percent','type_tax_use':'sale','company_id':c.company_id.id,'country_id':c.company_id.country_id.id})
  product.taxes_id=tax
  q=c._saif_calculate([{'id':product.id,'qty':2}])
  assert q['total']==21 and q['tax']==1,q
  checks.append('server tax engine verified on fictional 5% test tax; rolled back')
  raise Undo()
except Undo:pass
env.cr.rollback()
print('SAIF_MODEL_TESTS='+repr(checks))
