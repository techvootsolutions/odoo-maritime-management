import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";

export class MaritimeControlCenterDashboard extends Component {
    static template = "maritime_management.ControlCenterDashboard";
    static components = { Layout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            scope: "live",
            role: "superintendent",
            data: null,
        });
        onWillStart(() => this.loadData());
    }

    get display() {
        return { controlPanel: {} };
    }

    get currency() {
        return this.state.data?.currency_symbol || "€";
    }

    normalizeDashboardData(data) {
        const timeline = data?.timeline || {};
        return {
            currency_symbol: "€",
            kpis: [],
            fleet_strip: [],
            upcoming_arrivals: [],
            action_queue: [],
            live_port_calls: [],
            mr_pipeline: [],
            criticality_chart: [],
            spend_chart: [],
            variance_chart: [],
            port_call_states: [],
            at_risk: [],
            activity_feed: [],
            timeline: {
                from: "",
                to: "",
                items: [],
                ...timeline,
            },
            ...data,
        };
    }

    async loadData() {
        this.state.loading = true;
        const data = await this.orm.call(
            "maritime.control.center",
            "get_dashboard_data",
            [],
            { scope: this.state.scope, role: this.state.role }
        );
        this.state.data = this.normalizeDashboardData(data);
        this.state.loading = false;
    }

    async setScope(scope) {
        if (this.state.scope !== scope) {
            this.state.scope = scope;
            await this.loadData();
        }
    }

    async setRole(role) {
        if (this.state.role !== role) {
            this.state.role = role;
            await this.loadData();
        }
    }

    async openRecord(model, resId) {
        if (!resId) {
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openAction(xmlid) {
        await this.action.doAction(xmlid);
    }

    async openPortCallsList() {
        await this.action.doAction("maritime_management.action_port_calls_list");
    }

    formatMoney(amount) {
        const value = amount || 0;
        return `${this.currency} ${value.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        })}`;
    }

    maxChartValue(items) {
        return Math.max(...items.map((i) => i.value || 0), 1);
    }

    maxSpendRow(row) {
        return Math.max(row.pda || 0, row.po || 0, row.fda || 0, 1);
    }

    timelineOffset(dateStr, rangeFrom, rangeTo) {
        const from = new Date(rangeFrom).getTime();
        const to = new Date(rangeTo).getTime();
        const current = new Date(dateStr).getTime();
        const span = to - from || 1;
        return Math.min(100, Math.max(0, ((current - from) / span) * 100));
    }

    timelineWidth(start, end, rangeFrom, rangeTo) {
        const left = this.timelineOffset(start, rangeFrom, rangeTo);
        const right = this.timelineOffset(end, rangeFrom, rangeTo);
        return Math.max(4, right - left);
    }
}

registry.category("actions").add(
    "maritime_management.control_center_dashboard",
    MaritimeControlCenterDashboard
);
