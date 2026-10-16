"""Executed in Odoo shell on the isolated saif_pilot database only."""
import json,os
from odoo import Command
if env.cr.dbname!='saif_pilot':raise RuntimeError('Refusing seed outside isolated pilot database')
params=env['ir.config_parameter'].sudo()
if params.get_bool('saif_team.seed_complete'):
    print('Pilot already seeded; no prices, users or sessions changed.')
else:
    if env['pos.order'].search_count([]):raise RuntimeError('Refusing to seed a database containing orders')
    company=env.company
    omr=env.ref('base.OMR');omr.active=True
    company.write({'name':'Saif Team TEST ONLY','country_id':env.ref('base.om').id,'currency_id':omr.id})
    # Official Oman chart is for a synthetic isolated company; not tax compliance approval.
    env['account.chart.template'].try_loading('om',company)
    admin=env.ref('base.user_admin')
    admin.write({'login':'pilot.admin@example.test','password':os.environ['PILOT_ADMIN_PASSWORD'],'tz':'Asia/Muscat'})
    Pos=env['pos.config'].with_user(admin).with_company(company)
    result=Pos.load_onboarding_restaurant_scenario(with_demo_data=False)
    config=Pos.browse(result['config_id'])
    pricelist=env['product.pricelist'].create({'name':'TEST OMR','currency_id':omr.id,'company_id':company.id})
    config.write({'name':'Saif Team TEST Register','saif_menu_enabled':True,'saif_menu_demo':True,'self_ordering_mode':'mobile','self_ordering_pay_after':'meal','pricelist_id':pricelist.id,'available_pricelist_ids':[Command.set(pricelist.ids)]})
    category=env['pos.category'].create({'name':'أصناف اختبار / Test menu'})
    config.write({'limit_categories':True,'iface_available_categ_ids':[Command.set(category.ids)]})
    for number,(name,price) in enumerate([('شاي اختبار / Test tea',0.400),('فطيرة اختبار / Test pie',0.600)],1):
        env['product.template'].create({'name':name,'list_price':price,'type':'consu','sale_ok':True,'available_in_pos':True,'self_order_available':True,'pos_categ_ids':[Command.set(category.ids)],'taxes_id':[Command.clear()],'saif_menu_config_id':config.id,'saif_dataset_id':f'team-test-{number}'})
    session=env['pos.session'].with_user(admin).create({'config_id':config.id,'user_id':admin.id})
    session.with_user(admin).set_opening_control(0,'Synthetic pilot only')
    params.set_bool('saif_team.seed_complete',True)
    params.set_int('saif_team.config_id',config.id)
    env.cr.commit()
    print('SAIF_PILOT='+json.dumps({'config_id':config.id,'session_state':session.state,'menu_path':f'/cafe/{config.id}','admin_login':admin.login}))
