"""Load the full Seatribute demo scenario — all lifecycle use cases."""

from datetime import timedelta

from markupsafe import Markup

from odoo import fields


def _demo_env(env):
    return env(context=dict(env.context, maritime_management_demo_loading=True))


def post_init_hook(env):
    """Load the demo scenario, only when the module demo data is installed."""
    env = _demo_env(env)
    if not _load_refs(env):
        return
    icp = env['ir.config_parameter'].sudo()
    if not icp.get_param('maritime_management.scenario_v2'):
        _assign_demo_groups(env)
        refs = _load_refs(env)
        if not refs:
            return
        _setup_port_call_timeline(refs)
        _setup_maintenance_requests(refs)
        _prepare_maritime_stock_before_procurement(env)
        pos = _create_all_purchase_orders(env, refs)
        _finalize_maritime_stock_receipts(env)
        _setup_disbursement_accounts(env, refs, pos)
        _sync_demo_mr_stages(env)
        _post_demo_chatter_history(env, refs, pos)
        icp.set_param('maritime_management.scenario_v2', '1')
    if not icp.get_param('maritime_management.scenario_v3'):
        refs = _load_refs(env)
        if refs:
            _ensure_demo_team_users(env)
            _post_demo_email_notifications(env, refs)
        icp.set_param('maritime_management.scenario_v3', '1')
    if not icp.get_param('maritime_management.scenario_v4'):
        refs = _load_refs(env)
        if refs:
            pos = _find_existing_pos(env, refs)
            _post_demo_chatter_history(env, refs, pos)
        icp.set_param('maritime_management.scenario_v4', '1')
    if not icp.get_param('maritime_management.scenario_v5'):
        _sync_demo_mr_stages(env)
        icp.set_param('maritime_management.scenario_v5', '1')
    if not icp.get_param('maritime_management.scenario_v6'):
        refs = _load_refs(env)
        if refs:
            pos = _find_existing_pos(env, refs)
            _post_demo_chatter_history(env, refs, pos)
        icp.set_param('maritime_management.scenario_v6', '1')
    if not icp.get_param('maritime_management.scenario_v7'):
        _apply_hong_kong_locale(env)
        icp.set_param('maritime_management.scenario_v7', '1')
    if not icp.get_param('maritime_management.scenario_v8'):
        _clean_indian_locale_text(env)
        icp.set_param('maritime_management.scenario_v8', '1')
    if not icp.get_param('maritime_management.scenario_v9'):
        refs = _load_refs(env)
        if refs:
            _setup_dashboard_demo(env, refs)
        icp.set_param('maritime_management.scenario_v9', '1')
    if not icp.get_param('maritime_management.scenario_v10'):
        refs = _load_refs(env)
        if refs:
            _refresh_dashboard_arrivals_and_activity(env, refs)
        icp.set_param('maritime_management.scenario_v10', '1')
    if not icp.get_param('maritime_management.scenario_v11'):
        refs = _load_refs(env)
        if refs:
            _reseed_dashboard_activity(env, refs)
        icp.set_param('maritime_management.scenario_v11', '1')
    if not icp.get_param('maritime_management.scenario_v12'):
        _setup_maritime_stock_demo(env)
        icp.set_param('maritime_management.scenario_v12', '1')
    if not icp.get_param('maritime_management.scenario_v13'):
        _populate_vessel_master_data(env)
        icp.set_param('maritime_management.scenario_v13', '1')


def _load_refs(env):
    def ref(xmlid):
        return env.ref(f'maritime_management.{xmlid}', raise_if_not_found=False)

    keys = [
        'port_call_alpha_mumbai', 'port_call_beta_mumbai', 'port_call_gamma_piraeus',
        'port_call_delta_singapore', 'port_call_epsilon_piraeus',
        'port_call_delta_return_singapore', 'port_call_epsilon_hong_kong',
        'partner_chandler_mumbai_a', 'partner_chandler_mumbai_b', 'partner_chandler_mumbai_c',
        'partner_chandler_singapore',
        'mr_alpha_pump_seal', 'mr_alpha_filter', 'mr_alpha_draft', 'mr_beta_valve',
        'mr_beta_generator', 'mr_gamma_stores', 'mr_gamma_hvac', 'mr_gamma_purifier',
        'mr_gamma_draft', 'mr_gamma_submitted_urgent', 'mr_delta_turbo',
        'mr_epsilon_ballast', 'mr_epsilon_cancelled',
        'product_pump_seal', 'product_oil_filter', 'product_valve_kit',
        'product_generator_seal', 'product_hvac_part', 'product_turbo_bearing',
        'product_ballast_impeller',
        'da_alpha_mumbai', 'da_beta_mumbai', 'da_gamma_piraeus',
        'da_delta_singapore', 'da_epsilon_piraeus',
    ]
    refs = {k: ref(k) for k in keys}
    if not refs['port_call_alpha_mumbai']:
        return None
    return refs


def _assign_demo_groups(env):
    admin = env.ref('base.user_admin')
    for xmlid in [
        'maritime_management.group_maritime_user',
        'maritime_management.group_maritime_superintendent',
        'maritime_management.group_maritime_finance',
        'purchase.group_purchase_manager',
        'stock.group_stock_user',
        'account.group_account_manager',
        'maintenance.group_equipment_manager',
    ]:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group:
            admin.write({'group_ids': [(4, group.id)]})


