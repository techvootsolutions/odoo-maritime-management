import re
from datetime import timedelta

from odoo import api, fields, models

DA_STATE_LABELS = {
    'none': 'No DA',
    'draft': 'Estimate Draft',
    'pda_submitted': 'Awaiting Budget Approval',
    'pda_approved': 'Budget Approved',
    'executing': 'Agent Purchasing',
    'fda_submitted': 'Final Bill to Review',
    'matched': 'Matched',
    'paid': 'Paid',
    'cancelled': 'Cancelled',
}

DA_STATE_PRIORITY = [
    'fda_submitted', 'pda_submitted', 'executing',
    'pda_approved', 'matched', 'paid', 'draft', 'cancelled',
]

MR_PIPELINE_ORDER = [
    'draft', 'submitted', 'approved', 'assigned',
    'procured', 'delivered', 'done', 'cancelled',
]


class MaritimeControlCenter(models.AbstractModel):
    _name = 'maritime.control.center'
    _description = 'Maritime Control Center Dashboard'

    # ------------------------------------------------------------------ API
    @api.model
    def get_dashboard_data(self, scope='live', role='superintendent'):
        """Return aggregated dashboard payload for the OWL client action."""
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        currency = self.env.company.currency_id

        port_calls = self._port_calls_for_scope(scope, today)
        port_call_ids = port_calls.ids
        mrs = self._maintenance_requests_for_scope(scope, port_call_ids)
        das = self.env['port.disbursement.account'].search([
            ('port_call_id', 'in', port_call_ids),
        ]) if port_call_ids else self.env['port.disbursement.account']

        return {
            'scope': scope,
            'role': role,
            'currency_symbol': currency.symbol or currency.name,
            'generated_at': fields.Datetime.to_string(now),
            'kpis': self._build_kpis(mrs, port_calls, das, now, today, role),
            'action_queue': self._build_action_queue(mrs, port_calls, now, role),
            'live_port_calls': self._build_port_call_cards(
                port_calls.filtered(lambda pc: pc.state == 'active'),
                now,
            ),
            'mr_pipeline': self._build_mr_pipeline(mrs),
            'criticality_chart': self._build_criticality_chart(mrs),
            'spend_chart': self._build_spend_chart(port_calls),
            'variance_chart': self._build_variance_chart(das),
            'port_call_states': self._build_port_call_states(port_calls),
            'fleet_strip': self._build_fleet_strip(now),
            'upcoming_arrivals': self._build_upcoming_arrivals(port_calls, now),
            'at_risk': self._build_at_risk(mrs, port_calls, now),
            'activity_feed': self._build_activity_feed(port_call_ids),
            'timeline': self._build_timeline(port_calls, mrs, now, today),
        }

    # ------------------------------------------------------------- filters
    @api.model
    def _port_calls_for_scope(self, scope, today):
        domain = []
        if scope == 'live':
            domain = [('state', 'in', ('active', 'departed', 'planned'))]
        elif scope == 'month':
            month_start = today.replace(day=1)
            domain = [
                '|', '|',
                ('eta', '>=', month_start),
                ('etd', '>=', month_start),
                ('state', 'in', ('active', 'planned')),
            ]
        return self.env['port.call'].search(domain, order='eta desc, id desc')

    @api.model
    def _maintenance_requests_for_scope(self, scope, port_call_ids):
        if scope == 'all':
            return self.env['maintenance.request'].search([
                ('port_call_id', '!=', False),
            ])
        if not port_call_ids:
            return self.env['maintenance.request']
        return self.env['maintenance.request'].search([
            ('port_call_id', 'in', port_call_ids),
        ])

    # ---------------------------------------------------------------- KPIs
    @api.model
    def _build_kpis(self, mrs, port_calls, das, now, today, role):
        open_mrs = mrs.filtered(lambda mr: mr.shore_state not in ('done', 'cancelled'))
        week_end = today + timedelta(days=7)

        if role == 'finance':
            return [
                self._kpi(
                    'pda_pending',
                    'PDA to Approve',
                    len(das.filtered(lambda d: d.state == 'pda_submitted')),
                    'maritime_management.action_disbursement_pda',
                    'warning',
                ),
                self._kpi(
                    'fda_review',
                    'FDA to Review',
                    len(das.filtered(lambda d: d.state == 'fda_submitted')),
                    'maritime_management.action_disbursement_fda',
                    'danger',
                ),
                self._kpi(
                    'ready_pay',
                    'Ready to Pay',
                    len(das.filtered(lambda d: d.state == 'matched')),
                    'maritime_management.action_disbursement_matched',
                    'info',
                ),
                self._kpi(
                    'paid_month',
                    'Paid (scope)',
                    len(das.filtered(lambda d: d.state == 'paid')),
                    'maritime_management.action_disbursement_paid',
                    'success',
                ),
                self._kpi(
                    'over_budget',
                    'Over Budget DAs',
                    len(das.filtered(lambda d: d.variance_amount > 0 and d.fda_amount)),
                    'maritime_management.action_disbursement_fda',
                    'danger',
                ),
                self._kpi(
                    'executing',
                    'Agent Purchasing',
                    len(das.filtered(lambda d: d.state == 'executing')),
                    'maritime_management.action_disbursement_executing',
                    'primary',
                ),
            ]

        return [
            self._kpi(
                'awaiting_approval',
                'Awaiting My Approval',
                len(mrs.filtered(lambda mr: mr.shore_state == 'submitted')),
                'maritime_management.action_mr_submitted',
                'danger',
            ),
            self._kpi(
                'vital_open',
                'VITAL Jobs Open',
                len(open_mrs.filtered(lambda mr: mr.criticality == 'vital')),
                'maritime_management.action_mr_vital',
                'danger',
            ),
            self._kpi(
                'live_calls',
                'Live Port Calls',
                len(port_calls.filtered(lambda pc: pc.state == 'active')),
                'maritime_management.action_port_calls_active',
                'primary',
            ),
            self._kpi(
                'agent_buying',
                'Agent Still Buying',
                len(open_mrs.filtered(
                    lambda mr: mr.shore_state in ('assigned', 'approved')
                    and mr.procurement_status in ('none', 'rfq')
                )),
                'maritime_management.action_mr_procurement',
                'warning',
            ),
            self._kpi(
                'delivered',
                'Delivered Onboard',
                len(mrs.filtered(lambda mr: mr.shore_state == 'delivered')),
                'maritime_management.action_mr_delivered',
                'success',
            ),
            self._kpi(
                'upcoming',
                'Arriving This Week',
                len(port_calls.filtered(
                    lambda pc: pc.state == 'planned'
                    and pc.eta
                    and pc.eta.date() <= week_end
                )),
                'maritime_management.action_port_calls_planned',
                'info',
            ),
        ]

    @api.model
    def _kpi(self, key, label, value, action_xmlid, tone='primary'):
        return {
            'key': key,
            'label': label,
            'value': value,
            'action_xmlid': action_xmlid,
            'tone': tone,
        }

    # ---------------------------------------------------------- action queue
    @api.model
    def _build_action_queue(self, mrs, port_calls, now, role):
        items = []
        if role == 'finance':
            das = self.env['port.disbursement.account'].search([
                ('state', 'in', ('pda_submitted', 'fda_submitted', 'matched')),
            ], order='write_date desc', limit=20)
            for da in das:
                tone = 'danger' if da.state == 'fda_submitted' else 'warning'
                label = DA_STATE_LABELS.get(da.state, da.state)
                items.append({
                    'id': da.id,
                    'model': 'port.disbursement.account',
                    'priority': 1 if da.state == 'fda_submitted' else 2,
                    'tone': tone,
                    'title': da.name,
                    'subtitle': f'{da.vessel_id.name} @ {da.port_id.name}',
                    'reason': label,
                    'action_label': 'Open DA',
                    'sort_key': (1 if da.state == 'fda_submitted' else 2, -da.id),
                })
            items.sort(key=lambda x: x['sort_key'])
            return items[:12]

        for mr in mrs.filtered(lambda m: m.shore_state == 'submitted'):
            items.append(self._queue_mr(
                mr, 1, 'danger', 'Submitted — approve maintenance job', 'Approve',
            ))
        for mr in mrs.filtered(lambda m: m.shore_state == 'approved'):
            items.append(self._queue_mr(
                mr, 2, 'warning', 'Approved — assign to port call', 'Assign',
            ))
        for pc in port_calls.filtered(lambda p: p.state == 'planned'):
            if pc.eta and (pc.eta - now).days <= 5:
                items.append({
                    'id': pc.id,
                    'model': 'port.call',
                    'priority': 3,
                    'tone': 'info',
                    'title': pc.name,
                    'subtitle': f'{pc.vessel_id.name} @ {pc.port_id.name}',
                    'reason': f'Planned arrival in {(pc.eta - now).days} day(s)',
                    'action_label': 'Open port call',
                    'sort_key': (3, pc.eta),
                })
        items.sort(key=lambda x: x.get('sort_key', (x['priority'], x['title'])))
        return items[:12]

    @api.model
    def _queue_mr(self, mr, priority, tone, reason, action_label):
        crit = 0 if mr.criticality == 'vital' else 1
        return {
            'id': mr.id,
            'model': 'maintenance.request',
            'priority': priority,
            'tone': tone,
            'title': mr.name,
            'subtitle': f'{mr.equipment_id.name} · {mr.port_call_id.port_id.name if mr.port_call_id else "No port call"}',
            'reason': reason,
            'action_label': action_label,
            'badge': mr.criticality.upper() if mr.criticality else '',
            'sort_key': (priority, crit, mr.name),
        }

    # ------------------------------------------------------- port call cards
    @api.model
    def _build_port_call_cards(self, port_calls, now):
        cards = []
        for pc in port_calls:
            da_state = self._primary_da_state(pc)
            risk = self._port_call_risk(pc, now)
            cards.append({
                'id': pc.id,
                'name': pc.name,
                'vessel': pc.vessel_id.name,
                'port': pc.port_id.name,
                'agent': pc.agent_id.name or '—',
                'eta': self._fmt_dt(pc.eta),
                'etd': self._fmt_dt(pc.etd),
                'etd_hours': self._hours_until(pc.etd, now),
                'open_mrs': pc.open_mr_count,
                'total_mrs': pc.maintenance_request_count,
                'po_amount': pc.po_amount,
                'pda_amount': pc.pda_amount,
                'fda_amount': pc.fda_amount,
                'da_state': da_state,
                'da_label': DA_STATE_LABELS.get(da_state, da_state),
                'summary': self._port_call_summary(pc, da_state),
                'risk': risk,
            })
        return cards

    @api.model
    def _primary_da_state(self, port_call):
        states = port_call.disbursement_ids.mapped('state')
        if not states:
            return 'none'
        for state in DA_STATE_PRIORITY:
            if state in states:
                return state
        return states[0]

    @api.model
    def _port_call_summary(self, pc, da_state):
        parts = []
        if pc.open_mr_count:
            parts.append(f'{pc.open_mr_count} open job(s)')
        da_hints = {
            'pda_submitted': 'Approve budget',
            'executing': 'Agent buying now',
            'fda_submitted': 'Finance action needed',
        }
        if da_state in da_hints:
            parts.append(da_hints[da_state])
        return ' · '.join(parts) if parts else 'All clear'

    @api.model
    def _port_call_risk(self, pc, now):
        open_mrs = pc.maintenance_request_ids.filtered(
            lambda mr: mr.shore_state not in ('done', 'cancelled')
        )
        vital_unprocured = open_mrs.filtered(
            lambda mr: mr.criticality == 'vital'
            and mr.procurement_status in ('none', 'rfq')
        )
        if vital_unprocured and pc.etd and self._hours_until(pc.etd, now) < 48:
            return 'critical'
        if open_mrs.filtered(
            lambda mr: mr.shore_state in ('assigned', 'approved')
            and mr.procurement_status in ('none', 'rfq')
        ):
            return 'warning'
        return 'ok'

    # -------------------------------------------------------------- charts
    @api.model
    def _build_mr_pipeline(self, mrs):
        selection = dict(
            self.env['maintenance.request']._fields['shore_state'].selection
        )
        open_mrs = mrs.filtered(lambda mr: mr.shore_state != 'cancelled')
        counts = {k: 0 for k in MR_PIPELINE_ORDER}
        for mr in open_mrs:
            counts[mr.shore_state] = counts.get(mr.shore_state, 0) + 1
        total = sum(counts.values()) or 1
        colors = {
            'draft': '#94a3b8', 'submitted': '#f59e0b', 'approved': '#3b82f6',
            'assigned': '#6366f1', 'procured': '#8b5cf6', 'delivered': '#10b981',
            'done': '#059669', 'cancelled': '#64748b',
        }
        return [
            {
                'key': key,
                'label': selection.get(key, key),
                'value': counts.get(key, 0),
                'percent': round(100.0 * counts.get(key, 0) / total, 1),
                'color': colors.get(key, '#64748b'),
            }
            for key in MR_PIPELINE_ORDER
            if key in selection
            and (counts.get(key, 0) or key in ('submitted', 'assigned', 'procured'))
        ]

    @api.model
    def _build_criticality_chart(self, mrs):
        open_mrs = mrs.filtered(lambda mr: mr.shore_state not in ('done', 'cancelled'))
        data = {'vital': 0, 'essential': 0, 'desirable': 0}
        for mr in open_mrs:
            data[mr.criticality or 'essential'] = data.get(mr.criticality or 'essential', 0) + 1
        colors = {'vital': '#dc2626', 'essential': '#f59e0b', 'desirable': '#64748b'}
        labels = {'vital': 'VITAL', 'essential': 'ESSENTIAL', 'desirable': 'DESIRABLE'}
        return [
            {'key': k, 'label': labels[k], 'value': data[k], 'color': colors[k]}
            for k in ('vital', 'essential', 'desirable')
        ]

    @api.model
    def _build_spend_chart(self, port_calls):
        rows = []
        for pc in port_calls.filtered(lambda p: p.state in ('active', 'departed', 'planned'))[:8]:
            rows.append({
                'id': pc.id,
                'label': f'{pc.vessel_id.name}',
                'sublabel': pc.port_id.name,
                'pda': pc.pda_amount,
                'po': pc.po_amount,
                'fda': pc.fda_amount,
            })
        return rows

    @api.model
    def _build_variance_chart(self, das):
        rows = []
        for da in das.filtered(lambda d: d.pda_amount and d.fda_amount)[:10]:
            rows.append({
                'id': da.id,
                'label': da.port_call_id.name,
                'sublabel': da.vessel_id.name,
                'variance_percent': da.variance_percent,
                'variance_amount': da.variance_amount,
                'tone': 'danger' if da.variance_amount > 0 else 'success',
            })
        rows.sort(key=lambda r: abs(r['variance_percent']), reverse=True)
        return rows[:8]

    @api.model
    def _build_port_call_states(self, port_calls):
        labels = dict(self.env['port.call']._fields['state'].selection)
        counts = {}
        for pc in port_calls:
            counts[pc.state] = counts.get(pc.state, 0) + 1
        colors = {
            'planned': '#3b82f6', 'active': '#10b981',
            'departed': '#f59e0b', 'closed': '#64748b', 'draft': '#94a3b8',
        }
        return [
            {
                'key': state,
                'label': labels.get(state, state),
                'value': count,
                'color': colors.get(state, '#64748b'),
            }
            for state, count in counts.items()
        ]

    # ----------------------------------------------------------- fleet strip
    @api.model
    def _build_fleet_strip(self, now):
        vessels = self.env['maintenance.equipment'].search(
            [('is_vessel', '=', True)], order='name',
        )
        strip = []
        for vessel in vessels:
            pc = self.env['port.call'].search([
                ('vessel_id', '=', vessel.id),
                ('state', 'in', ('active', 'planned')),
            ], order='eta asc', limit=1)
            if pc:
                status = 'active' if pc.state == 'active' else 'planned'
                detail = f'{pc.port_id.name} · {pc.open_mr_count} open job(s)'
            else:
                last = self.env['port.call'].search(
                    [('vessel_id', '=', vessel.id)],
                    order='etd desc', limit=1,
                )
                status = 'idle'
                detail = last.port_id.name if last else 'No recent port call'
            strip.append({
                'id': vessel.id,
                'name': vessel.name,
                'status': status,
                'detail': detail,
                'port_call_id': pc.id if pc else False,
            })
        return strip

    # ---------------------------------------------------- upcoming arrivals
    @api.model
    def _build_upcoming_arrivals(self, port_calls, now):
        week_end = (now + timedelta(days=7)).date()
        upcoming = port_calls.filtered(
            lambda pc: pc.state == 'planned'
            and pc.eta
            and now.date() <= pc.eta.date() <= week_end
        ).sorted('eta')
        rows = []
        for pc in upcoming:
            days = (pc.eta.date() - now.date()).days
            if days == 0:
                eta_label = 'Today'
            elif days == 1:
                eta_label = 'Tomorrow'
            else:
                eta_label = f'In {days} days'
            open_mrs = pc.open_mr_count
            rows.append({
                'id': pc.id,
                'name': pc.name,
                'vessel': pc.vessel_id.name,
                'port': pc.port_id.name,
                'agent': pc.agent_id.name or '—',
                'eta': self._fmt_dt(pc.eta),
                'eta_label': eta_label,
                'open_mrs': open_mrs,
                'summary': (
                    f'{open_mrs} open job(s) · {pc.agent_id.name}'
                    if open_mrs and pc.agent_id
                    else (f'{open_mrs} open job(s)' if open_mrs else 'No open jobs yet')
                ),
            })
        return rows

    # -------------------------------------------------------------- at risk
    @api.model
    def _build_at_risk(self, mrs, port_calls, now):
        items = []
        open_mrs = mrs.filtered(lambda mr: mr.shore_state not in ('done', 'cancelled'))

        for mr in open_mrs.filtered(lambda m: m.criticality == 'vital'):
            pc = mr.port_call_id
            if pc and pc.etd and self._hours_until(pc.etd, now) < 48:
                if mr.procurement_status in ('none', 'rfq'):
                    items.append(self._risk_item(
                        mr, 'VITAL job not procured before ETD',
                        'critical',
                    ))

        for mr in open_mrs.filtered(lambda m: m.shore_state == 'submitted'):
            age = (now - mr.create_date).days if mr.create_date else 0
            if age >= 3:
                items.append(self._risk_item(
                    mr, f'Awaiting approval for {age} days', 'warning',
                ))

        for pc in port_calls.filtered(lambda p: p.state == 'active'):
            assigned = pc.maintenance_request_ids.filtered(
                lambda mr: mr.shore_state == 'assigned'
                and mr.procurement_status in ('none', 'rfq')
            )
            confirmed_pos = pc.sudo().purchase_order_ids.filtered(
                lambda po: po.state in ('purchase', 'done')
            )
            if assigned and not confirmed_pos:
                items.append({
                    'id': pc.id,
                    'model': 'port.call',
                    'title': pc.name,
                    'subtitle': pc.vessel_id.name,
                    'reason': 'Assigned jobs but no confirmed PO yet',
                    'tone': 'warning',
                })

        for pc in port_calls.filtered(lambda p: p.etd and p.etd < now and p.state == 'active'):
            if pc.open_mr_count:
                items.append({
                    'id': pc.id,
                    'model': 'port.call',
                    'title': pc.name,
                    'subtitle': pc.vessel_id.name,
                    'reason': 'ETD passed with open maintenance jobs',
                    'tone': 'critical',
                })

        return items[:10]

    @api.model
    def _risk_item(self, mr, reason, tone):
        return {
            'id': mr.id,
            'model': 'maintenance.request',
            'title': mr.name,
            'subtitle': mr.equipment_id.name,
            'reason': reason,
            'tone': tone,
        }

    # --------------------------------------------------------- activity feed
    @api.model
    def _build_activity_feed(self, port_call_ids):
        if not port_call_ids:
            return []
        models = ('port.call', 'maintenance.request', 'port.disbursement.account', 'purchase.order')
        domain = [
            ('model', 'in', models),
            ('message_type', '=', 'comment'),
        ]
        pc_pcs = list(port_call_ids)
        mr_ids = self.env['maintenance.request'].search([
            ('port_call_id', 'in', port_call_ids),
        ]).ids
        da_ids = self.env['port.disbursement.account'].search([
            ('port_call_id', 'in', port_call_ids),
        ]).ids
        po_ids = self.env['purchase.order'].sudo().search([
            ('port_call_id', 'in', port_call_ids),
        ]).ids

        messages = self.env['mail.message'].search([
            '|', '|', '|',
            '&', ('model', '=', 'port.call'), ('res_id', 'in', pc_pcs),
            '&', ('model', '=', 'maintenance.request'), ('res_id', 'in', mr_ids),
            '&', ('model', '=', 'port.disbursement.account'), ('res_id', 'in', da_ids),
            '&', ('model', '=', 'purchase.order'), ('res_id', 'in', po_ids),
            ('body', 'ilike', '<!-- mcc:'),
        ], order='date desc', limit=20)

        feed = []
        for msg in messages:
            raw = msg.body or ''
            body = self._strip_html(raw)[:140]
            if not body:
                continue
            feed.append({
                'id': msg.id,
                'model': msg.model,
                'res_id': msg.res_id,
                'date': self._fmt_dt(msg.date),
                'author': msg.author_id.name or 'System',
                'body': body,
            })
            if len(feed) >= 20:
                break
        return feed

    # -------------------------------------------------------------- timeline
    @api.model
    def _build_timeline(self, port_calls, mrs, now, today):
        horizon = today + timedelta(days=30)
        rows = []
        for pc in port_calls.filtered(lambda p: p.eta and p.eta.date() <= horizon):
            if pc.state == 'closed':
                continue
            vital = len(mrs.filtered(
                lambda mr: mr.port_call_id == pc
                and mr.criticality == 'vital'
                and mr.shore_state not in ('done', 'cancelled')
            ))
            start = max(pc.eta.date(), today) if pc.eta else today
            end = pc.etd.date() if pc.etd else start + timedelta(days=2)
            if end < today:
                continue
            rows.append({
                'id': pc.id,
                'label': pc.vessel_id.name,
                'sublabel': f'{pc.port_id.name} ({pc.state})',
                'start': start.isoformat(),
                'end': end.isoformat(),
                'vital': vital,
                'state': pc.state,
            })
        rows.sort(key=lambda r: r['start'])
        return {
            'from': today.isoformat(),
            'to': horizon.isoformat(),
            'items': rows,
        }

    # -------------------------------------------------------------- helpers
    @api.model
    def _fmt_dt(self, dt):
        if not dt:
            return '—'
        return fields.Datetime.to_string(dt)[:16]

    @api.model
    def _hours_until(self, dt, now):
        if not dt:
            return 9999
        return (dt - now).total_seconds() / 3600.0

    @api.model
    def _strip_html(self, html):
        text = re.sub(r'<[^>]+>', ' ', html or '')
        return ' '.join(text.split())
