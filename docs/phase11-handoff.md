# Azure Standard Integration — Phase 11 Handoff Context

## Goal

Phase 11 adds a dedicated **sidebar panel** to the Home Assistant UI. Users get a
live Azure Standard dashboard directly in the HA navigation — no Lovelace card
configuration required.

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
| **11** | **Sidebar panel (Web Component)** | **✅ Done** |

---

## What Was Done in Phase 11

### New file: `custom_components/azure_standard/www/azure-standard-panel.js`

A self-contained ES6 Web Component (`<azure-standard-panel>`).

**How it works:**
- HA injects the `hass` property on every state change — the component re-renders live.
- Reads all `sensor.azure_standard_*` and `binary_sensor.azure_standard_*` entities
  directly from `hass.states` — zero extra API calls.
- Shopping lists and tracked product tables are discovered dynamically (suffix-based)
  so new lists / tracked products appear without any code change.
- Uses HA CSS custom properties (`--primary-text-color`, `--card-background-color`, etc.)
  so it respects the user's chosen theme automatically.

**Sections rendered:**
| Section | Entities used | Visibility |
|---|---|---|
| Drop & Cutoff | `drop_name`, `next_cutoff`, `days_until_cutoff`, `delivery_date`, `pickup_date`, `pickup_week`, `days_until_pickup`, `order_window_open` | Always |
| Active Order | `active_order_status`, `active_order_item_count`, `active_order_total`, `order_placed`, `last_order_date`, `account_credit`, `pending_payment` | Account mode only (when entities exist) |
| Shopping Lists | All `sensor.azure_standard_*_list` entities | Account mode only |
| Tracked Products | All `sensor.azure_standard_*_last_ordered` entities | Account mode only |

**UX details:**
- Cutoff countdown turns amber at ≤ 3 days, red at ≤ 1 day.
- Order window shows a green "OPEN" or red "CLOSED" badge.
- Reorder-due products are highlighted in amber in the products table.
- Shopping list items preview the first 5 entries with a "+N more…" overflow.

### Changes to `custom_components/azure_standard/__init__.py`

1. **`async_setup`** — new hook that registers `www/` as an HA static path at
   `/azure_standard_panel/` using `hass.http.register_static_path()`. This must
   run before `async_setup_entry` so the JS URL is valid when HA renders the panel.

2. **`async_setup_entry`** — calls `panel_custom.async_register_panel()` after
   coordinator setup. Idempotent guard: skips registration if `DOMAIN` is already
   in `hass.data["frontend_panels"]` (handles multiple config entries gracefully).

3. **`async_unload_entry`** — calls `hass.components.frontend.async_remove_panel(DOMAIN)`
   when the last config entry is unloaded, cleaning up the sidebar entry.

### Changes to `manifest.json`

- `version`: `0.1.0` → `0.1.1`
- `dependencies`: `[]` → `["frontend"]`

The `frontend` dependency ensures HA loads its frontend integration (which provides
`panel_custom` and `hass.http`) before this integration initialises.

---

## Files Changed in Phase 11

```
custom_components/azure_standard/
├── __init__.py          — async_setup + panel registration/removal
├── manifest.json        — version 0.1.1, frontend dependency
└── www/
    └── azure-standard-panel.js   ← NEW

CHANGELOG.md             — 0.1.1 entry added
docs/phase11-handoff.md  ← this file
```

---

## Panel URL

Once HA loads the integration, the panel is accessible at:

```
http://<ha-host>/azure_standard
```

It appears in the HA left sidebar as **Azure Standard** with the `mdi:sprout` icon.

---

## Test Steps

1. Copy `custom_components/azure_standard/` to your HA `custom_components/` directory.
2. Restart Home Assistant.
3. Confirm "Azure Standard" appears in the left sidebar.
4. Click it — the panel should render all sensors live.
5. For manual mode: only the Drop & Cutoff section is populated.
6. For account mode: all four sections render with live data.

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

## Next Iteration Ideas (Phase 12+)

- **Panel actions** — Add to shopping list button, trigger manual coordinator refresh.
- **Price history chart** — Inline sparkline for tracked product price over time.
- **Panel config UI** — Let users choose which sections to show/hide.
- **Notifications badge** — Show unread reorder-due count on the sidebar icon.
