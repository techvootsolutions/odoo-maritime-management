from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PortCall(models.Model):
    """
    Core port call model managing vessel port visits, lifecycle states,
    disbursement accounts, procurement requests, and financial metrics.
    """
    _name = 'port.call'
    _description = 'Port Call'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'maritime.notification.mixin']
    _order = 'eta desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    vessel_id = fields.Many2one(
        'maintenance.equipment',
        string='Vessel',
        required=True,
        domain="[('is_vessel', '=', True)]",
        check_company=True,
        tracking=True,
        index=True,
    )
    port_id = fields.Many2one(
        'maritime.port',
        string='Port',
        required=True,
        tracking=True,
        index=True,
    )
    agent_id = fields.Many2one(
        'res.partner',
        string='Port Agent',
        domain="[('maritime_role', '=', 'port_agent')]",
        tracking=True,
        check_company=True,
    )
    eta = fields.Datetime(
        string='ETA',
        help='Estimated Time of Arrival — when the vessel is expected to reach the port.',
        tracking=True,
    )
    etd = fields.Datetime(
        string='ETD',
        help='Estimated Time of Departure — when the vessel is expected to leave the port.',
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('planned', 'Planned'),
            ('active', 'Active'),
            ('departed', 'Departed'),
            ('closed', 'Closed'),
        ],
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
    )
    note = fields.Html()

    # Disbursement relations & financial fields
    disbursement_ids = fields.One2many(
        'port.disbursement.account',
        'port_call_id',
        string='Disbursement Accounts',
    )
    disbursement_count = fields.Integer(
        compute='_compute_disbursement_count',
        string='DAs',
        help='Number of Disbursement Accounts (DA) linked to this port call.',
    )
    pda_amount = fields.Monetary(
        string='Approved PDA',
        compute='_compute_disbursement_financials',
        currency_field='currency_id',
        help='Proforma Disbursement Account — approved estimated port costs for this call.',
    )
    fda_amount = fields.Monetary(
        string='FDA Total',
        compute='_compute_disbursement_financials',
        currency_field='currency_id',
        help='Final Disbursement Account — total actual port costs submitted after departure.',
    )
    da_primary_state = fields.Selection(
        selection=[
            ('none', 'No DA'),
            ('draft', 'Estimate Draft'),
            ('pda_submitted', 'Awaiting Budget Approval'),
            ('pda_approved', 'Budget Approved'),
            ('executing', 'Agent Purchasing'),
            ('fda_submitted', 'Final Bill to Review'),
            ('matched', 'Matched'),
            ('paid', 'Paid'),
        ],
        string='Port Expenses Status',
        compute='_compute_da_primary_state',
        help=(
            'Disbursement Account (DA) status. '
            'PDA = Proforma Disbursement Account (estimate). '
            'FDA = Final Disbursement Account (actual costs).'
        ),
    )
    demo_highlight = fields.Char(
        string='Demo Highlight',
        compute='_compute_demo_highlight',
    )

    # Procurement relations & stats
    maintenance_request_ids = fields.One2many(
        'maintenance.request',
        'port_call_id',
        string='Maintenance Requests',
    )
    maintenance_request_count = fields.Integer(
        compute='_compute_procurement_counts',
        string='MRs',
        help='Total Maintenance Requests (MR) linked to this port call.',
    )
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'port_call_id',
        string='Purchase Orders',
    )
    purchase_order_count = fields.Integer(
        compute='_compute_procurement_counts',
        string='POs',
        help='Total Purchase Orders (PO) raised for this port call.',
    )
    vendor_bill_ids = fields.One2many(
        'account.move',
        'port_call_id',
        domain=[('move_type', '=', 'in_invoice')],
        string='Vendor Bills',
    )
    vendor_bill_count = fields.Integer(
        compute='_compute_procurement_counts',
        string='Bills',
        help='Total Vendor Bills linked to this port call.',
    )
    po_amount = fields.Monetary(
        string='PO Value',
        compute='_compute_procurement_counts',
        currency_field='currency_id',
        help='Purchase Order (PO) total value confirmed for this port call.',
    )
    open_mr_count = fields.Integer(
        string='Open MRs',
        compute='_compute_procurement_counts',
        help='Open Maintenance Requests (MR) — jobs not yet completed or cancelled.',
    )

    @api.constrains('vessel_id', 'port_id', 'state', 'eta', 'etd')
    def _check_unique_active_port_call(self):
        """
        Block duplicate Port Calls for the same vessel & port during overlapping dates.
        """
        for call in self.filtered(lambda c: c.state not in ('closed', 'cancelled')):
            domain = [
                ('id', '!=', call.id),
                ('vessel_id', '=', call.vessel_id.id),
                ('port_id', '=', call.port_id.id),
                ('state', 'not in', ('closed', 'cancelled')),
            ]
            if call.eta and call.etd:
                domain += [
                    ('eta', '<=', call.etd),
                    ('etd', '>=', call.eta),
                ]
            overlap = self.search(domain, limit=1)
            if overlap:
                raise ValidationError(_(
                    'A port call (%(ref)s) already exists for vessel %(vessel)s at port %(port)s '
                    'during this time period. Duplicate port calls for the same ship visit are not allowed.',
                    ref=overlap.name,
                    vessel=call.vessel_id.name,
                    port=call.port_id.name,
                ))

    @api.constrains('state', 'agent_id')
    def _check_agent_on_activate(self):
        """
        Block activation if Port Agent is not assigned.
        """
        for call in self:
            if call.state in ('active', 'departed', 'closed') and not call.agent_id:
                raise ValidationError(_(
                    'Cannot activate or operate Port Call %s: You must assign a Port Agent first.',
                    call.name,
                ))

    @api.depends('disbursement_ids')
    def _compute_disbursement_count(self):
        """
        Compute number of linked disbursement accounts.
        """
        for port_call in self:
            port_call.disbursement_count = len(port_call.disbursement_ids)

    @api.depends('disbursement_ids.pda_amount', 'disbursement_ids.fda_amount', 'disbursement_ids.state')
    def _compute_disbursement_financials(self):
        """
        Compute total approved PDA and submitted/paid FDA amounts for this port call.
        """
        for port_call in self:
            approved = port_call.disbursement_ids.filtered(
                lambda d: d.state in ('pda_approved', 'fda_submitted', 'matched', 'paid')
            )
            port_call.pda_amount = sum(approved.mapped('pda_amount'))
            submitted_fda = port_call.disbursement_ids.filtered(
                lambda d: d.state in ('fda_submitted', 'matched', 'paid')
            )
            port_call.fda_amount = sum(submitted_fda.mapped('fda_amount'))

    @api.depends(
        'maintenance_request_ids',
        'maintenance_request_ids.shore_state',
        'purchase_order_ids',
        'purchase_order_ids.state',
        'purchase_order_ids.amount_total',
        'vendor_bill_ids',
    )
    def _compute_procurement_counts(self):
        """
        Compute counts and total monetary value for MRs, POs, and Vendor Bills.
        """
        for port_call in self:
            # PO / bill figures stay readable for maritime users without Purchase/Accounting access
            port_call_sudo = port_call.sudo()
            port_call.maintenance_request_count = len(port_call.maintenance_request_ids)
            port_call.open_mr_count = len(
                port_call.maintenance_request_ids.filtered(
                    lambda mr: mr.shore_state not in ('done', 'cancelled')
                )
            )
            port_call.purchase_order_count = len(port_call_sudo.purchase_order_ids)
            port_call.vendor_bill_count = len(port_call_sudo.vendor_bill_ids)
            confirmed = port_call_sudo.purchase_order_ids.filtered(
                lambda po: po.state in ('purchase', 'done')
            )
            port_call.po_amount = sum(confirmed.mapped('amount_total'))

    @api.depends('disbursement_ids.state')
    def _compute_da_primary_state(self):
        """
        Compute primary disbursement account status across linked DAs.
        """
        priority = [
            'fda_submitted', 'pda_submitted', 'executing',
            'pda_approved', 'matched', 'paid', 'draft',
        ]
        for pc in self:
            states = pc.disbursement_ids.mapped('state')
            if not states:
                pc.da_primary_state = 'none'
                continue
            for state in priority:
                if state in states:
                    pc.da_primary_state = state
                    break
            else:
                pc.da_primary_state = states[0]

    @api.depends('state', 'open_mr_count', 'da_primary_state', 'vessel_id', 'port_id')
    def _compute_demo_highlight(self):
        """
        Compute summary badge string for control center views.
        """
        mapping = {
            'active': 'Live port call',
            'planned': 'Upcoming',
            'departed': 'Awaiting final bill',
            'closed': 'Completed reference',
        }
        for pc in self:
            parts = [mapping.get(pc.state, pc.state)]
            if pc.open_mr_count:
                parts.append(f'{pc.open_mr_count} open job(s)')
            if pc.da_primary_state == 'fda_submitted':
                parts.append('Finance action needed')
            elif pc.da_primary_state == 'pda_submitted':
                parts.append('Approve budget')
            elif pc.da_primary_state == 'executing':
                parts.append('Agent buying now')
            pc.demo_highlight = ' · '.join(parts)

    @api.model_create_multi
    def create(self, vals_list):
        """
        Assign sequence reference on creation.
        """
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('port.call') or _('New')
        return super().create(vals_list)

    def action_plan(self):
        """
        Set port call state to Planned.
        """
        self._check_required_fields()
        self.write({'state': 'planned'})

    def action_activate(self):
        """
        Activate port call, auto-create initial disbursement account if missing, and send notification email.
        """
        self._check_required_fields()
        if not self.agent_id:
            raise UserError(_('Cannot activate Port Call %s: You must assign a Port Agent first.', self.name))
        self.write({'state': 'active'})
        for port_call in self:
            body = _(
                'Port call %(pc)s activated for %(vessel)s at %(port)s. '
                'Agent %(agent)s notified by email.',
                pc=port_call.name,
                vessel=port_call.vessel_id.name,
                port=port_call.port_id.name,
                agent=port_call.agent_id.name,
            )
            port_call._maritime_message_post(body, partner=port_call.agent_id)
            port_call._maritime_notify_partner(
                'maritime_management.mail_template_port_call_activated',
                port_call.agent_id,
            )
        for call in self:
            if not call.disbursement_ids:
                self.env['port.disbursement.account'].create({
                    'port_call_id': call.id,
                    'agent_id': call.agent_id.id if call.agent_id else False,
                })

    def action_depart(self):
        """
        Set port call state to Departed.
        """
        self.write({'state': 'departed'})

    def action_close(self):
        """
        Close port call after ensuring all MRs are closed and all DAs are settled/paid.
        """
        open_mrs = self.maintenance_request_ids.filtered(
            lambda mr: mr.shore_state not in ('done', 'cancelled')
        )
        if open_mrs:
            raise UserError(
                _('Close all maintenance requests before closing the port call.')
            )
        for call in self:
            unpaid_das = call.disbursement_ids.filtered(lambda d: d.state not in ('paid', 'cancelled'))
            if unpaid_das:
                raise UserError(
                    self.env._(
                        'Cannot close Port Call %(pc)s: There are %(count)d unpaid/unsettled Disbursement Account(s) (%(das)s). '
                        'Please settle and mark all disbursement accounts as Paid before closing.',
                        pc=call.name,
                        count=len(unpaid_das),
                        das=', '.join(unpaid_das.mapped('name')),
                    )
                )
        self.write({'state': 'closed'})

    def _check_required_fields(self):
        """
        Verify required vessel and port fields before state transition.
        """
        for port_call in self:
            if not port_call.vessel_id or not port_call.port_id:
                raise UserError(_('Vessel and port are required.'))

    def action_view_disbursements(self):
        """
        Return action to view disbursement accounts linked to this port call.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Disbursement Accounts'),
            'res_model': 'port.disbursement.account',
            'view_mode': 'list,form',
            'domain': [('port_call_id', '=', self.id)],
            'context': {
                'default_port_call_id': self.id,
                'default_agent_id': self.agent_id.id,
            },
        }

    def action_create_purchase_order(self):
        """
        Create a pre-filled Purchase Order directly from the Port Call for the Port Agent.
        """
        self.ensure_one()
        if not self.agent_id:
            raise UserError(_('Please assign a Port Agent to this Port Call first.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Purchase Order'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'context': {
                'default_partner_id': self.agent_id.id,
                'default_port_call_id': self.id,
            },
        }

    def action_create_vendor_bill(self):
        """
        Create a pre-filled Vendor Bill directly from the Port Call for the Port Agent.
        """
        self.ensure_one()
        if not self.agent_id:
            raise UserError(_('Please assign a Port Agent to this Port Call first.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'context': {
                'default_move_type': 'in_invoice',
                'default_partner_id': self.agent_id.id,
                'default_port_call_id': self.id,
            },
        }

    def action_view_maintenance_requests(self):
        """
        Return action to view maintenance requests linked to this port call.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Maintenance Requests'),
            'res_model': 'maintenance.request',
            'view_mode': 'list,form,kanban',
            'domain': [('port_call_id', '=', self.id)],
            'context': {
                'default_port_call_id': self.id,
                'default_equipment_id': self.vessel_id.id,
            },
        }

    def action_view_purchase_orders(self):
        """
        Return action to view purchase orders linked to this port call.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('port_call_id', '=', self.id)],
            'context': {
                'default_port_call_id': self.id,
            },
        }

    def action_view_vendor_bills(self):
        """
        Return action to view vendor bills linked to this port call.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Vendor Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('port_call_id', '=', self.id), ('move_type', '=', 'in_invoice')],
            'context': {
                'default_port_call_id': self.id,
                'default_move_type': 'in_invoice',
            },
        }