def _populate_vessel_master_data(env):
    """Backfill category, team, cost centers, and specs on demo vessels."""
    company = env.ref('base.main_company', raise_if_not_found=False)
    superintendent = env.ref('maritime_management.user_demo_superintendent', raise_if_not_found=False)
    if not company:
        return

    category = env.ref('maritime_management.vessel_equipment_category', raise_if_not_found=False)
    if not category:
        category = env['maintenance.equipment.category'].create({
            'name': 'Dry Bulk Fleet',
            'company_id': company.id,
            'technician_user_id': superintendent.id if superintendent else False,
        })

    team = env.ref('maritime_management.vessel_maintenance_team', raise_if_not_found=False)
    if not team:
        team = env['maintenance.team'].create({
            'name': 'Fleet Technical',
            'company_id': company.id,
            'member_ids': [(4, superintendent.id)] if superintendent else [],
        })

    plan = env.ref('maritime_management.analytic_plan_vessels', raise_if_not_found=False)
    if not plan:
        plan = env['account.analytic.plan'].create({
            'name': 'Vessels',
        })

    vessel_specs = {
        'vessel_alpha': {
            'imo_number': '9123456',
            'serial_no': 'ALPHA-2019',
            'model': 'Handysize Bulk Carrier (32k DWT)',
            'flag_xmlid': 'base.gr',
            'analytic_code': 'VSL-ALPHA',
            'assign_date': '2024-03-01',
            'cost': 18500000,
            'note': (
                '<p><b>MV Seatribute Alpha</b> — Handysize dry bulk carrier under Sea Tribute '
                'technical management.</p><ul><li>DWT: 32,500 MT · LOA: 179 m · Built: 2019</li>'
                '<li>Main engine: MAN B&amp;W 6S50MC-C</li>'
                '<li>Trading: Asia-Pacific grain &amp; minor bulk</li></ul>'
            ),
        },
        'vessel_beta': {
            'imo_number': '9234567',
            'serial_no': 'BETA-2018',
            'model': 'Handysize Bulk Carrier (28k DWT)',
            'flag_xmlid': 'base.gr',
            'analytic_code': 'VSL-BETA',
            'assign_date': '2023-06-15',
            'cost': 16200000,
            'note': (
                '<p><b>MV Seatribute Beta</b> — Sister-class handysize, often paired with Alpha '
                'in Hong Kong.</p><ul><li>DWT: 28,200 MT · LOA: 172 m · Built: 2018</li>'
                '<li>Main engine: Wärtsilä 6L46</li>'
                '<li>Trading: Intra-Asia coal &amp; cement</li></ul>'
            ),
        },
        'vessel_gamma': {
            'imo_number': '9345678',
            'serial_no': 'GAMMA-2016',
            'model': 'Panamax Bulk Carrier (75k DWT)',
            'flag_xmlid': 'base.mh',
            'analytic_code': 'VSL-GAMMA',
            'assign_date': '2022-01-10',
            'cost': 24800000,
            'note': (
                '<p><b>MV Seatribute Gamma</b> — Panamax on long-haul grain routes, regular '
                'Piraeus calls.</p><ul><li>DWT: 75,800 MT · LOA: 225 m · Built: 2016</li>'
                '<li>Main engine: MAN B&amp;W 6S60MC-C</li>'
                '<li>Flag: Marshall Islands</li></ul>'
            ),
        },
        'vessel_delta': {
            'imo_number': '9456789',
            'serial_no': 'DELTA-2015',
            'model': 'Supramax Bulk Carrier (58k DWT)',
            'flag_xmlid': 'base.sg',
            'analytic_code': 'VSL-DELTA',
            'assign_date': '2021-09-01',
            'cost': 22100000,
            'note': (
                '<p><b>MV Seatribute Delta</b> — Supramax with strong Singapore / Straits '
                'trading history.</p><ul><li>DWT: 58,400 MT · LOA: 199 m · Built: 2015</li>'
                '<li>Main engine: MAN B&amp;W 5S50MC-C</li>'
                '<li>Recent job: turbocharger bearing replacement (completed)</li></ul>'
            ),
        },
        'vessel_epsilon': {
            'imo_number': '9567890',
            'serial_no': 'EPSILON-2017',
            'model': 'Ultramax Bulk Carrier (62k DWT)',
            'flag_xmlid': 'base.gr',
            'analytic_code': 'VSL-EPSILON',
            'assign_date': '2022-11-20',
            'cost': 23500000,
            'note': (
                '<p><b>MV Seatribute Epsilon</b> — Modern ultramax with eco-speed profile.</p>'
                '<ul><li>DWT: 62,100 MT · LOA: 199 m · Built: 2017</li>'
                '<li>Main engine: Wärtsilä 5RT-flex50</li>'
                '<li>Trading: Mediterranean / Black Sea</li></ul>'
            ),
        },
    }

    for xmlid, spec in vessel_specs.items():
        vessel = env.ref(f'maritime_management.{xmlid}', raise_if_not_found=False)
        if not vessel:
            continue
        analytic = env.ref(f'maritime_management.analytic_account_{xmlid}', raise_if_not_found=False)
        if not analytic:
            analytic = env['account.analytic.account'].search([
                ('code', '=', spec['analytic_code']),
                ('company_id', '=', company.id),
            ], limit=1)
        if not analytic:
            analytic = env['account.analytic.account'].create({
                'name': vessel.name,
                'code': spec['analytic_code'],
                'plan_id': plan.id,
                'company_id': company.id,
            })
        flag = env.ref(spec['flag_xmlid'], raise_if_not_found=False)
        vessel.write({
            'company_id': company.id,
            'is_vessel': True,
            'vessel_type': 'bulk',
            'imo_number': spec['imo_number'],
            'serial_no': spec['serial_no'],
            'model': spec['model'],
            'flag_country_id': flag.id if flag else False,
            'category_id': category.id,
            'maintenance_team_id': team.id,
            'owner_user_id': superintendent.id if superintendent else False,
            'technician_user_id': superintendent.id if superintendent else False,
            'analytic_account_id': analytic.id,
            'assign_date': spec['assign_date'],
            'cost': spec['cost'],
            'note': spec['note'],
        })

    vessels = env['maintenance.equipment'].search([('is_vessel', '=', True)])
    if vessels and hasattr(vessels, '_maritime_ensure_stock_location'):
        vessels._maritime_ensure_stock_location()


def _prepare_maritime_stock_before_procurement(env):
    """Vessel stores, storable products, and part-line product links — before PO receipts."""
    if 'maintenance.equipment' not in env.registry:
        return
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    stock_group = env.ref('stock.group_stock_user', raise_if_not_found=False)
    if admin and stock_group:
        admin.write({'group_ids': [(4, stock_group.id)]})
    vessels = env['maintenance.equipment'].search([('is_vessel', '=', True)])
    if vessels and hasattr(vessels, '_maritime_ensure_stock_location'):
        vessels._maritime_ensure_stock_location()

    products = env['product.product'].search([('default_code', 'like', 'SP-')])
    if products:
        products.write({'is_storable': True})

    Product = env['product.product']
    for part in env['maintenance.part.line'].search([]):
        if part.product_id or not part.part_number:
            continue
        product = Product.search([('default_code', '=', part.part_number)], limit=1)
        if product:
            part.product_id = product.id


def _finalize_maritime_stock_receipts(env):
    """Validate PO receipts into vessel stores and backfill legacy qty_received lines."""
    orders = env['purchase.order'].search([
        ('port_call_id', '!=', False),
        ('state', 'in', ('purchase', 'done')),
    ])
    _validate_maritime_purchase_pickings(env, orders)
    _backfill_vessel_stock_from_received_pos(env)


def _setup_maritime_stock_demo(env):
    """Full stock demo setup for upgrades (locations + receipts)."""
    _prepare_maritime_stock_before_procurement(env)
    _finalize_maritime_stock_receipts(env)


def _validate_maritime_purchase_pickings(env, orders):
    """Validate incoming pickings so PO receipts land in vessel stores."""
    if not orders:
        return
    orders = orders if hasattr(orders, '_name') else env['purchase.order'].browse(orders)
    for order in orders:
        if not order.picking_ids:
            continue
        for picking in order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            picking.action_confirm()
            picking.action_assign()
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            picking.button_validate()


def _backfill_vessel_stock_from_received_pos(env):
    """Add stock for legacy demo PO lines that were received without pickings."""
    Quant = env['stock.quant']
    lines = env['purchase.order.line'].search([
        ('order_id.port_call_id', '!=', False),
        ('order_id.state', 'in', ('purchase', 'done')),
        ('qty_received', '>', 0),
    ])
    for pol in lines:
        if not pol.product_id.is_storable:
            continue
        vessel = pol.order_id.port_call_id.vessel_id
        if not vessel or not vessel.stock_location_id:
            continue
        location = vessel.stock_location_id
        qty_needed = pol.product_uom_id._compute_quantity(
            pol.qty_received, pol.product_id.uom_id,
        )
        available = pol.product_id.with_context(location=location.id).qty_available
        if qty_needed > available:
            Quant._update_available_quantity(
                pol.product_id, location, qty_needed - available,
            )


def _setup_port_call_timeline(refs):
    """Set port call ETAs/states — tuned for control center dashboard density."""
    now = fields.Datetime.now()
    refs['port_call_alpha_mumbai'].write({
        'eta': now - timedelta(days=1),
        'etd': now + timedelta(days=3),
        'state': 'active',
    })
    refs['port_call_beta_mumbai'].write({
        'eta': now - timedelta(days=1),
        'etd': now + timedelta(hours=30),
        'state': 'active',
    })
    refs['port_call_gamma_piraeus'].write({
        'eta': now + timedelta(days=4),
        'etd': now + timedelta(days=7),
        'state': 'planned',
    })
    refs['port_call_delta_singapore'].write({
        'eta': now - timedelta(days=8),
        'etd': now - timedelta(days=5),
        'state': 'departed',
    })
    refs['port_call_epsilon_piraeus'].write({
        'eta': now - timedelta(days=12),
        'etd': now - timedelta(days=10),
        'state': 'departed',
    })


