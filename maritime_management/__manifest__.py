{
    'name': 'Maritime Management',
    'version': '19.0.1.0.0',
    'category': 'Industries/Maritime',
    'summary': 'Ship management: vessels, port calls, PDA/FDA disbursements, '
               'spare-part procurement, vessel stores and control center dashboard',
    'description': """
Maritime Management
===================
End-to-end, port-call-centric ship management for Odoo 19:

- Fleet master data: vessels, onboard machinery and world port catalog
- Port agent / ship chandler partner roles with automatic user role sync
- Port calls: vessel + port + ETA/ETD + agent, Draft → Planned → Active → Departed → Closed
- Proforma (PDA) and Final (FDA) disbursement accounts with variance tracking and PDF report
- Maintenance requests (MR) with shore approval, criticality and spare-part lists
- MR ↔ purchase order traceability and PDA budget gate before PO confirmation
- Vessel stores stock locations, PO receipts routed onboard, MR component consumption
- Role-aware Control Center dashboard for superintendents and finance
    """,
    'author': 'Techvoot Solutions',
    'website': 'https://www.techvoot.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'contacts',
        'maintenance',
        'account',
        'purchase',
        'stock',
        'purchase_stock',
    ],
    'data': [
        'security/maritime_security.xml',
        'security/ir.model.access.csv',
        'data/maritime_port_data.xml',
        'data/ir_sequence_data.xml',
        'data/maintenance_stage_data.xml',
        'data/mail_template_data.xml',
        'views/maritime_port_views.xml',
        'views/res_partner_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/port_call_views.xml',
        'views/disbursement_views.xml',
        'views/maintenance_request_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/control_center_views.xml',
        'views/maritime_menus.xml',
        'report/disbursement_report.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
        'demo/demo_users.xml',
        'demo/demo_partners.xml',
        'demo/demo_vessel_master.xml',
        'demo/demo_fleet.xml',
        'demo/demo_products.xml',
        'demo/demo_port_calls.xml',
        'demo/demo_maintenance.xml',
        'demo/demo_dashboard_maintenance.xml',
        'demo/demo_dashboard_port_calls.xml',
        'demo/demo_disbursement.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'maritime_management/static/src/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
    'images': ['static/description/banner.gif']
}
