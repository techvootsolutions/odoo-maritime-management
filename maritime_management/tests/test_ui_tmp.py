from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install', 'mm_ui')
class TestMaritimeUi(HttpCase):

    def _open(self, url, ready, login, code="console.log('test successful')"):
        self.browser_js(url, code, ready=ready, login=login, timeout=120)

    def test_ui_pages(self):
        users = ['admin']
        for xmlid in ('maritime_management.user_demo_superintendent', 'maritime_management.user_demo_finance'):
            user = self.env.ref(xmlid, raise_if_not_found=False)
            if user:
                user.password = user.login
                users.append(user.login)
        for login, group in (('ui_agent', 'group_maritime_agent'), ('ui_crew', 'group_maritime_user')):
            self.env['res.users'].create({
                'name': login, 'login': login, 'password': login,
                'group_ids': [(6, 0, [self.env.ref(f'maritime_management.{group}').id])],
            })
            users.append(login)
        dash = self.env.ref('maritime_management.action_control_center_dashboard')
        windows = [
            ('maritime_management.port_call_action', 'port.call'),
            ('maritime_management.port_disbursement_action', 'port.disbursement.account'),
            ('maritime_management.maintenance_request_maritime_action', 'maintenance.request'),
            ('maritime_management.maintenance_equipment_vessel_action', 'maintenance.equipment'),
            ('maritime_management.maritime_port_action', 'maritime.port'),
            ('maritime_management.action_port_calls_list', 'port.call'),
        ]
        for login in users:
            self._open(
                f'/odoo/action-{dash.id}', "!!document.querySelector('.o_mcc_kpi')", login,
                code="""
                    document.querySelector('.o_mcc_kpi').click();
                    const t0 = Date.now();
                    const wait = () => {
                        if (document.querySelector('.o_list_view, .o_kanban_view')) { console.log('test successful'); }
                        else if (Date.now() - t0 > 20000) { console.error('KPI drill-down did not open'); }
                        else { setTimeout(wait, 200); }
                    };
                    wait();
                """,
            )
            for xmlid, model in windows:
                action = self.env.ref(xmlid)
                self._open(f'/odoo/action-{action.id}', "!!document.querySelector('.o_view_controller')", login)
                for mode in [m for m in action.view_mode.split(',') if m in ('list', 'kanban')]:
                    self._open(f'/odoo/action-{action.id}?view_type={mode}', f"!!document.querySelector('.o_{mode}_view')", login)
                rec = self.env[model].search([], limit=1)
                if rec:
                    self._open(f'/odoo/action-{action.id}/{rec.id}', "!!document.querySelector('.o_form_view')", login)