def _setup_maintenance_requests(refs):
    refs['mr_gamma_stores'].write({'shore_state': 'submitted'})
    refs['mr_gamma_hvac'].write({'shore_state': 'approved'})
    refs['mr_epsilon_cancelled'].write({'shore_state': 'cancelled'})


def _create_all_purchase_orders(env, refs):
    PO = env['purchase.order']
    if PO.search([
        ('port_call_id', '!=', False),
        ('state', 'in', ('purchase', 'done')),
    ], limit=1):
        return _find_existing_pos(env, refs)

    po_alpha = PO.create({
        'partner_id': refs['partner_chandler_mumbai_a'].id,
        'port_call_id': refs['port_call_alpha_mumbai'].id,
        'order_line': [
            (0, 0, {
                'product_id': refs['product_pump_seal'].id,
                'product_qty': 2,
                'price_unit': 450.0,
                'maintenance_request_id': refs['mr_alpha_pump_seal'].id,
            }),
            (0, 0, {
                'product_id': refs['product_oil_filter'].id,
                'product_qty': 4,
                'price_unit': 120.0,
                'maintenance_request_id': refs['mr_alpha_filter'].id,
            }),
        ],
    })
    po_alpha.button_confirm()
    refs['mr_alpha_pump_seal'].shore_state = 'approved'
    refs['mr_alpha_filter'].shore_state = 'delivered'
    _validate_maritime_purchase_pickings(env, po_alpha)

    for partner, price in [
        (refs['partner_chandler_mumbai_b'], 520.0),
        (refs['partner_chandler_mumbai_c'], 475.0),
    ]:
        rfq = PO.create({
            'partner_id': partner.id,
            'port_call_id': refs['port_call_alpha_mumbai'].id,
            'order_line': [(0, 0, {
                'product_id': refs['product_pump_seal'].id,
                'product_qty': 2,
                'price_unit': price,
                'maintenance_request_id': refs['mr_alpha_pump_seal'].id,
            })],
        })
        rfq.sudo().write({'state': 'sent'})

    PO.create({
        'partner_id': refs['partner_chandler_mumbai_c'].id,
        'port_call_id': refs['port_call_alpha_mumbai'].id,
        'order_line': [(0, 0, {
            'product_id': refs['product_oil_filter'].id,
            'product_qty': 4,
            'price_unit': 115.0,
            'maintenance_request_id': refs['mr_alpha_filter'].id,
        })],
    })

    po_beta = PO.create({
        'partner_id': refs['partner_chandler_mumbai_b'].id,
        'port_call_id': refs['port_call_beta_mumbai'].id,
        'order_line': [(0, 0, {
            'product_id': refs['product_valve_kit'].id,
            'product_qty': 1,
            'price_unit': 2800.0,
            'maintenance_request_id': refs['mr_beta_valve'].id,
        })],
    })
    po_beta.button_confirm()
    _validate_maritime_purchase_pickings(env, po_beta)
    refs['mr_beta_valve'].shore_state = 'approved'

    po_delta = PO.create({
        'partner_id': refs['partner_chandler_singapore'].id,
        'port_call_id': refs['port_call_delta_singapore'].id,
        'order_line': [(0, 0, {
            'product_id': refs['product_turbo_bearing'].id,
            'product_qty': 1,
            'price_unit': 4200.0,
            'maintenance_request_id': refs['mr_delta_turbo'].id,
        })],
    })
    po_delta.button_confirm()
    _validate_maritime_purchase_pickings(env, po_delta)
    refs['mr_delta_turbo'].shore_state = 'done'

    po_eps = PO.create({
        'partner_id': refs['partner_chandler_mumbai_a'].id,
        'port_call_id': refs['port_call_epsilon_piraeus'].id,
        'order_line': [(0, 0, {
            'product_id': refs['product_ballast_impeller'].id,
            'product_qty': 1,
            'price_unit': 1550.0,
            'maintenance_request_id': refs['mr_epsilon_ballast'].id,
        })],
    })
    po_eps.button_confirm()
    _validate_maritime_purchase_pickings(env, po_eps)
    refs['mr_epsilon_ballast'].shore_state = 'done'

    return {
        'alpha': po_alpha,
        'beta': po_beta,
        'delta': po_delta,
        'epsilon': po_eps,
    }


def _find_existing_pos(env, refs):
    PO = env['purchase.order']
    return {
        'alpha': PO.search([
            ('port_call_id', '=', refs['port_call_alpha_mumbai'].id),
            ('state', 'in', ('purchase', 'done')),
        ], order='id', limit=1),
        'beta': PO.search([
            ('port_call_id', '=', refs['port_call_beta_mumbai'].id),
            ('state', 'in', ('purchase', 'done')),
        ], order='id', limit=1),
        'delta': PO.search([
            ('port_call_id', '=', refs['port_call_delta_singapore'].id),
            ('state', 'in', ('purchase', 'done')),
        ], order='id', limit=1),
        'epsilon': PO.search([
            ('port_call_id', '=', refs['port_call_epsilon_piraeus'].id),
            ('state', 'in', ('purchase', 'done')),
        ], order='id', limit=1),
    }


def _setup_disbursement_accounts(env, refs, pos):
    da_alpha = refs['da_alpha_mumbai']
    if da_alpha and pos.get('alpha'):
        da_alpha.write({
            'purchase_order_ids': [(6, 0, [pos['alpha'].id])],
            'state': 'fda_submitted',
        })
        da_alpha.line_ids.filtered(lambda l: l.line_type == 'fda').unlink()
        da_alpha.write({'line_ids': [
            (0, 0, {'line_type': 'fda', 'charge_category': 'spares',
                    'name': 'Pump seal kit — actual', 'purchase_order_id': pos['alpha'].id, 'amount': 900.0}),
            (0, 0, {'line_type': 'fda', 'charge_category': 'spares',
                    'name': 'Oil filters — actual', 'purchase_order_id': pos['alpha'].id, 'amount': 480.0}),
            (0, 0, {'line_type': 'fda', 'charge_category': 'agency',
                    'name': 'Agency fee — actual', 'amount': 350.0}),
        ]})

    da_beta = refs['da_beta_mumbai']
    if da_beta and pos.get('beta'):
        da_beta.write({
            'purchase_order_ids': [(6, 0, [pos['beta'].id])],
            'state': 'pda_approved',
        })

    da_gamma = refs['da_gamma_piraeus']
    if da_gamma:
        da_gamma.write({'state': 'pda_submitted'})

    da_delta = refs['da_delta_singapore']
    if da_delta and pos.get('delta'):
        da_delta.write({
            'purchase_order_ids': [(6, 0, [pos['delta'].id])],
            'state': 'paid',
        })
        da_delta.line_ids.filtered(lambda l: l.line_type == 'fda').unlink()
        da_delta.write({'line_ids': [
            (0, 0, {'line_type': 'fda', 'charge_category': 'spares',
                    'name': 'Turbo bearing kit — actual', 'purchase_order_id': pos['delta'].id, 'amount': 4200.0}),
            (0, 0, {'line_type': 'fda', 'charge_category': 'agency',
                    'name': 'Agency fee — actual', 'amount': 480.0}),
        ]})

    da_epsilon = refs['da_epsilon_piraeus']
    if da_epsilon and pos.get('epsilon'):
        da_epsilon.write({
            'purchase_order_ids': [(6, 0, [pos['epsilon'].id])],
            'state': 'matched',
        })
        da_epsilon.line_ids.filtered(lambda l: l.line_type == 'fda').unlink()
        da_epsilon.write({'line_ids': [
            (0, 0, {'line_type': 'fda', 'charge_category': 'spares',
                    'name': 'Ballast impeller — actual', 'purchase_order_id': pos['epsilon'].id, 'amount': 1550.0}),
            (0, 0, {'line_type': 'fda', 'charge_category': 'agency',
                    'name': 'Agency fee — actual', 'amount': 395.0}),
        ]})


