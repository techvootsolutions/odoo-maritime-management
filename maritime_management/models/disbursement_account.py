from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PortDisbursementAccount(models.Model):
    """
    Port Disbursement Account (DA) tracking estimated (PDA) and actual (FDA) port costs
    and facilitating 3-way financial reconciliation between POs, Vendor Bills, and DAs.
    """
    _name = 'port.disbursement.account'
    _description = 'Port Disbursement Account'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'maritime.notification.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(
        string='DA Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        help='Disbursement Account reference number for this port call.',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    port_call_id = fields.Many2one(
        'port.call',
        string='Port Call',
        required=True,
        ondelete='restrict',
        check_company=True,
        tracking=True,
        index=True,
    )
    vessel_id = fields.Many2one(
        'maintenance.equipment',
        related='port_call_id.vessel_id',
        store=True,
        readonly=True,
    )
    port_id = fields.Many2one(
        'maritime.port',
        related='port_call_id.port_id',
        store=True,
        readonly=True,
    )
    agent_id = fields.Many2one(
        'res.partner',
        string='Port Agent',
        domain="[('maritime_role', '=', 'port_agent')]",
        check_company=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('pda_submitted', 'PDA Submitted'),
            ('pda_approved', 'PDA Approved'),
            ('fda_submitted', 'FDA Submitted'),
            ('matched', 'Matched'),
            ('paid', 'Paid'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
        tracking=True,
        help=(
            'PDA = Proforma Disbursement Account (estimated port costs before spending). '
            'FDA = Final Disbursement Account (actual port costs after the vessel departs).'
        ),
    )
    line_ids = fields.One2many(
        'port.disbursement.line',
        'disbursement_id',
        string='Lines',
        copy=True,
    )
    pda_amount = fields.Monetary(
        string='PDA Total',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Proforma Disbursement Account total — estimated port costs approved before the agent purchases.',
    )
    fda_amount = fields.Monetary(
        string='FDA Total',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Final Disbursement Account total — actual port costs after the vessel has departed.',
    )
    variance_amount = fields.Monetary(
        string='Variance',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Difference between FDA (actual) and PDA (estimate). Positive means over budget.',
    )
    variance_percent = fields.Float(
        string='Variance %',
        compute='_compute_amounts',
        store=True,
        digits=(16, 2),
        help='Variance as a percentage of the PDA (Proforma Disbursement Account) estimate.',
    )
    purchase_order_ids = fields.Many2many(
        'purchase.order',
        'port_disbursement_purchase_rel',
        'disbursement_id',
        'purchase_id',
        string='Purchase Orders',
    )
    purchase_order_count = fields.Integer(
        compute='_compute_purchase_order_count',
        string='PO Count',
        help='Number of Purchase Orders linked to this Disbursement Account.',
    )
    bill_ids = fields.Many2many(
        'account.move',
        'port_disbursement_bill_rel',
        'disbursement_id',
        'move_id',
        string='Vendor Bills',
        domain="[('move_type', '=', 'in_invoice')]",
    )
    bill_count = fields.Integer(
        compute='_compute_bill_count',
        string='Bill Count',
        help='Number of Vendor Bills linked to this Disbursement Account.',
    )
    note = fields.Html()

    @api.depends('purchase_order_ids', 'port_call_id')
    def _compute_purchase_order_count(self):
        """
        Compute total purchase orders linked to this disbursement account or port call.
        """
        for da in self:
            # counters stay readable for maritime users without Purchase access
            if da.sudo().purchase_order_ids:
                da.purchase_order_count = len(da.sudo().purchase_order_ids)
            elif da.port_call_id:
                da.purchase_order_count = self.env['purchase.order'].sudo().search_count([('port_call_id', '=', da.port_call_id.id)])
            else:
                da.purchase_order_count = 0

    @api.depends('bill_ids', 'port_call_id')
    def _compute_bill_count(self):
        """
        Compute total vendor bills linked to this disbursement account or port call.
        """
        for da in self:
            # counters stay readable for maritime users without Accounting access
            if da.sudo().bill_ids:
                da.bill_count = len(da.sudo().bill_ids)
            elif da.port_call_id:
                da.bill_count = self.env['account.move'].sudo().search_count([
                    ('port_call_id', '=', da.port_call_id.id),
                    ('move_type', '=', 'in_invoice'),
                ])
            else:
                da.bill_count = 0

    def action_view_purchase_orders(self):
        """
        Open linked Purchase Orders.
        Directly opens the PO form view if only 1 order exists.
        """
        self.ensure_one()
        orders = self.purchase_order_ids
        if not orders and self.port_call_id:
            orders = self.env['purchase.order'].search([('port_call_id', '=', self.port_call_id.id)])
        if len(orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase Order'),
                'res_model': 'purchase.order',
                'res_id': orders.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', orders.ids)],
        }

    def action_view_vendor_bills(self):
        """
        Open linked Vendor Bills.
        Directly opens the Vendor Bill form view if only 1 bill exists.
        """
        self.ensure_one()
        bills = self.bill_ids
        if not bills and self.port_call_id:
            bills = self.env['account.move'].search([
                ('port_call_id', '=', self.port_call_id.id),
                ('move_type', '=', 'in_invoice'),
            ])
        if len(bills) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Vendor Bill'),
                'res_model': 'account.move',
                'res_id': bills.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', bills.ids)],
        }

    @api.depends('line_ids.amount', 'line_ids.line_type')
    def _compute_amounts(self):
        """
        Calculate total PDA, FDA, and Variance amounts.
        """
        for da in self:
            pda_lines = da.line_ids.filtered(lambda l: l.line_type == 'pda')
            fda_lines = da.line_ids.filtered(lambda l: l.line_type == 'fda')
            da.pda_amount = sum(pda_lines.mapped('amount'))
            da.fda_amount = sum(fda_lines.mapped('amount'))
            da.variance_amount = da.fda_amount - da.pda_amount
            if da.pda_amount:
                da.variance_percent = (da.variance_amount / da.pda_amount) * 100.0
            else:
                da.variance_percent = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        """
        Assign sequence code and sync document links on record creation.
        """
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'port.disbursement.account'
                ) or _('New')
        records = super().create(vals_list)
        for record in records:
            if not record.agent_id and record.port_call_id.agent_id:
                record.agent_id = record.port_call_id.agent_id
            record._sync_port_call_documents()
        return records

    def write(self, vals):
        """
        Update records and sync documents if port_call_id changes.
        """
        res = super().write(vals)
        if 'port_call_id' in vals:
            self._sync_port_call_documents()
        return res

    @api.onchange('port_call_id')
    def _onchange_port_call_id(self):
        """
        Auto-populate port agent and sync documents when port call is selected.
        """
        if self.port_call_id:
            self.agent_id = self.port_call_id.agent_id
            self._sync_port_call_documents()

    def action_sync_documents(self):
        """
        Manually trigger document sync for linked POs and Vendor Bills.
        """
        self._sync_port_call_documents()

    def _sync_port_call_documents(self):
        """
        Auto-link POs and Bills belonging to this Port Call and create DA line items.
        """
        for da in self:
            if not da.port_call_id:
                continue
            pos = self.env['purchase.order'].search([('port_call_id', '=', da.port_call_id.id)])
            bills = self.env['account.move'].search([
                ('port_call_id', '=', da.port_call_id.id),
                ('move_type', '=', 'in_invoice'),
            ])
            da.write({
                'purchase_order_ids': [(6, 0, pos.ids)],
                'bill_ids': [(6, 0, bills.ids)],
            })
            existing_po_ids = set(da.line_ids.mapped('purchase_order_id.id'))
            existing_bill_ids = set(da.line_ids.mapped('bill_id.id'))
            new_lines = []
            mrs = self.env['maintenance.request'].search([
                ('port_call_id', '=', da.port_call_id.id),
                ('shore_state', 'in', ('approved', 'delivered', 'done')),
            ])
            existing_line_names = set(da.line_ids.mapped('name'))
            for mr in mrs:
                for part in mr.part_line_ids:
                    prod_name = part.name or (part.product_id.display_name if part.product_id else 'Spare Part')
                    line_desc = f"{mr.name} - {prod_name}"
                    if line_desc not in existing_line_names:
                        unit_price = part.product_id.standard_price if part.product_id else 0.0
                        est_amount = unit_price * (part.quantity or 1.0)
                        new_lines.append((0, 0, {
                            'line_type': 'pda',
                            'name': line_desc,
                            'charge_category': 'spares',
                            'amount': est_amount,
                        }))
                        existing_line_names.add(line_desc)

            for po in pos:
                if po.id not in existing_po_ids:
                    new_lines.append((0, 0, {
                        'line_type': 'pda' if da.state in ('draft', 'pda_submitted') else 'fda',
                        'name': _('Purchase Order %s', po.name),
                        'charge_category': 'spares',
                        'purchase_order_id': po.id,
                        'amount': po.amount_total,
                    }))
            for bill in bills:
                if bill.id not in existing_bill_ids:
                    new_lines.append((0, 0, {
                        'line_type': 'fda',
                        'name': _('Vendor Bill %s', bill.name or bill.ref or 'Invoice'),
                        'charge_category': 'spares',
                        'bill_id': bill.id,
                        'amount': bill.amount_total,
                    }))
            if new_lines:
                da.write({'line_ids': new_lines})

    def action_submit_pda(self):
        """
        Submit Proforma Disbursement Account (PDA) for shore review.
        """
        for da in self:
            if not da.line_ids.filtered(lambda l: l.line_type == 'pda'):
                raise UserError(_('Add at least one PDA estimate line before submitting.'))
        self.write({'state': 'pda_submitted'})
        self._notify_finance(
            _('PDA submitted for review'),
            'maritime_management.mail_template_pda_submitted_finance',
        )

    def action_approve_pda(self):
        """
        Approve PDA budget, releasing spending authority to the port agent.
        """
        self.write({'state': 'pda_approved'})
        self._notify_agent(
            _('PDA approved — spending authority released'),
            'maritime_management.mail_template_pda_approved_agent',
        )

    def action_submit_fda(self):
        """
        Submit Final Disbursement Account (FDA) to finance for 3-way matching.
        """
        self._sync_port_call_documents()
        for da in self:
            fda_lines = da.line_ids.filtered(lambda l: l.line_type == 'fda')
            if not fda_lines:
                if da.bill_ids:
                    for bill in da.bill_ids:
                        da.write({
                            'line_ids': [(0, 0, {
                                'line_type': 'fda',
                                'name': _('Vendor Bill %s', bill.name or bill.ref or 'Invoice'),
                                'charge_category': 'spares',
                                'bill_id': bill.id,
                                'amount': bill.amount_total,
                            })]
                        })
                elif da.purchase_order_ids:
                    for po in da.purchase_order_ids:
                        da.write({
                            'line_ids': [(0, 0, {
                                'line_type': 'fda',
                                'name': _('Purchase Order %s', po.name),
                                'charge_category': 'spares',
                                'purchase_order_id': po.id,
                                'amount': po.amount_total,
                            })]
                        })
            if not da.line_ids.filtered(lambda l: l.line_type == 'fda'):
                raise UserError(_('Add FDA actual lines before submitting the final DA.'))
        self.write({'state': 'fda_submitted'})
        self._notify_finance(
            _('FDA submitted for 3-way match'),
            'maritime_management.mail_template_fda_submitted_finance',
        )

    def action_mark_matched(self):
        """
        Set state to Matched after 3-way financial reconciliation.
        """
        self.write({'state': 'matched'})

    def action_mark_paid(self):
        """
        Set state to Paid upon invoice settlement.
        """
        self.write({'state': 'paid'})
        self._notify_agent(
            _('Disbursement account payment approved'),
            'maritime_management.mail_template_da_paid_agent',
        )

    def action_create_purchase_order(self):
        """
        Create a pre-filled Purchase Order for the Port Call once PDA budget is approved by Finance.
        Preserves exact requested spare part line quantities.
        """
        self.ensure_one()
        partner_id = self.agent_id.id if self.agent_id else (self.port_call_id.agent_id.id if self.port_call_id and self.port_call_id.agent_id else False)

        mrs = self.env['maintenance.request'].search([
            ('port_call_id', '=', self.port_call_id.id),
            ('shore_state', 'in', ('approved', 'delivered', 'done')),
        ])
        default_product = self.env['product.product'].search([('type', '=', 'consu')], limit=1)
        if not default_product:
            default_product = self.env['product.product'].search([], limit=1)

        po_lines = []
        seen_part_ids = set()

        for mr in mrs:
            if mr.purchase_line_ids:
                continue

            for part in mr.part_line_ids:
                if part.id in seen_part_ids:
                    continue
                seen_part_ids.add(part.id)

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
                    'date_planned': fields.Datetime.now(),
                    'maintenance_request_id': mr.id,
                    'vessel_id': self.vessel_id.id if self.vessel_id else False,
                }))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Purchase Order'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'context': {
                'default_partner_id': partner_id,
                'default_port_call_id': self.port_call_id.id if self.port_call_id else False,
                'default_partner_ref': f"DA Budget: {self.name}",
                'default_origin': f"{self.name} ({self.port_call_id.name})",
                'default_order_line': po_lines,
            },
        }

    def action_create_vendor_bill(self):
        """
        Create a pre-filled Vendor Bill directly from the Disbursement Account for the Port Agent.
        """
        self.ensure_one()
        partner_id = self.agent_id.id if self.agent_id else (self.port_call_id.agent_id.id if self.port_call_id and self.port_call_id.agent_id else False)
        currency = self.currency_id or self.company_id.currency_id or self.env.company.currency_id

        invoice_lines = []
        if self.purchase_order_ids:
            for po in self.purchase_order_ids:
                for line in po.order_line.filtered(lambda l: not l.display_type):
                    invoice_lines.append((0, 0, {
                        'product_id': line.product_id.id if line.product_id else False,
                        'name': line.name or (line.product_id.display_name if line.product_id else _('Port Service')),
                        'quantity': line.product_qty or 1.0,
                        'price_unit': line.price_unit or 0.0,
                        'product_uom_id': line.product_uom_id.id or line.product_id.uom_id.id,
                        'purchase_line_id': line.id,
                    }))
        if not invoice_lines and self.line_ids:
            for da_line in self.line_ids:
                if da_line.amount:
                    invoice_lines.append((0, 0, {
                        'name': da_line.name,
                        'quantity': 1.0,
                        'price_unit': da_line.amount,
                    }))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'context': {
                'default_move_type': 'in_invoice',
                'default_partner_id': partner_id,
                'default_currency_id': currency.id,
                'default_port_call_id': self.port_call_id.id if self.port_call_id else False,
                'default_ref': f"DA: {self.name}",
                'default_invoice_line_ids': invoice_lines,
            },
        }

    def action_cancel(self):
        """
        Cancel disbursement account.
        """
        self.write({'state': 'cancelled'})

    def _notify_finance(self, subject, template_xmlid):
        """
        Notify finance group users and schedule a todo activity.
        """
        finance_group = self.env.ref('maritime_management.group_maritime_finance', raise_if_not_found=False)
        for da in self:
            body = _(
                '%(subject)s for %(da)s (Port Call %(pc)s). PDA: %(pda).2f %(cur)s',
                subject=subject,
                da=da.name,
                pc=da.port_call_id.name,
                pda=da.pda_amount,
                cur=da.currency_id.name,
            )
            da.message_post(body=body, subtype_xmlid='mail.mt_note')
            da._maritime_notify_group(template_xmlid, 'maritime_management.group_maritime_finance')
            if finance_group and finance_group.user_ids:
                da.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=finance_group.user_ids[0].id,
                    summary=subject,
                )

    def _notify_agent(self, subject, template_xmlid):
        """
        Notify assigned port agent partner via email.
        """
        for da in self:
            body = _(
                '%(subject)s for %(da)s.',
                subject=subject,
                da=da.name,
            )
            da._maritime_notify_partner(template_xmlid, da.agent_id, body=body)


