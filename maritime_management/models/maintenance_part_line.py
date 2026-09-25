from odoo import api, fields, models


class MaintenancePartLine(models.Model):
    """
    Spare part requisition line linked to a Maintenance Request, including catalog
    product mapping, requested quantities, and onboard vessel stock tracking.
    """
    _name = 'maintenance.part.line'
    _description = 'Maintenance Request Spare Part Line'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'maintenance.request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        domain="[('purchase_ok', '=', True)]",
        help='Stockable product consumed from vessel stores.',
    )
    name = fields.Char(string='Component / Part', required=True)
    part_number = fields.Char(string='Part Number')
    maker_ref = fields.Char(string='Maker Reference')
    quantity = fields.Float(default=1.0, digits='Product Unit')
    uom_name = fields.Char(
        string='UoM',
        default='PCE',
        help='Unit of Measure (e.g. PCE = pieces, SET = set, KG = kilogram).',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit',
        compute='_compute_product_uom_id',
        store=True,
        readonly=False,
        precompute=True,
    )
    criticality = fields.Selection(
        selection=[
            ('vital', 'VITAL'),
            ('essential', 'ESSENTIAL'),
            ('desirable', 'DESIRABLE'),
        ],
        default='essential',
        help='VITAL = must have before sailing; ESSENTIAL = needed soon; DESIRABLE = optional.',
    )
    company_id = fields.Many2one(
        related='request_id.company_id',
        store=True,
    )
    qty_available = fields.Float(
        string='Available',
        compute='_compute_stock_quantities',
        digits='Product Unit',
    )
    qty_consumed = fields.Float(
        string='Consumed',
        digits='Product Unit',
        readonly=True,
        copy=False,
    )
    qty_remaining = fields.Float(
        string='Remaining',
        compute='_compute_qty_remaining',
        digits='Product Unit',
    )

    @api.depends('product_id', 'product_id.uom_id')
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id or self.env.ref(
                'uom.product_uom_unit', raise_if_not_found=False,
            )

    @api.depends('quantity', 'qty_consumed')
    def _compute_qty_remaining(self):
        for line in self:
            line.qty_remaining = max(line.quantity - line.qty_consumed, 0.0)

    @api.depends(
        'product_id',
        'request_id.equipment_id.stock_location_id',
        'request_id.port_call_id.vessel_id.stock_location_id',
    )
    def _compute_stock_quantities(self):
        for line in self:
            if not line.product_id:
                line.qty_available = 0.0
                continue
            location = line.request_id._get_vessel_stock_location()
            if not location:
                line.qty_available = 0.0
                continue
            product = line.product_id.with_context(location=location.id)
            line.qty_available = product.free_qty

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        self.name = self.product_id.display_name
        if self.product_id.default_code:
            self.part_number = self.product_id.default_code
        self.product_uom_id = self.product_id.uom_id