def _setup_dashboard_demo(env, refs):
    """Enrich demo data so the control center dashboard is fully populated."""
    now = fields.Datetime.now()
    PO = env['purchase.order']

    _setup_port_call_timeline(refs)

    # --- Maintenance request states across the full pipeline ---
    if refs.get('mr_alpha_draft'):
        refs['mr_alpha_draft'].write({'shore_state': 'draft'})
    if refs.get('mr_gamma_draft'):
        refs['mr_gamma_draft'].write({'shore_state': 'draft'})
    if refs.get('mr_gamma_stores'):
        refs['mr_gamma_stores'].write({'shore_state': 'submitted'})
    if refs.get('mr_gamma_submitted_urgent'):
        refs['mr_gamma_submitted_urgent'].write({'shore_state': 'submitted'})
    if refs.get('mr_gamma_hvac'):
        refs['mr_gamma_hvac'].write({'shore_state': 'approved'})
    if refs.get('mr_gamma_purifier'):
        refs['mr_gamma_purifier'].write({'shore_state': 'approved'})
    if refs.get('mr_beta_generator'):
        refs['mr_beta_generator'].write({'shore_state': 'approved'})
    if refs.get('mr_alpha_pump_seal'):
        refs['mr_alpha_pump_seal'].write({'shore_state': 'approved'})
    if refs.get('mr_alpha_filter'):
        refs['mr_alpha_filter'].write({'shore_state': 'delivered'})
    if refs.get('mr_beta_valve'):
        refs['mr_beta_valve'].write({'shore_state': 'approved'})
    if refs.get('mr_delta_turbo'):
        refs['mr_delta_turbo'].write({'shore_state': 'done'})
    if refs.get('mr_epsilon_ballast'):
        refs['mr_epsilon_ballast'].write({'shore_state': 'done'})
    if refs.get('mr_epsilon_cancelled'):
        refs['mr_epsilon_cancelled'].write({'shore_state': 'cancelled'})

    # Backdate submitted MRs for "awaiting approval" risk alerts.
    for xmlid in ('mr_gamma_stores', 'mr_gamma_submitted_urgent'):
        mr = refs.get(xmlid)
        if mr:
            env.cr.execute(
                "UPDATE maintenance_request SET create_date = %s WHERE id = %s",
                (now - timedelta(days=5), mr.id),
            )

    # RFQ only (not confirmed) for VITAL generator job — triggers procurement + risk KPIs.
    if refs.get('mr_beta_generator') and refs.get('product_generator_seal'):
        existing = PO.search([
            ('port_call_id', '=', refs['port_call_beta_mumbai'].id),
            ('order_line.maintenance_request_id', '=', refs['mr_beta_generator'].id),
        ], limit=1)
        if not existing:
            rfq = PO.create({
                'partner_id': refs['partner_chandler_mumbai_c'].id,
                'port_call_id': refs['port_call_beta_mumbai'].id,
                'order_line': [(0, 0, {
                    'product_id': refs['product_generator_seal'].id,
                    'product_qty': 1,
                    'price_unit': 890.0,
                    'maintenance_request_id': refs['mr_beta_generator'].id,
                })],
            })
            rfq.sudo().write({'state': 'sent'})

    # Gamma: sent RFQ for purifier (no confirmed PO on this port call).
    if refs.get('mr_gamma_purifier') and refs.get('product_hvac_part'):
        if not PO.search([
            ('port_call_id', '=', refs['port_call_gamma_piraeus'].id),
            ('state', 'in', ('purchase', 'done')),
        ], limit=1):
            gamma_rfq = PO.search([
                ('port_call_id', '=', refs['port_call_gamma_piraeus'].id),
                ('state', '=', 'sent'),
            ], limit=1)
            if not gamma_rfq:
                gamma_rfq = PO.create({
                    'partner_id': refs['partner_chandler_singapore'].id,
                    'port_call_id': refs['port_call_gamma_piraeus'].id,
                    'order_line': [(0, 0, {
                        'product_id': refs['product_hvac_part'].id,
                        'product_qty': 1,
                        'price_unit': 2100.0,
                        'maintenance_request_id': refs['mr_gamma_purifier'].id,
                    })],
                })
                gamma_rfq.sudo().write({'state': 'sent'})

    # --- Disbursement accounts: finance KPIs, variance chart, spend bars ---
    da_alpha = refs.get('da_alpha_mumbai')
    if da_alpha:
        da_alpha.write({'state': 'fda_submitted'})
        da_alpha.line_ids.filtered(lambda l: l.line_type == 'fda').unlink()
        da_alpha.write({'line_ids': [
            (0, 0, {'line_type': 'fda', 'charge_category': 'spares',
                    'name': 'Pump seal kit — actual', 'amount': 900.0}),
            (0, 0, {'line_type': 'fda', 'charge_category': 'spares',
                    'name': 'Oil filters — actual', 'amount': 480.0}),
            (0, 0, {'line_type': 'fda', 'charge_category': 'agency',
                    'name': 'Agency fee — actual', 'amount': 350.0}),
        ]})

    da_beta = refs.get('da_beta_mumbai')
    if da_beta:
        da_beta.write({'state': 'pda_approved'})

    da_gamma = refs.get('da_gamma_piraeus')
    if da_gamma:
        da_gamma.write({'state': 'pda_submitted'})

    da_delta = refs.get('da_delta_singapore')
    pos = _find_existing_pos(env, refs)
    if da_delta and pos.get('delta'):
        da_delta.write({
            'purchase_order_ids': [(6, 0, [pos['delta'].id])],
            'state': 'paid',
        })
        da_delta.line_ids.filtered(lambda l: l.line_type == 'fda').unlink()
        da_delta.write({'line_ids': [
            (0, 0, {'line_type': 'fda', 'charge_category': 'spares',
                    'name': 'Turbo bearing kit — actual (over budget)',
                    'purchase_order_id': pos['delta'].id, 'amount': 4800.0}),
            (0, 0, {'line_type': 'fda', 'charge_category': 'agency',
                    'name': 'Agency fee — actual', 'amount': 520.0}),
        ]})

    da_epsilon = refs.get('da_epsilon_piraeus')
    if da_epsilon and pos.get('epsilon'):
        da_epsilon.write({
            'purchase_order_ids': [(6, 0, [pos['epsilon'].id])],
            'state': 'matched',
        })
        da_epsilon.line_ids.filtered(lambda l: l.line_type == 'fda').unlink()
        da_epsilon.write({'line_ids': [
            (0, 0, {'line_type': 'fda', 'charge_category': 'spares',
                    'name': 'Ballast impeller — actual',
                    'purchase_order_id': pos['epsilon'].id, 'amount': 1550.0}),
            (0, 0, {'line_type': 'fda', 'charge_category': 'agency',
                    'name': 'Agency fee — actual', 'amount': 395.0}),
        ]})

    _setup_upcoming_arrivals(refs)
    _sync_demo_mr_stages(env)
    _post_recent_activity(env, refs)


def _refresh_dashboard_arrivals_and_activity(env, refs):
    """Backfill upcoming port calls + recent activity feed for existing databases."""
    _setup_port_call_timeline(refs)
    _setup_upcoming_arrivals(refs)
    _post_recent_activity(env, refs)


