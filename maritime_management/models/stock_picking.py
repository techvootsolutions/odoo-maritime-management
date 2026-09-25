from odoo import fields, models


class StockPicking(models.Model):
    """
    Inherit stock.picking to link stock transfers with maintenance requests.
    """
    _inherit = 'stock.picking'

    maintenance_request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        index=True,
        copy=False,
    )


class StockMove(models.Model):
    """
    Inherit stock.move to link stock move lines with maintenance requests.
    """
    _inherit = 'stock.move'

    maintenance_request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        index=True,
        copy=False,
    )
