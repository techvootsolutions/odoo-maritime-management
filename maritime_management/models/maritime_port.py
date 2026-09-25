from odoo import fields, models
from odoo.addons.base.models.res_partner import _tz_get


class MaritimePort(models.Model):
    """
    Sea ports worldwide where vessel calls and cargo/bunkering operations take place.
    """
    _name = 'maritime.port'
    _description = 'Maritime Port'
    _order = 'country_id, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(string='Port Code', help='UN/LOCODE or internal code')
    country_id = fields.Many2one('res.country', required=True)
    city = fields.Char()
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    timezone = fields.Selection(
        selection=_tz_get,
        default=lambda self: self.env.user.tz or 'UTC',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )

    _port_code_company_uniq = models.Constraint(
        'unique(code, company_id)',
        'Port code must be unique per company.',
    )
