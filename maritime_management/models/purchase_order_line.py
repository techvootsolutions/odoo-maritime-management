from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    """
    Inherit purchase.order.line to link lines with maintenance requests, vessels, and port calls.
    """
    _inherit = 'purchase.order.line'

    maintenance_request_id = fields.Many2one(
        'maintenance.request',
        string='MR',
        index=True,
        check_company=True,
        help='Maintenance Request (MR) that this purchase line fulfils.',
    )
    vessel_id = fields.Many2one(
        'maintenance.equipment',
        string='Vessel',
        domain="[('is_vessel', '=', True)]",
        compute='_compute_vessel_id',
        store=True,
        readonly=False,
        check_company=True,
    )
    port_call_id = fields.Many2one(
        'port.call',
        related='order_id.port_call_id',
        store=True,
        readonly=True,
    )

    @api.depends('maintenance_request_id.equipment_id', 'order_id.port_call_id.vessel_id')
    def _compute_vessel_id(self):
        """
        Compute assigned vessel from linked MR or parent PO's port call.
        """
        for line in self:
            if line.maintenance_request_id and line.maintenance_request_id.equipment_id:
                line.vessel_id = line.maintenance_request_id.equipment_id
            elif line.order_id.port_call_id:
                line.vessel_id = line.order_id.port_call_id.vessel_id
            else:
                line.vessel_id = False

    @api.onchange('maintenance_request_id')
    def _onchange_maintenance_request_id(self):
        """
        Auto-fill description and port call from selected maintenance request.
        """
        if self.maintenance_request_id:
            self.name = self.maintenance_request_id.name
            if self.maintenance_request_id.port_call_id:
                self.order_id.port_call_id = self.maintenance_request_id.port_call_id
