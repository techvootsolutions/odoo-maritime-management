from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MaintenanceEquipment(models.Model):
    """
    Inherit maintenance.equipment to represent vessels and onboard machinery components,
    including automated vessel stores stock location management.
    """
    _inherit = 'maintenance.equipment'

    is_vessel = fields.Boolean(
        string='Is Vessel',
        help='Mark equipment records that represent a ship / vessel.',
    )
    imo_number = fields.Char(
        string='IMO Number',
        help='International Maritime Organization number — unique seven-digit vessel identifier.',
    )
    vessel_type = fields.Selection(
        selection=[
            ('bulk', 'Dry Bulk Carrier'),
            ('tanker', 'Tanker'),
            ('container', 'Container'),
            ('other', 'Other'),
        ],
        string='Vessel Type',
    )
    flag_country_id = fields.Many2one('res.country', string='Flag State')
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Vessel Cost Center',
        check_company=True,
    )
    vessel_id = fields.Many2one(
        'maintenance.equipment',
        string='Assigned Vessel',
        domain="[('is_vessel', '=', True)]",
        help='Select the ship / vessel this machinery component belongs to.',
    )
    equipment_count = fields.Integer(
        string='Machinery Count',
        compute='_compute_equipment_count',
        help='Total machinery components installed on this vessel.',
    )
    stock_location_id = fields.Many2one(
        'stock.location',
        string='Vessel Stores Location',
        check_company=True,
        domain="[('usage', '=', 'internal')]",
        help='Onboard spare parts stock location for this vessel.',
    )

    @api.depends('is_vessel')
    def _compute_equipment_count(self):
        """
        Compute total sub-equipment / machinery assigned to this vessel record.
        """
        for record in self:
            if record.is_vessel:
                record.equipment_count = self.search_count([
                    ('vessel_id', '=', record.id),
                    ('is_vessel', '=', False),
                ])
            else:
                record.equipment_count = 0

    def action_view_vessel_equipments(self):
        """
        Return an act_window action opening the machinery components installed on this vessel.

        :return: dict act_window action specification
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Ship Machinery / Components'),
            'res_model': 'maintenance.equipment',
            'view_mode': 'list,form',
            'domain': [('vessel_id', '=', self.id), ('is_vessel', '=', False)],
            'context': {
                'default_vessel_id': self.id,
                'default_is_vessel': False,
            },
        }

    def _maritime_ensure_stock_location(self):
        """
        Create an internal stock location under the company warehouse if missing.
        """
        Location = self.env['stock.location']
        for equipment in self.filtered('is_vessel'):
            if equipment.stock_location_id:
                continue
            company = equipment.company_id or self.env.company
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', company.id)], limit=1,
            )
            if not warehouse:
                raise UserError(_(
                    'Configure a warehouse for %(company)s before creating vessel stock locations.',
                    company=company.name,
                ))
            parent = warehouse.lot_stock_id
            existing = Location.search([
                ('location_id', '=', parent.id),
                ('name', '=', f'{equipment.name} Stores'),
                ('company_id', '=', company.id),
            ], limit=1)
            location = existing or Location.create({
                'name': f'{equipment.name} Stores',
                'location_id': parent.id,
                'usage': 'internal',
                'company_id': company.id,
            })
            equipment.stock_location_id = location.id
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create equipment records and ensure stock locations for vessel records.
        """
        records = super().create(vals_list)
        records.filtered('is_vessel')._maritime_ensure_stock_location()
        return records
