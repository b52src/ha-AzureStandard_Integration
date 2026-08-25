# Azure Standard Integration — Phase 12 Handoff Context

## Goal

Phase 12 fixes the startup crash introduced in Phase 11 and redesigns the
sidebar panel with a **four-tab layout**, replacing the single-page scroll
with focused views for Summary, Lists, Products, and Account.

---

## Build Plan Status

| Phase | Description | Status |
|---|---|---|
| 1 | Core scaffold | ✅ Done |
| 2 | Drop & cutoff sensors | ✅ Done |
| 3 | Account login: config flow | ✅ Done |
| 4 | Order sensors | ✅ Done |
| 5 | Shopping list sensors | ✅ Done |
| 6 | Product discovery engine | ✅ Done |
| 7 | Per-product sensor groups | ✅ Done |
| 8 | Options flow product management | ✅ Done |
| 9 | Account sensors: AccountCredit, PendingPayment | ✅ Done |
| 10 | Polish: translations, icons, README | ✅ Done |
| 11 | Sidebar panel (Web Component) | ✅ Done |
| **12** | **Panel tabs + startup fix** | **✅ Done** |

---

## What Was Done in Phase 12

### Bug Fix — `register_static_path` AttributeError

**Symptom:**
```
AttributeError: 'HomeAssistantHTTP' object has no attribute 'register_static_path'.
Did you mean: 'async_register_static_paths'?
```

**Root cause:** HA 2024.x removed the synchronous `register_static_path` method from
`HomeAssistantHTTP`. Phase 11 used the old API directly.

**Fix in `custom_components/azure_standard/__init__.py`:**

```python
# Before (broken)
hass.http.register_static_path(
    "/azure_standard_panel",
    str(www_path),
    cache_headers=True,
)

# After (fixed)
from homeassistant.components.http import StaticPathConfig

await hass.http.async_register_static_paths([
    StaticPathConfig(
        url_path="/azure_standard_panel",
        path=str(www_path),
        cache_headers=True,
    )
])
```

The `async_setup` function was already `async`, so `await` was the only additional
change needed. The unused `_PANEL_URL` constant was also removed.

---

### Panel Redesign — Four-Tab Layout

`www/azure-standard-panel.js` was rewritten. The single-page scroll is replaced
by a tab bar. Tab state is stored in `this._tab` and survives re-renders triggered
by `hass` state updates, so the user's selected tab doesn't reset on every poll.

#### Tab 1 — Summary (always visible)

Combines the two most-watched cards on one screen:

- **Drop & Cutoff** — order window badge (OPEN/CLOSED), cutoff date + urgency
  colouring (amber ≤3 days, red ≤1 day), delivery date, pickup date/week,
  days until pickup.
- **Active Order** (account mode only) — status + "placed" badge, item count,
  order total, last order date, account credit, pending payment.

#### Tab 2 — Lists (account mode)

One card per shopping list. Each card shows:
- List name + item count header.
- First 5 items previewed as a bullet list; "+N more…" if longer.
- **"Edit on Azure Standard ↗"** link-button at the bottom of each card.

No in-panel list editing. All mutations happen on the Azure Standard website.

Empty state: a single "Manage lists on Azure Standard ↗" button.

The tab label shows the total list count as a static badge.

#### Tab 3 — Products (account mode)

Tracked products table with a new **Avg cycle** column:

| Column | Source |
|---|---|
| Product | `friendly_name` attr or code slug |
| Last ordered | `sensor.azure_standard_<code>_last_ordered` |
| Times | `sensor.azure_standard_<code>_times_ordered` |
| Days since | `sensor.azure_standard_<code>_days_since` |
| **Avg cycle** | `round(days_since / (times − 1))` displayed as `~Nd` |
| Reorder | `sensor.azure_standard_<code>_reorder_due` == "true" → ✓ |

Reorder-due rows are highlighted amber; the tab label shows a **red badge** with
the count of due products (hidden when zero).

A **"Shop on Azure Standard ↗"** link-button sits below the table.

#### Tab 4 — Account (account mode)

Summary card: credit, pending payment, last order date, active order status.
A **"Order history on Azure Standard ↗"** link-button below.

---

### ↻ Refresh Button

A circular refresh button (↻) appears in the panel header on every tab.
Clicking it calls `homeassistant.update_entity` on `sensor.azure_standard_drop_name`,
which triggers a coordinator refresh without a full HA reload. The button shows
`…` while the call is in-flight and re-enables on completion.

---

## Files Changed in Phase 12

```
custom_components/azure_standard/
├── __init__.py          — async_register_static_paths fix; removed _PANEL_URL constant
├── manifest.json        — version 0.1.1 → 0.1.2
└── www/
    └── azure-standard-panel.js   — full rewrite: tab bar, refresh button, avg cycle

CHANGELOG.md             — 0.1.2 entry added
docs/phase12-handoff.md  ← this file
```

---

## Test Steps

1. Copy `custom_components/azure_standard/` to your HA `custom_components/` directory.
2. Restart Home Assistant.
3. Confirm **no** `register_static_path` error in the logs.
4. Confirm "Azure Standard" appears in the left sidebar.
5. Click it — the **Summary** tab should render with Drop & Cutoff (and Active Order
   if you're in account mode).
6. Switch to the **Lists** tab — shopping list cards with "Edit on Azure Standard ↗"
   link-buttons.
7. Switch to the **Products** tab — tracked products table with the Avg cycle column.
   If any products are reorder-due, the tab should show a red badge.
8. Switch to the **Account** tab — credit and payment info.
9. Click the **↻** button — it should spin briefly and the panel should refresh.
10. Manual mode: only the Summary tab (with Drop & Cutoff only) is visible.

### Syntax check

```bash
cd /Users/seancrow/Forgejo/AzureStandard_Intigration
.venv/bin/python3 -m py_compile \
  custom_components/azure_standard/__init__.py \
  custom_components/azure_standard/api.py \
  custom_components/azure_standard/coordinator.py \
  custom_components/azure_standard/config_flow.py \
  custom_components/azure_standard/sensor.py \
  custom_components/azure_standard/const.py \
  custom_components/azure_standard/discovery.py
```

---

## Next Iteration Ideas (Phase 13+)

| Phase | Name | Description |
|---|---|---|
| 13 | Price history chart | Inline SVG sparkline per tracked product showing price over the last N drops. Requires coordinator to accumulate a price history list in entry data. |
| 14 | Panel config UI | Options to show/hide individual tabs; persisted via HA storage API. |
| 15 | Notifications badge | Red unread count on the sidebar nav icon when reorder-due products exist; clears on panel visit. |
| 16 | Automation blueprints | Blueprint-based automations: notify on cutoff approaching, alert when order window opens, push reminder when reorder-due products appear. |