def _setup_upcoming_arrivals(refs):
    """Two additional planned calls so Arriving This Week is visible on the dashboard."""
    now = fields.Datetime.now()
    if refs.get('port_call_delta_return_singapore'):
        refs['port_call_delta_return_singapore'].write({
            'eta': now + timedelta(days=3),
            'etd': now + timedelta(days=6),
            'state': 'planned',
        })
    if refs.get('port_call_epsilon_hong_kong'):
        refs['port_call_epsilon_hong_kong'].write({
            'eta': now + timedelta(days=5),
            'etd': now + timedelta(days=8),
            'state': 'planned',
        })


def _post_recent_activity(env, refs):
    """Seed a backdated chatter timeline for the dashboard Recent activity panel."""
    now = fields.Datetime.now()
    agent_hk = env.ref('maritime_management.partner_agent_mumbai', raise_if_not_found=False)
    agent_pir = env.ref('maritime_management.partner_agent_piraeus', raise_if_not_found=False)
    agent_sg = env.ref('maritime_management.partner_agent_singapore', raise_if_not_found=False)
    superintendent = env.ref('maritime_management.user_demo_superintendent', raise_if_not_found=False)
    su_partner = superintendent.partner_id if superintendent else None

    PO = env['purchase.order']
    gamma_rfq = PO.search([
        ('port_call_id', '=', refs['port_call_gamma_piraeus'].id),
        ('state', '=', 'sent'),
    ], limit=1) if refs.get('port_call_gamma_piraeus') else PO
    beta_rfq = PO.search([
        ('port_call_id', '=', refs['port_call_beta_mumbai'].id),
        ('state', '=', 'sent'),
    ], limit=1) if refs.get('port_call_beta_mumbai') else PO

    # (hours_ago, record, keyword, body, author_partner)
    entries = [
        (68, refs.get('port_call_delta_singapore'), 'feed-delta-paid',
         'Delta departed Singapore — turbo bearing job closed and FDA paid.', agent_sg),
        (54, refs.get('da_epsilon_piraeus'), 'feed-epsilon-matched',
         'Epsilon disbursement matched — ballast impeller within PDA tolerance.', su_partner),
        (48, refs.get('port_call_epsilon_piraeus'), 'feed-epsilon-closed',
         'Epsilon port call archived — 3-way match complete.', agent_pir),
        (36, refs.get('port_call_gamma_piraeus'), 'feed-gamma-planned',
         'Gamma voyage plan filed — ETA Piraeus in 4 days. Superintendent notified.', agent_pir),
        (30, refs.get('mr_gamma_stores'), 'feed-mr-stores',
         'Stores replenishment submitted — awaiting superintendent approval.', agent_pir),
        (28, refs.get('mr_gamma_submitted_urgent'), 'feed-mr-compressor',
         'Air compressor bearings flagged essential for Piraeus call.', agent_pir),
        (24, refs.get('da_gamma_piraeus'), 'feed-pda-gamma',
         'PDA submitted for Gamma / Piraeus — finance budget review requested.', agent_pir),
        (20, refs.get('port_call_alpha_mumbai'), 'feed-alpha-active',
         'Alpha alongside Hong Kong — agent consolidating spares for 2 open jobs.', agent_hk),
        (18, refs.get('mr_alpha_pump_seal'), 'feed-alpha-procured',
         'Pump seal kit procured — chandler confirms delivery before ETD.', agent_hk),
        (16, refs.get('port_call_beta_mumbai'), 'feed-beta-etd',
         'Beta ETD in 30 hours — generator seal RFQ still outstanding.', agent_hk),
        (14, refs.get('mr_beta_generator'), 'feed-mr-generator',
         'VITAL: Generator fuel pump seal assigned — RFQ sent to chandler.', su_partner),
        (12, refs.get('da_alpha_mumbai'), 'feed-fda-alpha',
         'FDA submitted for Alpha — under budget vs PDA. Finance notified.', agent_hk),
        (10, refs.get('mr_gamma_hvac'), 'feed-mr-hvac-approved',
         'HVAC spare approved — ready for agent assignment on Gamma call.', su_partner),
        (8, refs.get('port_call_delta_return_singapore'), 'feed-delta-return',
         'Delta return voyage to Singapore confirmed — ETA in 3 days.', agent_sg),
        (6, refs.get('port_call_epsilon_hong_kong'), 'feed-epsilon-hk',
         'Epsilon routed via Hong Kong — stores replenishment call planned.', agent_hk),
        (4, refs.get('mr_gamma_purifier'), 'feed-mr-purifier',
         'Purifier service kit assigned — RFQ out to Singapore chandler.', agent_pir),
        (2, refs.get('port_call_beta_mumbai'), 'feed-beta-chase',
         'Agent chasing quotes for generator seal — ETD pressure building.', agent_hk),
        (1, refs.get('mr_gamma_submitted_urgent'), 'feed-mr-urgent',
         'Compressor bearings still in approval queue — 5 days since submission.', su_partner),
        (0.5, refs.get('port_call_gamma_piraeus'), 'feed-gamma-readiness',
         'Pre-arrival checklist: 2 MRs awaiting approval, PDA with finance.', agent_pir),
    ]
    if gamma_rfq:
        entries.append((
            5, gamma_rfq, 'feed-gamma-rfq',
            'RFQ sent for purifier kit — awaiting chandler response.', agent_pir,
        ))
    if beta_rfq:
        entries.append((
            3, beta_rfq, 'feed-beta-rfq',
            'Generator seal RFQ open — no confirmed PO yet.', agent_hk,
        ))

    for idx, (hours_ago, record, keyword, body, partner) in enumerate(
        sorted(entries, key=lambda e: e[0], reverse=True)
    ):
        if not record:
            continue
        msg_date = now - timedelta(hours=hours_ago, minutes=idx)
        _post_if_missing(env, record, keyword, body, partner, msg_date=msg_date)


def _reseed_dashboard_activity(env, refs):
    """Replace noisy / double-encoded dashboard feed messages with a clean timeline."""
    _purge_dashboard_feed_messages(env)
    _post_recent_activity(env, refs)


def _purge_dashboard_feed_messages(env):
    """Remove demo dashboard chatter so the feed can be re-seeded cleanly."""
    phrases = [
        'Port call active at Hong Kong',
        'Gamma arriving Piraeus',
        'Stores replenishment submitted 5 days ago',
        'Air compressor bearings submitted',
        'VITAL: Generator fuel pump seal assigned',
        'PDA submitted for Gamma / Piraeus — finance review requested',
        'FDA submitted for Alpha — under budget',
        'Delta port call paid — turbo bearing job closed',
        'Epsilon disbursement matched — ready for payment',
        'Reminder: Beta ETD in 30 hours',
        'Delta departed Singapore',
        'Epsilon disbursement matched — ballast',
        'Epsilon port call archived',
        'Gamma voyage plan filed',
        'Pre-arrival checklist',
        'Agent chasing quotes for generator seal',
        'Compressor bearings still in approval queue',
        'Delta return voyage to Singapore',
        'Epsilon routed via Hong Kong',
        'Purifier service kit assigned',
        'Pump seal kit procured',
        'HVAC spare approved',
        'RFQ sent for purifier kit',
        'Generator seal RFQ open',
    ]
    MailMessage = env['mail.message'].sudo()
    MailMessage.search([('body', 'ilike', '<!-- mcc:')]).unlink()
    for phrase in phrases:
        MailMessage.search([('body', 'ilike', phrase)]).unlink()


