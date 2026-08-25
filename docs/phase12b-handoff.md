# Azure Standard Integration — Phase 12b Handoff Context

## Goal

Phase 12b wires real Azure Standard deep-link URLs into all link-out buttons
in the sidebar panel. Every button now opens the exact list, order, or product
page on azurestandard.com instead of a generic landing page.

---

## Build Plan Status

| Phase | Description | Status |
|---|---|---|
| 1–10 | Core sensors, account, polish | ✅ Done |
| 11 | Sidebar panel (Web Component) | ✅ Done |
| 12 | Panel tabs + startup fix | ✅ Done |
| **12b** | **Real deep-link URLs in panel** | **✅ Done** |

---

## What Was Done in Phase 12b

### New attributes on `ProductLastOrderedSensor`

[`sensor.py`](../custom_components/azure_standard/sensor.py) —
`ProductLastOrderedSensor.extra_state_attributes` now returns:

```python
{
    "product_id": stats.product_id,   # int, from ProductStats.product_id
    "code":       stats.code,          # str, packaging code e.g. "SW033"
    "last_order_id": stats.last_order_id,  # int or None
}
```

These were already in `ProductStats` (populated from the
`ordered-packaged-products` API) but not previously exposed to the panel.
No new API calls required.

---

### Panel link-out URLs ([`azure-standard-panel.js`](../custom_components/azure_standard/www/azure-standard-panel.js))

Three module-level constants replace the single `AZURE_STANDARD_URL` variable
used for all links:

```js
const AZURE_STANDARD_URL  = "https://www.azurestandard.com";
const _LISTS_BASE   = `${AZURE_STANDARD_URL}/my-account/lists`;
const _ORDERS_BASE  = `${AZURE_STANDARD_URL}/my-account/order`;
const _SHOP_BASE    = `${AZURE_STANDARD_URL}/shop/product`;
```

#### Lists tab

Each list card reads `list_id` from the sensor's state attributes:

```js
const listId  = this._attr(id, "list_id", null);
const listUrl = listId ? `${_LISTS_BASE}/${listId}` : _LISTS_BASE;
```

URL shape: `https://www.azurestandard.com/my-account/lists/1954436`

Falls back to the lists index page if `list_id` is unavailable.

#### Summary + Account tabs — active order link

The active order ID is read from `sensor.azure_standard_active_order_status`'s
`order_id` attribute (already present since Phase 4):

```js
const orderIdRaw = this._attr("sensor.azure_standard_active_order_status", "order_id", null);
const orderLink  = orderId ? `${_ORDERS_BASE}/${orderId}` : null;
```

URL shape: `https://www.azurestandard.com/my-account/order/17393000`

The "View order" button is hidden entirely when `order_id` is unavailable
(manual mode or no active order).

#### Products tab — product name as clickable link

Product names become `<a>` links using `product_id` and `code` from the new
`ProductLastOrderedSensor` attributes:

```js
const productId = this._attr(id, "product_id", null);
const pkgCode   = this._attr(id, "code", code.toUpperCase());
const nameSlug  = name.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
const productLink = `${_SHOP_BASE}/${nameSlug}/${productId}?package=${pkgCode}`;
```

URL shape:
`https://www.azurestandard.com/shop/product/demerara-sugar-natural-turbinado-style/11386?package=SW033`

Falls back to plain text if `product_id` is unavailable.

---

## Files Changed in Phase 12b

```
custom_components/azure_standard/
├── sensor.py            — ProductLastOrderedSensor: added extra_state_attributes
├── manifest.json        — version 0.1.2 → 0.1.3
└── www/
    └── azure-standard-panel.js   — real deep-link URLs for lists, orders, products

CHANGELOG.md             — 0.1.3 entry added
docs/phase12b-handoff.md ← this file
```

---

## Test Steps

1. Deploy updated `custom_components/azure_standard/` and restart HA.
2. Open the Azure Standard sidebar panel.
3. **Lists tab** — each "Edit on Azure Standard ↗" button should open
   `https://www.azurestandard.com/my-account/lists/<your-list-id>`.
4. **Summary tab** — if an active order exists, a "View order on Azure Standard ↗"
   button should appear linking to `…/my-account/order/<order-id>`.
5. **Products tab** — each product name should be a green underlined link opening
   `…/shop/product/<slug>/<product-id>?package=<code>`.
6. **Account tab** — "View active order ↗" deep-links to the same order URL.
7. Verify in `Developer Tools → States` that
   `sensor.azure_standard_<code>_last_ordered` entities now have
   `product_id`, `code`, and `last_order_id` in their attributes.

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
