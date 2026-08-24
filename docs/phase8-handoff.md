# Azure Standard Integration — Phase 8 Handoff Context

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
| **8** | **Options flow product management: checkbox UI, dynamic entity creation** | **⬅ NEXT** |
| 9 | Account sensors: AccountCredit, PendingPayment | Pending |
| 10 | Polish: translations, icons, README | Pending |

---

## What Was Done in Phase 8

Phase 8 added `AzureStandardOptionsFlowHandler` to `config_flow.py`. Tapping the
**Configure** button in the HA integrations UI now presents:

1. **Tracked products** — a multi-select list showing every `ProductStats` candidate
   (those with `is_candidate=True`, i.e. `order_count >= min_purchase_count`), sorted
   by order count descending. Each option label includes the code, order count, and
   last-ordered date.
2. **Minimum order count** — a number input (default 3) controlling which products
   appear as candidates on the next history refresh.

Saving the form writes to `entry.options`:
```python
{
    "tracked_products": ["SW033", "CT123", ...],
    "min_purchase_count": 3,
}
```

This triggers `async_update_options` in `__init__.py`, which reloads the config entry.
On reload the coordinator's `_async_update_data` picks up the new `tracked_products`
list and calls `_make_product_sensors` for any newly-tracked codes.

**Fallback**: if `coordinator.data.product_stats` is empty (history not yet fetched),
the options form shows only the `min_purchase_count` field with a descriptive note.

---

## Files Changed in Phase 8

```
custom_components/azure_standard/
├── config_flow.py       — AzureStandardOptionsFlowHandler (new class) +
│                          async_get_options_flow static method on ConfigFlow
├── strings.json         — added top-level "options" block
└── translations/en.json — added top-level "options" block (mirrors strings.json)
```

---

## Confirmed API Endpoints (live-tested, August 2025)

See `docs/api-reference.md` for full details.

### Ordered Products
- `GET /person/{personId}/ordered-packaged-products`
- Item shape: `{code, productId, orderCount, lastOrderInvoiceDate, lastOrderId}`
- 124 products confirmed for personId=1674720
- Live example: `code=SW033, orderCount=20, lastOrderInvoiceDate="2026-06-19"`

### Shopping Lists (v2 base URL)
- `GET /v2/products/product_lists?customerNumber={personId}` → list metadata
- `GET /v2/products/product_lists/{listId}/items` → items with `{productCode, name, slug, quantity, isPinned}`

---

## File Structure

```
custom_components/azure_standard/
├── __init__.py          — setup/unload entry, async_update_options listener
├── api.py               — AzureStandardApiClient (all methods corrected)
├── binary_sensor.py     — OrderWindowOpenBinarySensor
├── config_flow.py       — AzureStandardConfigFlow + AzureStandardOptionsFlowHandler
├── const.py             — all constants including CONF_TRACKED_PRODUCTS, CONF_MIN_PURCHASE_COUNT
├── coordinator.py       — AzureStandardCoordinator + AzureStandardData
├── discovery.py         — ProductStats, ProductDiscoveryEngine
├── entity.py            — AzureStandardEntity base class
├── manifest.json        — HA integration manifest (version 0.0.3)
├── sensor.py            — all sensors incl. ShoppingListSensor + 4 product sensor classes
├── strings.json         — UI strings (config + options + entity)
└── translations/en.json — English translations (mirrors strings.json)

docs/
├── api-reference.md     — FULLY UPDATED with all confirmed endpoint corrections
├── architecture.md      — developer architecture reference
├── phase8-handoff.md    — this file
└── proposal.md          — full build plan (phases 1–10)

test_credentials.py      — smoke test (11 checks, all passing)
.venv/                   — Python venv with aiohttp
```

---

## Key Implementation Details

### Options flow — `AzureStandardOptionsFlowHandler`

```python
class AzureStandardOptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None) -> FlowResult:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        # Builds SelectOptionDict list from coordinator.data.product_stats
        # Renders SelectSelector (multi, list mode) + NumberSelector
        # On submit: async_create_entry(data={CONF_TRACKED_PRODUCTS, CONF_MIN_PURCHASE_COUNT})
```

Saving fires `async_update_options` → `hass.config_entries.async_reload(entry_id)`.

### How newly-tracked codes become entities

On reload, `coordinator._async_update_data` runs `_history_due()` (first run ≡ True).
After populating `product_stats`, it compares `tracked` from `entry.options` against
`self._known_product_codes`. Any `new_codes` present in `product_stats` get
`_make_product_sensors(coordinator, code)` called and entities are registered via
`self._platform_callbacks[Platform.SENSOR](new_entities)`.

---

## Phase 9 Specification

**Goal:** Add `AccountCredit` and `PendingPayment` sensors.

### Sensors to add

| Sensor class | unique_id suffix | state | unit | device_class |
|---|---|---|---|---|
| `AccountCreditSensor` | `account_credit` | float | `USD` | `monetary` |
| `PendingPaymentSensor` | `pending_payment` | float | `USD` | `monetary` |

### Data sources

- `AccountCreditSensor.native_value` → `coordinator.data.account_credit`
- `PendingPaymentSensor.native_value` → `coordinator.data.pending_payment`

`account_credit` is already fetched and stored in `AzureStandardData`; it
reads from `GET /account-entries` (the `balance` field, confirmed live).

`pending_payment` is not yet fetched. The endpoint needs to be confirmed:
a likely candidate is `GET /orders?filter-person={pid}&filter-status=open&limit=1`
summing `lineTotal` or `grandTotal` on the open order — but **verify in
`probe_endpoints.py` first** before implementing.

### Implementation approach

1. **`sensor.py`**: Add `AccountCreditSensor` and `PendingPaymentSensor` classes
   inheriting from `_BaseAccountSensor` (or directly from `AzureStandardEntity`).
   Add them to the `entities` list in `async_setup_entry` alongside the existing sensors.

2. **`coordinator.py`**: `pending_payment` field already exists in `AzureStandardData`
   but is never populated. Wire up the correct API call in the orders fetch block
   (piggyback on `_orders_due()`) once the endpoint is confirmed.

3. **`strings.json` / `translations/en.json`**: Add entries under `entity.sensor` for
   `account_credit` and `pending_payment`.

### Test additions

Add check [12] to `test_credentials.py`:
```
[12] Account credit — verify the /account-entries endpoint returns a numeric balance field.
     Print the raw response for inspection.
```

---

## Test Command

```bash
cd /Users/seancrow/Forgejo/AzureStandard_Intigration
AZ_EMAIL=b52src@gmail.com AZ_PASSWORD='P@$790rd052' .venv/bin/python3 test_credentials.py
```

All 11 checks currently pass.

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
