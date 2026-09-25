from odoo import api, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Automatically set partner maritime_role to 'port_agent' when a user
        is created with the Port Agent security group.
        """
        users = super().create(vals_list)
        users._sync_maritime_partner_roles()
        return users

    def write(self, vals):
        """
        Automatically update partner maritime_role when user security groups change.
        """
        res = super().write(vals)
        self._sync_maritime_partner_roles()
        return res

    def _sync_maritime_partner_roles(self):
        """
        Synchronize partner maritime_role based on assigned maritime security groups.
        """
        for user in self:
            if not user.partner_id:
                continue
            if user.has_group('maritime_management.group_maritime_agent'):
                if user.partner_id.maritime_role != 'port_agent':
                    user.partner_id.sudo().write({'maritime_role': 'port_agent'})
