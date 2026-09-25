from odoo import api, fields, models


class AccountMove(models.Model):
    """
    Inherit account.move to link vendor bills to port calls and sync disbursement account documents.
    """
    _inherit = 'account.move'

    port_call_id = fields.Many2one(
        'port.call',
        string='Port Call',
        check_company=True,
        index=True,
        help='Port visit linked to this vendor bill.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create invoice records and sync related disbursement account documents.
        """
        moves = super().create(vals_list)
        for move in moves:
            if move.port_call_id and move.move_type == 'in_invoice':
                disbursements = self.env['port.disbursement.account'].search([('port_call_id', '=', move.port_call_id.id)])
                for da in disbursements:
                    da.write({'bill_ids': [(4, move.id)]})
        return moves

    def write(self, vals):
        """
        Update invoice records and sync related disbursement account documents if port call changed.
        """
        res = super().write(vals)
        if 'port_call_id' in vals:
            for move in self:
                if move.port_call_id and move.move_type == 'in_invoice':
                    disbursements = self.env['port.disbursement.account'].search([('port_call_id', '=', move.port_call_id.id)])
                    for da in disbursements:
                        da.write({'bill_ids': [(4, move.id)]})
        return res
