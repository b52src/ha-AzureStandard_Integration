# Azure Standard Integration — Phase 9 Handoff Context

## Goal

Build a complete Home Assistant custom integration for Azure Standard (organic food co-op delivery).
The integration monitors drop cutoff dates, orders, shopping lists, and purchase history.
Being built phase by phase per the spec in `docs/proposal.md`.

---

## Build Plan Status

| Phase | Description | Status |
|---|---|---|
| 1 | Core scaffold: manifest, const, __init__, entity, api (public), strings | ✅ Done |
| 2 | Drop & cutoff sensors: coordinator, NextCutoff, DaysUntilCutoff, DropName, DeliveryDate, OrderWindowOpen | ✅ Done |
| 3 | Account login: config_flow (mode select, manual, account, drop_confirm steps) | ✅ Done |
| 4 | Order sensors: ActiveOrderStatus, ActiveOrderItemCount, ActiveOrderTotal, LastOrderDate | ✅ Done |
| 5 | Shopping list sensors: ShoppingListSensor (dynamic), coordinator list polling | ✅ Done |
| 6 | Product discovery engine: discovery.py, ProductStats, ProductDiscoveryEngine, HA notification | ✅ Done |
| 7 | Product sensors: per-product sensor group (last_ordered, times_ordered, days_since, reorder_due) | ✅ Done |
| 8 | Options flow product management: checkbox UI, dynamic entity creation | ✅ Done |
| **9** | **Account sensors: AccountCredit, PendingPayment** | **✅ Done** |
| 10 | Polish: translations, icons, README | Pending |

---

## What Was Done in Phase 9

### AccountCreditSensor

Added to `sensor.py`. Reads `coordinator.data.account_credit` which was already populated
by the orders-interval block in `coordinator.py` via `GET /account-entries?balance=true&limit=1&start=-1`.

- `device_class = MONETARY`, `unit = USD`, `state_class = MEASUREMENT`
- `unique_id = {entry_id}_account_credit`
- `translation_key = "account_credit"` (added to strings.json and translations/en.json)

### PendingPaymentSensor

Added to `sensor.py`. Reads `coordinator.data.pending_payment`, which remains `None`
because **no Azure Standard API endpoint exposes an open-order total**.

**Endpoint investigation (live-tested):**
- `GET /order/{id}` — no `total`, `grandTotal`, or `lineTotal` field; only `salesTax`,
  `status`, `checkout-payment` (payment method, not amount)
- `GET /order/{id}/items`, `/order-items?filter-order=`, `/packaged-order-products?filter-order=`,
  `/order/{id}/invoice` — all return 404
- `GET /orders?filter-status=open` — same shape as single-order endpoint; no totals

The sensor is wired and will show `unavailable` in HA until the endpoint is found.
`coordinator.py` does not need changes — `pending_payment` is already a field on
`AzureStandardData` (defaulting to `None`).

Both sensors are registered in `async_setup_entry` alongside the order sensors
(account mode only).

---

## Files Changed in Phase 9

```
custom_components/azure_standard/
├── sensor.py            — AccountCreditSensor + PendingPaymentSensor (new classes)
│                          both added to async_setup_entry entity list (account mode)
├── strings.json         — added account_credit and pending_payment under entity.sensor
└── translations/en.json — same additions (mirrors strings.json)

test_credentials.py      — added check [12]: account credit balance field verification
```

---

## Confirmed API Endpoints (live-tested, August 2025)

See `docs/api-reference.md` for full details.

### Account credit
- `GET /account-entries?filter-person={pid}&balance=true&limit=1&start=-1`
- Returns `[{id, person, amount, date, notes, balance}]`
- `balance` field confirmed numeric (0.0 when fully paid up)

### Pending payment — NOT AVAILABLE
- Open order `GET /order/{id}` contains no total or line-item fields
- All item/invoice sub-paths return 404
- `PendingPaymentSensor` will remain `unavailable` until resolved

---

## File Structure

```
custom_components/azure_standard/
├── __init__.py          — setup/unload entry, async_update_options listener
├── api.py               — AzureStandardApiClient (all methods corrected)
├── binary_sensor.py     — OrderWindowOpenBinarySensor
├── config_flow.py       — AzureStandardConfigFlow + AzureStandardOptionsFlowHandler
├── const.py             — all constants
├── coordinator.py       — AzureStandardCoordinator + AzureStandardData
├── discovery.py         — ProductStats, ProductDiscoveryEngine
├── entity.py            — AzureStandardEntity base class
├── manifest.json        — HA integration manifest
├── sensor.py            — all sensors incl. AccountCreditSensor + PendingPaymentSensor
├── strings.json         — UI strings (config + options + entity)
└── translations/en.json — English translations (mirrors strings.json)

docs/
├── api-reference.md     — FULLY UPDATED with all confirmed endpoint corrections
├── architecture.md      — developer architecture reference
├── phase9-handoff.md    — this file
└── proposal.md          — full build plan (phases 1–10)

test_credentials.py      — smoke test (12 checks, all passing)
.venv/                   — Python venv with aiohttp
```

---

## Phase 10 Specification

**Goal:** Polish — translations completeness, icons, README, and manifest version bump.

### Tasks

1. **`manifest.json`** — bump `version` to `0.1.0` (first "complete" release).

2. **`strings.json` / `translations/en.json`** — audit all sensor `translation_key` values
   against `entity.sensor` entries. Missing keys produce HA warnings.
   Notably, the dynamic product sensors use hard-coded `_attr_name` rather than
   `translation_key`, which is acceptable but could be migrated.

3. **`README.md`** — create a user-facing README covering:
   - What the integration does
   - Installation (HACS or manual)
   - Configuration (manual mode vs account mode)
   - Sensor reference table
   - Known limitations (no delivery date, no open-order total)

4. **`hacs.json`** — add HACS metadata file for eventual HACS submission:
   ```json
   {
     "name": "Azure Standard",
     "render_readme": true
   }
   ```

5. **Icons** — add `icon.png` and `icon@2x.png` (256×256 px) to
   `custom_components/azure_standard/` if desired for the HA integrations list.

6. **`architecture.md`** — update to reflect phases 7–9 additions (product sensors,
   options flow, account sensors).

---

## Test Command

```bash
cd /Users/seancrow/Forgejo/AzureStandard_Intigration
AZ_EMAIL=b52src@gmail.com AZ_PASSWORD='P@$790rd052' .venv/bin/python3 test_credentials.py
```

All 12 checks currently pass.

## Syntax check command

```bash
.venv/bin/python3 -m py_compile \
  custom_components/azure_standard/api.py \
  custom_components/azure_standard/coordinator.py \
  custom_components/azure_standard/config_flow.py \
  custom_components/azure_standard/sensor.py \
  custom_components/azure_standard/const.py \
  custom_components/azure_standard/discovery.py
```
