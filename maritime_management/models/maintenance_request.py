from odoo import _, api, fields, models
from odoo.exceptions import UserError

SHORE_STATE_STAGE_XMLIDS = {
    'draft': 'maritime_management.maritime_mr_stage_draft',
    'submitted': 'maritime_management.maritime_mr_stage_submitted',
    'approved': 'maritime_management.maritime_mr_stage_approved',
    'delivered': 'maritime_management.maritime_mr_stage_delivered',
    'done': 'maritime_management.maritime_mr_stage_done',
    'cancelled': 'maritime_management.maritime_mr_stage_cancelled',
}


class MaintenanceRequest(models.Model):
    """
    Inherit maintenance.request for maritime requisitions, shore approval workflow,
    spare part lists, procurement tracking, and onboard vessel stores consumption.
    """
    _name = 'maintenance.request'
    _inherit = ['maintenance.request', 'maritime.notification.mixin']

    equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='Vessel',
        domain="[('is_vessel', '=', True)]",
    )
    port_call_id = fields.Many2one(
        'port.call',
        string='Port Call',
        check_company=True,
        tracking=True,
        index=True,
        help='Port visit where spare parts will be delivered to the vessel.',
    )
    shore_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted to Shore'),
            ('approved', 'Approved'),
            ('delivered', 'Delivered Onboard'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        index=True,
        copy=False,
        group_expand='_read_group_shore_state_ids',
        help=(
            'Single pipeline status for this maintenance job: from vessel request '
            'through shore approval, agent procurement, and onboard delivery.'
        ),
    )
    is_maritime_job = fields.Boolean(
        string='Port Call Job',
        compute='_compute_is_maritime_job',
        store=True,
        default=True,
        help='True when this maintenance request is linked to a port call.',
    )
    criticality = fields.Selection(
        selection=[
            ('vital', 'VITAL'),
            ('essential', 'ESSENTIAL'),
            ('desirable', 'DESIRABLE'),
        ],
        default='essential',
        tracking=True,
        help=(
            'Spare part priority: VITAL (must have before sailing), '
            'ESSENTIAL (needed soon), DESIRABLE (nice to have).'
        ),
    )
    part_number = fields.Char(string='Primary Part Number')
    maker_ref = fields.Char(string='Maker Reference')
    required_by_date = fields.Date(
        string='Required By (Port ETA)',
        help=(
            'Date parts must arrive at port. Align with Port ETA '
            '(Estimated Time of Arrival) so the agent can deliver before departure.'
        ),
    )
    part_line_ids = fields.One2many(
        'maintenance.part.line',
        'request_id',
        string='Spare Parts List',
        copy=True,
    )
    purchase_line_ids = fields.One2many(
        'purchase.order.line',
        'maintenance_request_id',
        string='Purchase Lines',
        copy=False,
    )
    purchase_line_count = fields.Integer(
        compute='_compute_purchase_stats',
        store=True,
        string='PO Lines',
        help='Number of Purchase Order (PO) lines linked to this Maintenance Request (MR).',
    )
    purchase_order_count = fields.Integer(
        compute='_compute_purchase_stats',
        store=True,
        string='Purchase Orders',
        help='Number of Purchase Orders (PO) linked to this Maintenance Request (MR).',
    )
    procurement_status = fields.Selection(
        selection=[
            ('none', 'Not Ordered'),
            ('rfq', 'RFQ'),
            ('ordered', 'Ordered'),
            ('received', 'Received'),
            ('invoiced', 'Invoiced'),
        ],
        string='Procurement Status',
        compute='_compute_purchase_stats',
        store=True,
        copy=False,
        help='Purchase progress. RFQ = Request for Quotation sent to vendors.',
    )
    purchase_amount = fields.Monetary(
        compute='_compute_purchase_stats',
        store=True,
        currency_field='currency_id',
        copy=False,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
    )

    # Stock fields
    stock_location_id = fields.Many2one(
        'stock.location',
        string='Vessel Stores',
        compute='_compute_stock_location_id',
        store=True,
    )
    consumption_picking_ids = fields.One2many(
        'stock.picking',
        'maintenance_request_id',
        string='Consumption Transfers',
    )
    consumption_picking_count = fields.Integer(
        compute='_compute_consumption_picking_count',
    )
    stock_consumption_state = fields.Selection(
        selection=[
            ('none', 'No Products'),
            ('pending', 'Not Consumed'),
            ('partial', 'Partially Consumed'),
            ('done', 'Consumed'),
        ],
        string='Stock Consumption',
        compute='_compute_stock_consumption_state',
        store=True,
    )

    def copy(self, default=None):
        """
        Reset state to draft on record duplication.
        """
        default = dict(default or {})
        default.setdefault('shore_state', 'draft')
        default.setdefault('procurement_status', 'none')
        return super().copy(default)

    @api.depends('port_call_id')
    def _compute_is_maritime_job(self):
        """
        Compute whether this maintenance request is a maritime job.
        """
        for request in self:
            request.is_maritime_job = True

    @api.model
    def _read_group_shore_state_ids(self, states, domain):
        """
        Show all status columns in kanban, including empty ones.
        """
        return [key for key, _label in self._fields['shore_state'].selection]

    @api.depends(
        'purchase_line_ids.state',
        'purchase_line_ids.order_id',
        'purchase_line_ids.qty_received',
        'purchase_line_ids.qty_invoiced',
        'purchase_line_ids.price_subtotal',
        'purchase_line_ids.order_id.state',
    )
    def _compute_purchase_stats(self):
        """
        Compute PO line count, order count, total value, and procurement status.
        """
        for request in self:
            lines = request.purchase_line_ids.filtered(lambda l: not l.display_type)
            request.purchase_line_count = len(lines)
            orders = lines.mapped('order_id')
            request.purchase_order_count = len(orders)
            request.purchase_amount = sum(lines.mapped('price_subtotal'))
            if not lines:
                request.procurement_status = 'none'
                continue
            states = set(lines.mapped('order_id.state'))
            if lines and all(line.qty_invoiced >= line.product_qty for line in lines):
                request.procurement_status = 'invoiced'
            elif lines and all(line.qty_received >= line.product_qty for line in lines):
                request.procurement_status = 'received'
            elif 'purchase' in states or 'done' in states:
                request.procurement_status = 'ordered'
            elif 'sent' in states or 'to approve' in states:
                request.procurement_status = 'rfq'
            else:
                request.procurement_status = 'none'

    @api.onchange('equipment_id')
    def _onchange_equipment_id_set_port_call(self):
        """
        Automatically set active Port Call when vessel is selected.
        """
        if self.equipment_id and not self.port_call_id:
            active_pc = self.env['port.call'].search([
                ('vessel_id', '=', self.equipment_id.id),
                ('state', 'in', ('active', 'planned')),
            ], limit=1)
            if active_pc:
                self.port_call_id = active_pc

    @api.depends('equipment_id.stock_location_id', 'port_call_id.vessel_id.stock_location_id')
    def _compute_stock_location_id(self):
        """
        Compute vessel stores stock location.
        """
        for request in self:
            request.stock_location_id = request._get_vessel_stock_location()

    @api.depends('consumption_picking_ids')
    def _compute_consumption_picking_count(self):
        """
        Compute count of stock consumption transfers.
        """
        for request in self:
            # counter stays readable for maritime users without Inventory access
            request.consumption_picking_count = len(request.sudo().consumption_picking_ids)

    @api.depends('part_line_ids.product_id', 'part_line_ids.quantity', 'part_line_ids.qty_consumed')
    def _compute_stock_consumption_state(self):
        """
        Compute stock consumption progress for this MR.
        """
        for request in self:
            lines = request.part_line_ids.filtered('product_id')
            if not lines:
                request.stock_consumption_state = 'none'
                continue
            remaining = sum(lines.mapped('qty_remaining'))
            consumed = sum(lines.mapped('qty_consumed'))
            if remaining <= 0 and consumed > 0:
                request.stock_consumption_state = 'done'
            elif consumed > 0:
                request.stock_consumption_state = 'partial'
            else:
                request.stock_consumption_state = 'pending'

    def _get_vessel_equipment(self):
        """
        Helper method to get the vessel equipment record for this request.
        """
        self.ensure_one()
        if self.equipment_id and self.equipment_id.is_vessel:
            return self.equipment_id
        if self.port_call_id and self.port_call_id.vessel_id:
            return self.port_call_id.vessel_id
        return self.equipment_id

    def _get_vessel_stock_location(self):
        """
        Helper method to get or ensure the vessel stock location.
        """
        self.ensure_one()
        vessel = self._get_vessel_equipment()
        if vessel:
            if not vessel.stock_location_id and vessel.is_vessel:
                vessel._maritime_ensure_stock_location()
            return vessel.stock_location_id
        return False

    def _line_qty_to_consume(self, line):
        """
        Calculate quantity needed for consumption.
        """
        if line.id:
            return line.qty_remaining
        return max(line.quantity - (line.qty_consumed or 0.0), 0.0)

    def _get_consumption_lines(self):
        """
        Return part lines still to consume, falling back to PO products.
        """
        self.ensure_one()
        lines = self.part_line_ids.filtered(
            lambda line: line.product_id and line.qty_remaining > 0,
        )
        if lines:
            return lines

        fallback_lines = self.env['maintenance.part.line']
        for pol in self.purchase_line_ids.filtered(
            lambda line: not line.display_type and line.product_id.is_storable,
        ):
            qty = pol.product_uom_id._compute_quantity(
                pol.qty_received or pol.product_qty,
                pol.product_id.uom_id,
            )
            if qty <= 0:
                continue
            fallback_lines |= self.env['maintenance.part.line'].new({
                'request_id': self.id,
                'name': pol.product_id.display_name,
                'product_id': pol.product_id,
                'product_uom_id': pol.product_uom_id,
                'quantity': qty,
                'qty_consumed': 0.0,
            })
        return fallback_lines

    def _sync_stage_from_shore_state(self):
        """
        Align the standard maintenance stage with the maritime shore status.
        """
        for request in self:
            xmlid = SHORE_STATE_STAGE_XMLIDS.get(request.shore_state)
            stage = self.env.ref(xmlid, raise_if_not_found=False) if xmlid else False
            if stage and request.stage_id != stage:
                request.stage_id = stage

    def action_submit_shore(self):
        """
        Submit requisition from ship to shore office for approval.
        """
        self.write({'shore_state': 'submitted'})
        for request in self:
            body = _(
                'Maintenance request %(mr)s submitted from %(vessel)s for shore approval.',
                mr=request.name,
                vessel=request.equipment_id.name if request.equipment_id else 'Ship',
            )
            request._maritime_message_post(body)
            request._maritime_notify_group(
                'maritime_management.mail_template_mr_submitted_superintendent',
                'maritime_management.group_maritime_superintendent',
            )

    def action_approve_shore(self):
        """
        Approve requisition (Superintendent only) and sync DA lines.
        """
        self.write({'shore_state': 'approved'})
        for request in self:
            if request.port_call_id:
                for da in request.port_call_id.disbursement_ids:
                    if hasattr(da, '_sync_port_call_documents'):
                        da._sync_port_call_documents()

    def action_mark_delivered(self):
        """
        Mark spare parts delivered onboard ship.
        """
        self.write({'shore_state': 'delivered'})

    def action_shore_done(self):
        """
        Close maintenance request upon job completion onboard.
        """
        self.write({'shore_state': 'done'})

    def action_shore_cancel(self):
        """
        Cancel maintenance request.
        """
        self.write({'shore_state': 'cancelled'})

    def action_check_availability(self):
        """
        Check vessel stock and consume components for this MR.
        """
        for request in self:
            request._action_check_availability()
        return True

    def _action_check_availability(self):
        """
        Execute stock validation, picking creation, auto-assignment, validation, and chatter logging.
        """
        self.ensure_one()
        if not self.is_maritime_job:
            raise UserError(_('Stock consumption applies only to port-call maintenance jobs.'))

        location = self._get_vessel_stock_location()
        if not location:
            raise UserError(_(
                'No vessel stores location found for %(vessel)s.',
                vessel=self._get_vessel_equipment().name,
            ))

        lines = self._get_consumption_lines()
        if not lines:
            raise UserError(_(
                'Add spare part lines with products, or receive purchase order lines first.',
            ))

        shortages = []
        for line in lines:
            qty_needed = self._line_qty_to_consume(line)
            available = line.product_id.with_context(location=location.id).free_qty
            if available < qty_needed:
                shortages.append(_(
                    '%(part)s: need %(need).2f %(uom)s, only %(avail).2f available',
                    part=line.name,
                    need=qty_needed,
                    uom=line.product_uom_id.name,
                    avail=available,
                ))
        if shortages:
            raise UserError(_(
                'Insufficient stock in %(location)s:\n%(details)s',
                location=location.display_name,
                details='\n'.join(shortages),
            ))

        warehouse = location.warehouse_id or self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1,
        )
        if not warehouse:
            raise UserError(_('No warehouse configured for this company.'))

        picking_type = warehouse.out_type_id
        dest_location = picking_type.default_location_dest_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'maintenance_request_id': self.id,
            'company_id': self.company_id.id,
        })

        Move = self.env['stock.move']
        for line in lines:
            qty_needed = self._line_qty_to_consume(line)
            Move.create({
                'description_picking_manual': line.name,
                'product_id': line.product_id.id,
                'product_uom_qty': qty_needed,
                'product_uom': line.product_uom_id.id,
                'picking_id': picking.id,
                'location_id': location.id,
                'location_dest_id': dest_location.id,
                'maintenance_request_id': self.id,
                'company_id': self.company_id.id,
            })

        consumption_qty = {line: self._line_qty_to_consume(line) for line in lines}

        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.button_validate()

        for line in lines:
            if line.id:
                line.qty_consumed += consumption_qty[line]

        consumed_summary = ', '.join(
            f'{line.name} ({consumption_qty[line]:g} {line.product_uom_id.name})'
            for line in lines
        )
        body = _(
            'Components consumed from %(location)s: %(parts)s.',
            location=location.display_name,
            parts=consumed_summary,
        )
        self.message_post(body=body, subtype_xmlid='mail.mt_comment')
        return picking

    def action_view_consumption_pickings(self):
        """
        Return action to view stock consumption pickings.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consumption Transfers'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.consumption_picking_ids.ids)],
        }

    def action_create_purchase_order(self):
        """
        Create a pre-filled Purchase Order pre-populated with spare parts from this Maintenance Request.
        """
        self.ensure_one()
        po_lines = []
        default_product = self.env['product.product'].search([('type', '=', 'consu')], limit=1)
        if not default_product:
            default_product = self.env['product.product'].search([], limit=1)

        for part in self.part_line_ids:
            product = part.product_id
            if not product and part.name:
                product = self.env['product.product'].search([('name', '=ilike', part.name)], limit=1)
            if not product:
                product = default_product
            if not product:
                continue

            po_lines.append((0, 0, {
                'product_id': product.id,
                'name': part.name or product.display_name,
                'product_qty': part.quantity or 1.0,
                'product_uom_id': product.uom_id.id,
                'price_unit': product.standard_price or 0.0,
                'maintenance_request_id': self.id,
                'vessel_id': self.equipment_id.id if self.equipment_id else False,
            }))
        partner = self.port_call_id.agent_id if self.port_call_id and self.port_call_id.agent_id else False
        if not partner:
            partner = self.env['res.partner'].search([('maritime_role', '=', 'port_agent')], limit=1)

        origin_str = f"{self.name} ({self.port_call_id.name})" if self.port_call_id else self.name
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Purchase Order'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'context': {
                'default_partner_id': partner.id if partner else False,
                'default_partner_ref': self.name,
                'default_origin': origin_str,
                'default_port_call_id': self.port_call_id.id if self.port_call_id else False,
                'default_order_line': po_lines,
            },
        }

    def action_view_purchase_lines(self):
        """
        Return action to view linked PO lines.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order Lines'),
            'res_model': 'purchase.order.line',
            'view_mode': 'list',
            'domain': [('maintenance_request_id', '=', self.id)],
        }

    def action_view_purchase_orders(self):
        """
        Return action to view linked Purchase Orders.
        """
        self.ensure_one()
        orders = self.purchase_line_ids.order_id
        if len(orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase Order'),
                'res_model': 'purchase.order',
                'res_id': orders.id,
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', orders.ids)],
        }
