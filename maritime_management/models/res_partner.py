from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    maritime_role = fields.Selection(
        selection=[
            ('none', 'Not Maritime'),
            ('port_agent', 'Port Agent'),
            ('ship_chandler', 'Ship Chandler'),
            ('stevedore', 'Stevedore / Terminal Operator'),
            ('bunker_supplier', 'Bunker Supplier'),
            ('surveyor', 'Marine Surveyor'),
            ('other', 'Other Maritime Vendor'),
        ],
        string='Maritime Role',
        default='none',
        help='Categorize partner for maritime workflows e.g. Port Agent for disbursement accounts.',
    )
    maritime_port_ids = fields.Many2many(
        'maritime.port',
        'res_partner_maritime_port_rel',
        'partner_id',
        'port_id',
        string='Covered Ports',
        help='Ports where this agent or chandler operates.',
    )
    is_port_agent = fields.Boolean(
        compute='_compute_maritime_flags',
        store=True,
    )
    is_ship_chandler = fields.Boolean(
        compute='_compute_maritime_flags',
        store=True,
    )

    @api.depends('maritime_role')
    def _compute_maritime_flags(self):
        for partner in self:
            partner.is_port_agent = (partner.maritime_role == 'port_agent')
            partner.is_ship_chandler = (partner.maritime_role == 'ship_chandler')
