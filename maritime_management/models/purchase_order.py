from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    """
    Inherit purchase.order to link POs with port calls, validate PDA approval before confirmation,
    route delivery to vessel stock locations, and trigger notification workflows.
    """
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'maritime.notification.mixin']

    port_call_id = fields.Many2one(
        'port.call',
        string='Port Call',
        check_company=True,
        index=True,
        help='Port visit during which the port agent will procure and deliver these items.',
    )
    is_maritime_procurement = fields.Boolean(
        compute='_compute_is_maritime_procurement',
        store=True,
    )

    @api.depends('port_call_id', 'order_line.maintenance_request_id')
    def _compute_is_maritime_procurement(self):
        """
        Compute whether this purchase order is related to maritime procurement.
        """
        for order in self:
            order.is_maritime_procurement = bool(
                order.port_call_id
                or order.order_line.filtered('maintenance_request_id')
            )

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create purchase order records and sync related disbursement account documents.
        """
        orders = super().create(vals_list)
        for order in orders:
            if order.port_call_id:
                disbursements = self.env['port.disbursement.account'].search([('port_call_id', '=', order.port_call_id.id)])
                for da in disbursements:
                    da.write({'purchase_order_ids': [(4, order.id)]})
        return orders

    def write(self, vals):
        """
        Update purchase order records and sync related disbursement account documents if port call changed.
        """
        res = super().write(vals)
        if 'port_call_id' in vals:
            for order in self:
                if order.port_call_id:
                    disbursements = self.env['port.disbursement.account'].search([('port_call_id', '=', order.port_call_id.id)])
                    for da in disbursements:
                        da.write({'purchase_order_ids': [(4, order.id)]})
        return res

    def button_confirm(self):
        """
        Validate PDA approval, set line delivery dates, notify stakeholders, and update maintenance requests.
        """
        for order in self:
            if order.port_call_id:
                approved_da = order.port_call_id.disbursement_ids.filtered(
                    lambda d: d.state in ('pda_approved', 'fda_submitted', 'matched', 'paid')
                )
                if not approved_da:
                    raise UserError(
                        self.env._(
                            'Cannot confirm Purchase Order %(po)s for Port Call %(pc)s: '
                            'Finance has not approved the Proforma Disbursement Account (PDA) budget yet. '
                            'Please approve the Disbursement Account (PDA Approved) before confirming spending.',
                            po=order.name,
                            pc=order.port_call_id.name,
                        )
                    )
            for line in order.order_line:
                if not line.date_planned:
                    line.date_planned = order.date_order or fields.Datetime.now()

        res = super().button_confirm()
        self._maritime_notify_purchase_confirmed()
        self._maritime_update_maintenance_requests()
        return res

    def _maritime_notify_purchase_confirmed(self):
        """
        Send notification emails to superintendent, finance, and agent when PO is confirmed.
        """
        if self.env.context.get('maritime_management_demo_loading'):
            return
        finance_group = self.env.ref(
            'maritime_management.group_maritime_finance',
            raise_if_not_found=False,
        )
        for order in self.filtered('port_call_id'):
            mr_links = order.order_line.filtered('maintenance_request_id').mapped(
                'maintenance_request_id'
            )
            if not mr_links:
                continue
            mr_names = ', '.join(mr_links.mapped('name'))
            body = _(
                'Purchase order %(po)s confirmed by agent for port call %(pc)s. '
                'Fulfils maintenance request(s): %(mrs)s. '
                'Superintendent, finance, and agent notified by email.',
                po=order.name,
                pc=order.port_call_id.name,
                mrs=mr_names,
            )
            order._maritime_message_post(body, partner=order.port_call_id.agent_id)
            order.port_call_id.message_post(body=body, subtype_xmlid='mail.mt_comment')
            for mr in mr_links:
                mr.message_post(body=body, subtype_xmlid='mail.mt_comment')
                if mr.shore_state == 'assigned':
                    mr.shore_state = 'procured'
            order._maritime_notify_group(
                'maritime_management.mail_template_po_confirmed',
                'maritime_management.group_maritime_superintendent',
            )
            if finance_group and finance_group.user_ids:
                order._maritime_send_template(
                    'maritime_management.mail_template_po_confirmed',
                    users=finance_group.user_ids,
                )
            if order.port_call_id.agent_id:
                order._maritime_notify_partner(
                    'maritime_management.mail_template_po_confirmed_agent',
                    order.port_call_id.agent_id,
                )

    def _maritime_update_maintenance_requests(self):
        """
        Link confirmed purchase orders to disbursement accounts.
        """
        for order in self.filtered(lambda o: o.port_call_id and o.state in ('purchase', 'done')):
            disbursements = order.port_call_id.disbursement_ids.filtered(
                lambda d: d.state in ('pda_approved', 'executing', 'fda_submitted', 'matched', 'paid')
            )
            if disbursements:
                disbursements[0].purchase_order_ids = [(4, order.id)]

    def _maritime_vessel_stock_location(self):
        """
        Helper method to locate the target vessel stock location for this PO.
        """
        self.ensure_one()
        if self.port_call_id and self.port_call_id.vessel_id:
            vessel = self.port_call_id.vessel_id
            if not vessel.stock_location_id and vessel.is_vessel:
                vessel._maritime_ensure_stock_location()
            return vessel.stock_location_id
        for line in self.order_line:
            equipment = line.maintenance_request_id.equipment_id
            if equipment and equipment.is_vessel:
                if not equipment.stock_location_id:
                    equipment._maritime_ensure_stock_location()
                return equipment.stock_location_id
        return False

    def _get_destination_location(self):
        """
        Route stock picking destination to vessel stores if applicable.
        """
        location = self._maritime_vessel_stock_location()
        if location:
            return location.id
        return super()._get_destination_location()

    def _get_final_location_record(self):
        """
        Return vessel stock location record for stock picking generation.
        """
        location = self._maritime_vessel_stock_location()
        if location:
            return location
        return super()._get_final_location_record()
