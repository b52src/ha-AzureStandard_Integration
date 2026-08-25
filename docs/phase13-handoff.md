# Phase 13 Handoff — Price History Sparklines (v0.1.4)

## What changed

### `coordinator.py`
- Added `_PRICE_HISTORY_MAX = 12` module constant — caps the rolling window.
- Added `price_history: dict[str, list[float]]` field to `AzureStandardData`
  (keyed by packaging code, values are lists of floats oldest-first).
- Added `self._price_history: dict[str, list[float]] = {}` instance variable on
  `AzureStandardCoordinator.__init__` — this persists across refreshes and is
  never reset between coordinator updates.
- Inside the `_history_due()` block (daily cadence), after name resolution, the
  coordinator iterates every tracked product code and calls
  `self.client.get_product_price(code)`. Each non-None result is appended to the
  rolling list; entries beyond `_PRICE_HISTORY_MAX` are dropped from the front.
- `result.price_history` is assigned a shallow copy of `self._price_history` at
  the end of the block.
- The error and non-due fallback branches carry `self.data.price_history` forward
  so sensors always see the latest available history.

### `sensor.py` — `ProductLastOrderedSensor.extra_state_attributes`
Added two new attributes alongside the existing `product_id` / `code` / `last_order_id`:

| Attribute | Type | Notes |
|---|---|---|
| `last_price` | `float \| None` | Last entry in `price_history`, or `null` |
| `price_history` | `list[float]` | Up to 12 floats, oldest first; empty list until first fetch |

### `www/azure-standard-panel.js`
- Version comment updated to `Phase 13 / v0.1.4`.
- `_sparkline(history)` helper added — pure SVG, no external deps:
  - Returns `"—"` when `history.length < 2`.
  - Renders a 40×20 px `<polyline>` with `stroke="#16a34a"` (green).
  - Adds a 2 px filled `<circle>` at the rightmost (current) point.
  - Scales both axes to fit the full `[min, max]` range; flat history
    (all prices equal) uses `range = 1` to avoid divide-by-zero.
- Products table has a new **"Price"** column between "Last ordered" and "Times".
  Each cell contains either the sparkline SVG or `"—"`.
- Added `.sparkline-cell` CSS rule: `text-align: center; padding: 4px 8px`.

### `manifest.json`
- `"version"` bumped from `"0.1.3"` to `"0.1.4"`.

### `CHANGELOG.md`
- `[0.1.4]` entry added at the top.

---

## Data shape

```json
// sensor.azure_standard_<code>_last_ordered  attributes
{
  "product_id": 28776,
  "code": "BK603",
  "last_order_id": 13624820,
  "last_price": 4.99,
  "price_history": [4.79, 4.89, 4.99]
}
```

`price_history` grows by one entry per daily coordinator refresh, up to 12.
In-memory only — resets if HA restarts (no `.storage` persistence in this phase).

---

## How price is fetched

`api.get_product_price(packaging_code)` calls:
```
GET /products?packagingCode=<code>
```
Returns the first match's packaging list, finds the entry whose `code` matches,
and returns `float(pkg["price"])`. Returns `None` on any error or no-match.

---

## Test steps

1. **Pull v0.1.4** and reload the integration (or restart HA).
2. Open the sidebar panel → **Products tab**.
3. The "Price" column is now visible. On first load it shows `—` for all products
   (no history yet — price is fetched at the daily `SCAN_INTERVAL_HISTORY` cadence).
4. **Force an immediate history refresh** by restarting HA or temporarily lowering
   `SCAN_INTERVAL_HISTORY` in `const.py` to `timedelta(minutes=1)` for testing.
5. After one refresh cycle, the `last_price` and `price_history` attributes should
   appear on the `*_last_ordered` sensor in Developer Tools → States.
6. After **two or more** refresh cycles the sparkline SVG renders in the panel.
7. Verify the sparkline dots align with the price values in the attribute.

---

## Known limitations / next steps

- Price history is **in-memory only** and resets on HA restart. A future phase
  can persist it via `homeassistant.helpers.storage.Store` using
  `STORAGE_KEY_PRICE_HISTORY` (already defined in `const.py`).
- Price is sampled once per `SCAN_INTERVAL_HISTORY` (default 24 h). Users with
  few tracked products won't see a meaningful sparkline for several days.
- The sparkline shows no price labels or axis ticks. Hover tooltip support could
  be added in a future phase.

---

## Release

```bash
fj release create "v0.1.4" --tag v0.1.4 --body "..."
fj release list   # confirm v0.1.4 appears
```

Tag `v0.1.4` and the Forgejo release were created as part of this phase.