def _ensure_demo_team_users(env):
    """Ensure dedicated demo inboxes exist for superintendent and finance."""
    specs = [
        {
            'xmlid': 'maritime_management.user_demo_superintendent',
            'name': 'Demo Superintendent',
            'login': 'superintendent@seatribute.demo',
            'email': 'superintendent@seatribute.demo',
            'groups': [
                'base.group_user',
                'maritime_management.group_maritime_user',
                'maritime_management.group_maritime_superintendent',
                'maintenance.group_equipment_manager',
            ],
        },
        {
            'xmlid': 'maritime_management.user_demo_finance',
            'name': 'Demo Finance',
            'login': 'finance@seatribute.demo',
            'email': 'finance@seatribute.demo',
            'groups': [
                'base.group_user',
                'maritime_management.group_maritime_user',
                'maritime_management.group_maritime_finance',
                'account.group_account_user',
            ],
        },
    ]
    for spec in specs:
        user = env.ref(spec['xmlid'], raise_if_not_found=False)
        if not user:
            partner = env['res.partner'].create({
                'name': spec['name'],
                'email': spec['email'],
                'company_id': env.company.id,
            })
            group_ids = [
                env.ref(g, raise_if_not_found=False).id
                for g in spec['groups']
                if env.ref(g, raise_if_not_found=False)
            ]
            user = env['res.users'].create({
                'name': spec['name'],
                'login': spec['login'],
                'email': spec['email'],
                'partner_id': partner.id,
                'company_id': env.company.id,
                'company_ids': [(6, 0, [env.company.id])],
                'group_ids': [(6, 0, group_ids)],
            })
        user.write({'password': 'demo'})


def _sync_demo_mr_stages(env):
    """Align maintenance.stage with maritime shore_state on demo records."""
    mrs = env['maintenance.request'].search([('port_call_id', '!=', False)])
    if mrs:
        mrs._sync_stage_from_shore_state()


def _post_if_missing(env, record, keyword, body, partner=None, *, msg_date=None):
    """Post a chatter message only if a similar one does not exist yet."""
    if not record:
        return
    marker = f'<!-- mcc:{keyword} -->'
    existing = env['mail.message'].search([
        ('model', '=', record._name),
        ('res_id', '=', record.id),
        ('body', 'ilike', marker),
    ], limit=1)
    if existing:
        return
    if isinstance(body, str) and not body.lstrip().startswith('<'):
        body = Markup(f'<p>{body}</p>{marker}')
    elif marker not in (body or ''):
        body = Markup(f'{body}{marker}')
    kwargs = {'body': body, 'subtype_xmlid': 'mail.mt_comment'}
    if partner:
        kwargs['partner_ids'] = partner.ids
    if msg_date:
        kwargs['date'] = msg_date
    record.message_post(**kwargs)


def _post_timeline(env, record, entries):
    """Post backdated chatter entries in chronological order (oldest first)."""
    if not record:
        return
    now = fields.Datetime.now()
    for idx, entry in enumerate(entries):
        days_ago = entry[0]
        keyword = entry[1]
        body = entry[2]
        partner = entry[3] if len(entry) > 3 else None
        msg_date = now - timedelta(days=days_ago, minutes=idx)
        _post_if_missing(env, record, keyword, body, partner, msg_date=msg_date)


def _apply_hong_kong_locale(env):
    """Replace Indian port/agent demo labels with Hong Kong for existing databases."""
    hk_country = env.ref('base.hk', raise_if_not_found=False)
    if not hk_country:
        return

    hk_port = env.ref('maritime_management.port_hong_kong', raise_if_not_found=False)
    if not hk_port:
        legacy = env['maritime.port'].search([('code', 'in', ('INBOM', 'HKHKG'))], limit=1)
        if legacy:
            legacy.write({
                'name': 'Hong Kong',
                'code': 'HKHKG',
                'country_id': hk_country.id,
                'city': 'Hong Kong',
                'active': True,
            })
            hk_port = legacy
        else:
            hk_port = env['maritime.port'].create({
                'name': 'Hong Kong',
                'code': 'HKHKG',
                'country_id': hk_country.id,
                'city': 'Hong Kong',
            })

    for legacy in env['maritime.port'].search([('code', '=', 'INBOM')]):
        if legacy != hk_port:
            legacy.active = False

    agent = env.ref('maritime_management.partner_agent_mumbai', raise_if_not_found=False)
    if agent and hk_port:
        agent.write({
            'name': 'Hong Kong Maritime Services',
            'street': 'Central Plaza, 18 Harbour Road',
            'city': 'Hong Kong',
            'country_id': hk_country.id,
            'email': 'ops@hkmaritime.demo',
            'maritime_port_ids': [(6, 0, [hk_port.id])],
        })

    chandler_updates = {
        'partner_chandler_mumbai_a': 'Harbour Marine Supplies Ltd',
        'partner_chandler_mumbai_b': 'Victoria Harbour Ship Chandlers',
        'partner_chandler_mumbai_c': 'Kowloon Marine Stores Co.',
    }
    for xmlid, name in chandler_updates.items():
        partner = env.ref(f'maritime_management.{xmlid}', raise_if_not_found=False)
        if partner and hk_port:
            partner.write({
                'name': name,
                'city': 'Hong Kong',
                'country_id': hk_country.id,
                'maritime_port_ids': [(6, 0, [hk_port.id])],
            })

    port_call_notes = {
        'port_call_alpha_mumbai': (
            '<p><b>ACTIVE DEMO</b> — Alpha at Hong Kong. '
            'Agent consolidating spares for 2 maintenance jobs.</p>'
        ),
        'port_call_beta_mumbai': (
            '<p><b>ACTIVE DEMO</b> — Beta at Hong Kong. '
            'Same agent, different vessel — multi-ship consolidation.</p>'
        ),
    }
    for xmlid, note in port_call_notes.items():
        port_call = env.ref(f'maritime_management.{xmlid}', raise_if_not_found=False)
        if port_call and hk_port:
            port_call.write({'port_id': hk_port.id, 'note': note})

    _clean_indian_locale_text(env)


def _clean_indian_locale_text(env):
    replacements = [
        ('Mumbai Maritime Services', 'Hong Kong Maritime Services'),
        ('Beta / Mumbai', 'Beta / Hong Kong'),
        ('@ Mumbai', '@ Hong Kong'),
        ('assigned to Mumbai', 'assigned to Hong Kong'),
        ('Mumbai port call', 'Hong Kong port call'),
        ('Western India Ship Suppliers', 'Victoria Harbour Ship Chandlers'),
        ('Bombay Marine Stores Co.', 'Kowloon Marine Stores Co.'),
        ('Arabian Sea Chandlers Pvt Ltd', 'Harbour Marine Supplies Ltd'),
        ('Mumbai', 'Hong Kong'),
    ]
    terms = ('Mumbai', 'India', 'Bombay', 'Arabian Sea')
    for model, field in [('mail.message', 'body'), ('mail.mail', 'body_html')]:
        domain = ['|'] * (len(terms) - 1) + [(field, 'ilike', t) for t in terms]
        for record in env[model].search(domain):
            text = record[field] or ''
            for old, new in replacements:
                text = text.replace(old, new)
            record.write({field: text})