class PortDisbursementLine(models.Model):
    """
    Line items within a Disbursement Account distinguishing PDA estimates and FDA actuals.
    """
    _name = 'port.disbursement.line'
    _description = 'Port Disbursement Line'
    _order = 'line_type, sequence, id'

    disbursement_id = fields.Many2one(
        'port.disbursement.account',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    line_type = fields.Selection(
        selection=[
            ('pda', 'PDA Estimate'),
            ('fda', 'FDA Actual'),
        ],
        required=True,
        default='pda',
        help=(
            'PDA = Proforma Disbursement Account line (estimated cost). '
            'FDA = Final Disbursement Account line (actual cost).'
        ),
    )
    name = fields.Char(string='Description', required=True)
    charge_category = fields.Selection(
        selection=[
            ('spares', 'Spare Parts'),
            ('stores', 'Stores'),
            ('agency', 'Agency Fee'),
            ('port_dues', 'Port Dues'),
            ('other', 'Other'),
        ],
        default='spares',
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='PO',
        help='Purchase Order linked to this disbursement line.',
    )
    bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        domain="[('move_type', '=', 'in_invoice')]",
    )
    amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        related='disbursement_id.currency_id',
        store=True,
    )
    company_id = fields.Many2one(
        related='disbursement_id.company_id',
        store=True,
    )
