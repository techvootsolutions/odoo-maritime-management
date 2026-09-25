# Maritime Management

`maritime_management` — **Odoo 19** (Community and Enterprise)

Port-call-centric ship management: vessels and machinery, port calls, Proforma/Final
Disbursement Accounts (PDA/FDA), maintenance requests with shore approval, spare-part
procurement, vessel stores stock, and a role-aware Control Center dashboard.

## Dependencies

`contacts`, `maintenance`, `account`, `purchase`, `stock`, `purchase_stock` (plus `base`, `mail`).

## Security roles (Settings → Users → Ship Management)

| Group | XML ID | Purpose |
|---|---|---|
| User | `group_maritime_user` | Onboard officers: vessels, port calls, maintenance requests |
| Technical Superintendent | `group_maritime_superintendent` | Approves requisitions and PDAs |
| Maritime Finance | `group_maritime_finance` | Reviews FDA variance, 3-way match, payment |
| Port Agent | `group_maritime_agent` | Submits PDA/FDA; partner role is synced automatically |

Maritime users see the whole fleet (vessels, machinery and maintenance requests), within
their allowed companies. Buttons and tabs that open purchase orders, vendor bills or
transfers are shown to users who also hold the matching Purchase, Accounting or Inventory
rights.

## Workflow

1. **Fleet setup** — create vessels (a vessel stores location is created automatically) and machinery.
2. **Port call** — vessel + port + agent + ETA/ETD → *Plan* → *Activate* (a disbursement account is created and the agent is emailed).
3. **Maintenance request** — spare-part lines, criticality → *Submit to Shore* → *Approve Requisition* (PDA estimate lines are synced to the DA).
4. **Procurement** — create the PO from the DA or MR; confirmation is blocked until the PDA is approved. Receipts go to the vessel stores.
5. **Consumption** — *Check Availability* on the approved MR consumes parts from the vessel stores.
6. **Settlement** — *Submit FDA* → *3-Way Matched* → *Mark Paid*; then *Departed* → *Close* the port call.

## Demo data

Installed only in databases created with demo data: a five-vessel dry-bulk fleet, port
agents and chandlers, port calls in every state, disbursement accounts across the PDA/FDA
lifecycle, purchase orders and dashboard activity. The demo scenario is loaded by the
`post_init_hook`, which does nothing on databases without demo data.