def _post_demo_chatter_history(env, refs, pos):
    """Build realistic chatter timelines on all demo documents."""
    agent_hong_kong = env.ref('maritime_management.partner_agent_mumbai', raise_if_not_found=False)
    agent_piraeus = env.ref('maritime_management.partner_agent_piraeus', raise_if_not_found=False)
    agent_singapore = env.ref('maritime_management.partner_agent_singapore', raise_if_not_found=False)

    alpha = refs['port_call_alpha_mumbai']
    beta = refs['port_call_beta_mumbai']
    gamma = refs['port_call_gamma_piraeus']
    delta = refs['port_call_delta_singapore']
    epsilon = refs['port_call_epsilon_piraeus']

    # --- Port calls ---
    _post_if_missing(env, alpha, 'Port call activated',
        'Port call activated. Agent Hong Kong Maritime Services notified by email.',
        agent_hong_kong)
    _post_if_missing(env, beta, 'Port call activated',
        'Port call activated. Agent Hong Kong Maritime Services assigned for Beta @ Hong Kong.',
        agent_hong_kong)
    _post_if_missing(env, gamma, 'Port call planned',
        'Port call planned for Gamma @ Piraeus. Agent Piraeus Ship Agency SA assigned.',
        agent_piraeus)

    da_delta = refs['da_delta_singapore']
    po_delta = pos.get('delta')
    if delta:
        delta_pc_timeline = [
            (25, 'Port call activated',
             'Port call activated for Delta @ Singapore. '
             'Agent Singapore Maritime Agency notified by email.',
             agent_singapore),
            (22, 'Maintenance job assigned',
             'Maintenance job (turbo bearing replacement) assigned to Singapore port call. '
             'Agent notified by email.',
             agent_singapore),
        ]
        if da_delta:
            delta_pc_timeline.extend([
                (20, 'PDA submitted',
                 f'PDA submitted — budget EUR {da_delta.pda_amount:,.0f} sent to finance team.'),
                (19, 'PDA approved',
                 f'PDA approved — agent authorised to purchase up to EUR {da_delta.pda_amount:,.0f}. '
                 'Email sent to agent.',
                 da_delta.agent_id),
            ])
        if po_delta:
            delta_pc_timeline.append((
                16, 'Agent purchased spares',
                f'Alert: Agent purchased spares on {po_delta.name} covering turbo bearing replacement.',
                agent_singapore,
            ))
        if da_delta:
            delta_pc_timeline.extend([
                (10, 'FDA submitted',
                 f'FDA submitted — actual costs EUR {da_delta.fda_amount:,.0f}. '
                 f'Variance vs PDA: {da_delta.variance_percent:.1f}%. Finance notified.'),
                (8, 'Payment approved',
                 'Disbursement account payment approved. Agent notified by email.',
                 da_delta.agent_id),
            ])
        delta_pc_timeline.append((
            4, 'Port call departed',
            'Port call departed Singapore. Full procurement and disbursement cycle completed.',
        ))
        _post_timeline(env, delta, delta_pc_timeline)

    da_epsilon = refs['da_epsilon_piraeus']
    po_epsilon = pos.get('epsilon')
    if epsilon:
        epsilon_pc_timeline = [
            (40, 'Port call activated',
             'Port call activated for Epsilon @ Piraeus. '
             'Agent Piraeus Ship Agency SA notified by email.',
             agent_piraeus),
            (37, 'Maintenance job assigned',
             'Maintenance job (ballast pump impeller) assigned to Piraeus port call. '
             'Agent notified by email.',
             agent_piraeus),
        ]
        if da_epsilon:
            epsilon_pc_timeline.extend([
                (35, 'PDA submitted',
                 f'PDA submitted — budget EUR {da_epsilon.pda_amount:,.0f} sent to finance team.'),
                (34, 'PDA approved',
                 f'PDA approved — agent authorised to purchase up to EUR {da_epsilon.pda_amount:,.0f}. '
                 'Email sent to agent.',
                 da_epsilon.agent_id),
            ])
        if po_epsilon:
            epsilon_pc_timeline.append((
                31, 'Agent purchased spares',
                f'Alert: Agent purchased spares on {po_epsilon.name} covering ballast pump renewal.',
                agent_piraeus,
            ))
        if da_epsilon:
            epsilon_pc_timeline.extend([
                (30, 'FDA submitted',
                 f'FDA submitted — actual costs EUR {da_epsilon.fda_amount:,.0f}. '
                 f'Variance vs PDA: {da_epsilon.variance_percent:.1f}%. Finance notified.'),
                (28, '3-way match complete',
                 '3-way match complete — PDA, PO, and vendor bills reconciled.'),
            ])
        epsilon_pc_timeline.append((
            2, 'Port call closed',
            'Port call closed. All maintenance jobs and disbursement accounts reconciled.',
        ))
        _post_timeline(env, epsilon, epsilon_pc_timeline)

    # --- Maintenance requests ---
    mr_messages = [
        (refs['mr_alpha_pump_seal'], 'assigned to Hong Kong',
         'Maintenance job assigned to Hong Kong port call. Agent notified by email.', agent_hong_kong),
        (refs['mr_alpha_filter'], 'assigned to Hong Kong',
         'Maintenance job assigned to Hong Kong port call. Agent notified by email.', agent_hong_kong),
        (refs['mr_beta_valve'], 'assigned to Hong Kong',
         'Maintenance job assigned to Beta / Hong Kong port call. Agent notified by email.', agent_hong_kong),
        (refs['mr_gamma_stores'], 'submitted from',
         'Maintenance request submitted from MV Seatribute Gamma for shore approval. Superintendent notified by email.', None),
        (refs['mr_gamma_hvac'], 'Approved by superintendent',
         'Approved by superintendent. Awaiting port call assignment.', None),
        (refs['mr_delta_turbo'], 'Procured and delivered',
         'Procured and delivered in Singapore. Job completed onboard.', None),
        (refs['mr_epsilon_ballast'], 'Procured and delivered',
         'Procured and delivered in Piraeus. Job completed onboard.', None),
        (refs['mr_epsilon_cancelled'], 'Cancelled — covered under',
         'Cancelled — covered under warranty. No procurement required.', None),
    ]
    for record, keyword, body, partner in mr_messages:
        _post_if_missing(env, record, keyword, body, partner)

    # --- Disbursement accounts ---
    da_alpha = refs['da_alpha_mumbai']
    if da_alpha:
        alpha_po = pos.get('alpha')
        alpha_timeline = [
            (12, 'PDA submitted',
             f'PDA submitted for review — budget EUR {da_alpha.pda_amount:,.0f} sent to finance team.'),
            (11, 'PDA approved',
             f'PDA approved — agent authorised to purchase up to EUR {da_alpha.pda_amount:,.0f}. '
             'Email sent to agent.', da_alpha.agent_id),
            (10, 'Execution started',
             'Execution started — agent authorised to purchase spare parts within approved budget.'),
        ]
        if alpha_po:
            alpha_timeline.append((
                8, 'linked to disbursement',
                f'Purchase order {alpha_po.name} linked to disbursement account.',
            ))
        alpha_timeline.append((
            3, 'FDA submitted',
            f'FDA submitted for 3-way match. Finance notified by email. '
            f'PDA EUR {da_alpha.pda_amount:,.0f} → FDA EUR {da_alpha.fda_amount:,.0f} '
            f'({da_alpha.variance_percent:.1f}% variance).',
        ))
        _post_timeline(env, da_alpha, alpha_timeline)

    da_beta = refs['da_beta_mumbai']
    if da_beta:
        beta_timeline = [
            (7, 'PDA submitted',
             f'PDA submitted for review — budget EUR {da_beta.pda_amount:,.0f} sent to finance team.'),
            (6, 'PDA approved',
             f'PDA approved — spending authority released for EUR {da_beta.pda_amount:,.0f}. '
             'Agent Hong Kong Maritime Services notified by email.', da_beta.agent_id),
            (5, 'Execution started',
             'Execution started — agent actively purchasing spare parts for Beta @ Hong Kong.'),
        ]
        if pos.get('beta'):
            beta_timeline.append((
                4, 'linked to disbursement',
                f'Purchase order {pos["beta"].name} confirmed and linked to disbursement account.',
            ))
        _post_timeline(env, da_beta, beta_timeline)

    da_gamma = refs['da_gamma_piraeus']
    if da_gamma:
        _post_timeline(env, da_gamma, [(
            2, 'PDA submitted',
            f'PDA submitted — finance team notified by email for Gamma / Piraeus. '
            f'Budget EUR {da_gamma.pda_amount:,.0f} awaiting approval.',
        )])

    da_delta = refs['da_delta_singapore']
    if da_delta:
        delta_timeline = [
            (20, 'PDA submitted',
             f'PDA submitted for review — budget EUR {da_delta.pda_amount:,.0f} sent to finance team.'),
            (19, 'PDA approved',
             f'PDA approved — spending authority EUR {da_delta.pda_amount:,.0f}. '
             'Agent Singapore Maritime Agency notified by email.', da_delta.agent_id),
            (18, 'Execution started',
             'Execution started — agent procuring turbo bearing kit in Singapore.'),
        ]
        if pos.get('delta'):
            delta_timeline.append((
                16, 'linked to disbursement',
                f'Purchase order {pos["delta"].name} linked to disbursement account.',
            ))
        delta_timeline.extend([
            (10, 'FDA submitted',
             f'FDA submitted — actual costs EUR {da_delta.fda_amount:,.0f}. '
             f'Variance vs PDA: {da_delta.variance_percent:.1f}%.'),
            (8, 'Payment approved',
             'Disbursement account payment approved. Agent notified by email.', da_delta.agent_id),
        ])
        _post_timeline(env, da_delta, delta_timeline)

    da_epsilon = refs['da_epsilon_piraeus']
    if da_epsilon:
        epsilon_timeline = [
            (35, 'PDA submitted',
             f'PDA submitted for review — budget EUR {da_epsilon.pda_amount:,.0f} sent to finance team.'),
            (34, 'PDA approved',
             f'PDA approved — spending authority EUR {da_epsilon.pda_amount:,.0f}. '
             'Agent Piraeus Ship Agency notified by email.', da_epsilon.agent_id),
            (33, 'Execution started',
             'Execution started — agent procuring ballast pump parts in Piraeus.'),
        ]
        if pos.get('epsilon'):
            epsilon_timeline.append((
                31, 'linked to disbursement',
                f'Purchase order {pos["epsilon"].name} linked to disbursement account.',
            ))
        epsilon_timeline.extend([
            (30, 'FDA submitted',
             f'FDA submitted — actual costs EUR {da_epsilon.fda_amount:,.0f}. '
             f'Variance vs PDA: {da_epsilon.variance_percent:.1f}%.'),
            (28, '3-way match complete',
             '3-way match complete — PDA, PO, and vendor bills reconciled. Ready for payment.'),
        ])
        _post_timeline(env, da_epsilon, epsilon_timeline)

    # --- Purchase orders ---
    po_alpha = pos.get('alpha')
    if po_alpha:
        _post_if_missing(env, po_alpha, 'Purchase confirmed',
            'Purchase confirmed for Main engine pump seal failure and '
            'Scheduled lube oil filter change. '
            'Superintendent, finance, and agent notified by email.', agent_hong_kong)
        _post_if_missing(env, alpha, 'Agent purchased spares',
            f'Alert: Agent purchased spares on {po_alpha.name} covering 2 maintenance jobs.')

    po_beta = pos.get('beta')
    if po_beta:
        _post_if_missing(env, po_beta, 'Purchase confirmed',
            f'Purchase order confirmed for Cargo valve actuator repair. '
            f'Total EUR {po_beta.amount_total:,.0f}. '
            'Superintendent, finance, and agent notified by email.', agent_hong_kong)
        _post_if_missing(env, beta, 'Agent purchased spares',
            f'Agent confirmed purchase {po_beta.name} for cargo valve repair.')

    for po in env['purchase.order'].search([
        ('port_call_id', '=', alpha.id), ('state', '=', 'sent'),
    ]):
        _post_if_missing(env, po, 'RFQ sent',
            f'RFQ sent to {po.partner_id.name} for pump seal kit — awaiting vendor quote.')

    draft_filter = env['purchase.order'].search([
        ('port_call_id', '=', alpha.id), ('state', '=', 'draft'),
    ], limit=1)
    if draft_filter:
        _post_if_missing(env, draft_filter, 'Draft RFQ',
            'Draft RFQ prepared for oil filter change — agent comparing chandler prices.')

    po_delta = pos.get('delta')
    if po_delta:
        _post_if_missing(env, po_delta, 'Purchase confirmed',
            f'Purchase confirmed for turbo bearing replacement. '
            f'Total EUR {po_delta.amount_total:,.0f}. Parts received onboard.', agent_singapore)

    po_epsilon = pos.get('epsilon')
    if po_epsilon:
        _post_if_missing(env, po_epsilon, 'Purchase confirmed',
            f'Purchase confirmed for ballast pump impeller renewal. '
            f'Total EUR {po_epsilon.amount_total:,.0f}. Parts received onboard.', agent_piraeus)


def _post_demo_email_notifications(env, refs):
    """Backfill email notifications for demo records (multi-team workflow)."""
    alpha = refs['port_call_alpha_mumbai']
    agent_hong_kong = env.ref('maritime_management.partner_agent_mumbai', raise_if_not_found=False)

    if alpha and agent_hong_kong:
        alpha._maritime_send_template(
            'maritime_management.mail_template_port_call_activated',
            partners=agent_hong_kong,
        )

    for mr in (refs['mr_alpha_pump_seal'], refs['mr_alpha_filter']):
        if mr and mr.port_call_id.agent_id:
            mr._maritime_send_template(
                'maritime_management.mail_template_mr_assigned_agent',
                partners=mr.port_call_id.agent_id,
            )

    da_alpha = refs['da_alpha_mumbai']
    if da_alpha and da_alpha.agent_id:
        da_alpha._maritime_send_template(
            'maritime_management.mail_template_pda_approved_agent',
            partners=da_alpha.agent_id,
        )
        finance_group = env.ref('maritime_management.group_maritime_finance', raise_if_not_found=False)
        if finance_group and finance_group.user_ids:
            da_alpha._maritime_send_template(
                'maritime_management.mail_template_fda_submitted_finance',
                users=finance_group.user_ids,
            )

    da_gamma = refs['da_gamma_piraeus']
    if da_gamma:
        finance_group = env.ref('maritime_management.group_maritime_finance', raise_if_not_found=False)
        if finance_group and finance_group.user_ids:
            da_gamma._maritime_send_template(
                'maritime_management.mail_template_pda_submitted_finance',
                users=finance_group.user_ids,
            )

    superintendent_group = env.ref(
        'maritime_management.group_maritime_superintendent',
        raise_if_not_found=False,
    )
    if refs['mr_gamma_stores'] and superintendent_group and superintendent_group.user_ids:
        refs['mr_gamma_stores']._maritime_send_template(
            'maritime_management.mail_template_mr_submitted_superintendent',
            users=superintendent_group.user_ids,
        )

    po_alpha = env['purchase.order'].search([
        ('port_call_id', '=', alpha.id), ('state', 'in', ('purchase', 'done')),
    ], limit=1, order='id')
    if po_alpha:
        if superintendent_group and superintendent_group.user_ids:
            po_alpha._maritime_send_template(
                'maritime_management.mail_template_po_confirmed',
                users=superintendent_group.user_ids,
            )
        finance_group = env.ref('maritime_management.group_maritime_finance', raise_if_not_found=False)
        if finance_group and finance_group.user_ids:
            po_alpha._maritime_send_template(
                'maritime_management.mail_template_po_confirmed',
                users=finance_group.user_ids,
            )
        if po_alpha.port_call_id.agent_id:
            po_alpha._maritime_send_template(
                'maritime_management.mail_template_po_confirmed_agent',
                partners=po_alpha.port_call_id.agent_id,
            )
