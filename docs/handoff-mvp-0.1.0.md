# Handoff — Azure Standard Integration v0.1.0 MVP

## Purpose
This document is the complete handoff for the next task: fix two known bugs,
cut a `0.1.0` MVP release, then work through the planned phases to build a
full-featured integration.

---

## Repo & tooling

| Item | Value |
|---|---|
| Forgejo repo | `https://forgejo.crow-nest.xyz/scrow/AzureStandard_Intigration` |
| Current version | `0.0.7` (see `manifest.json` and `CHANGELOG.md`) |
| Target MVP version | `0.1.0` |
| Runtime | Python 3.12+, Home Assistant 2024.1.0+ |
| No extra pip deps | `requirements: []` in `manifest.json` |

---

## Current state (as of 0.0.7)

The integration is functional. The following files contain working code:

```
custom_components/azure_standard/
├── __init__.py
├── api.py            # AzureStandardApiClient — all confirmed endpoints
├── binary_sensor.py  # order_window_open, order_placed
├── config_flow.py    # manual + account paths, reauth, options flow
├── const.py
├── coordinator.py    # AzureStandardData dataclass + coordinator
├── discovery.py      # ProductDiscoveryEngine + ProductStats
├── entity.py
├── manifest.json
├── sensor.py         # all sensors including ShoppingListSensor + product sensors
├── strings.json
└── translations/en.json
```

### What works
- Drop lookup via paginated `GET /drops` (direct `GET /drops/{id}` returns 404)
- Next cutoff date + days-until-cutoff sensors
- Delivery date sensor (raw string e.g. "Week of Sep 13")
- Full account auth flow: login, cookie persistence, silent reauth
- Active order status / item count / total sensors
- Order placed binary sensor
- Shopping list sensors (dynamically created per list)
- Product discovery engine — `ProductStats` keyed by packaging code
- Per-product sensors: last ordered, times ordered, days since, reorder due
- Account credit + pending payment sensors

---

## Bug 1 — Pickup week/date missing

### Problem
The `delivery_date` field in `AzureStandardData` stores the raw delivery
**string** from `estimatedDelivery` (e.g. `"Week of Sep 13"`). There is no
structured pickup date or week sensors. The sensor `DeliveryDateSensor` exists
but just shows this string. The user wants:

- `sensor.azure_standard_pickup_date` — ISO date, e.g. `2026-09-13`
- `sensor.azure_standard_pickup_week` — ISO week string, e.g. `2026-W37`
- `sensor.azure_standard_days_until_pickup` — integer countdown

### Root cause
`_find_next_cutoff()` in `coordinator.py` only reads `estimatedDelivery` as a
raw string. The drop API also returns `trip-date` (an ISO date field) alongside
`cutoff` and `estimatedDelivery` inside each `order-frequency` entry.

### Fix — 3 files

**1. `coordinator.py` — `AzureStandardData` dataclass**

Add three new fields alongside `delivery_date`:
```python
pickup_date: date | None = None        # parsed ISO date from trip-date
pickup_week: str | None = None         # e.g. "2026-W37"
days_until_pickup: int | None = None   # (pickup_date - today).days
```

**2. `coordinator.py` — `_find_next_cutoff()`**

Rename to `_find_next_schedule()`, change return type to also include the
structured pickup date. Inside the `order-frequency` loop also read:
```python
trip_date_raw = freq.get("trip-date") or freq.get("tripDate") or freq.get("trip_date")
trip_date = _parse_date(trip_date_raw)
```
Store `trip_date` alongside `best_delivery`. Return a 3-tuple:
`(best_cutoff, best_delivery, best_trip_date)`.

Then in `_async_update_data()` where `_find_next_cutoff` is called:
```python
next_cutoff, delivery_date, pickup_date = _find_next_schedule(drop)
today = date.today()
result = AzureStandardData(
    drop=drop,
    next_cutoff=next_cutoff,
    delivery_date=delivery_date,
    pickup_date=pickup_date,
    pickup_week=pickup_date.strftime("%%Y-W%%V") if pickup_date else None,
    days_until_pickup=(pickup_date - today).days if pickup_date else None,
)
```

**3. `sensor.py` — add three new sensor classes + register them**

Follow the exact pattern of `DeliveryDateSensor`. Add after it:

```python
class PickupDateSensor(AzureStandardEntity, SensorEntity):
    _attr_translation_key = "pickup_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:truck-check"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pickup_date"

    @property
    def native_value(self):
        return self.coordinator.data.pickup_date if self.coordinator.data else None


class PickupWeekSensor(AzureStandardEntity, SensorEntity):
    _attr_translation_key = "pickup_week"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pickup_week"

    @property
    def native_value(self):
        return self.coordinator.data.pickup_week if self.coordinator.data else None


class DaysUntilPickupSensor(AzureStandardEntity, SensorEntity):
    _attr_translation_key = "days_until_pickup"
    _attr_native_unit_of_measurement = "days"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_days_until_pickup"

    @property
    def native_value(self):
        return self.coordinator.data.days_until_pickup if self.coordinator.data else None
```

In `async_setup_entry` in `sensor.py`, add the three new sensors to the base
entity list that is registered on every setup (alongside `NextCutoffSensor`,
`DaysUntilCutoffSensor`, etc.):
```python
PickupDateSensor(coordinator),
PickupWeekSensor(coordinator),
DaysUntilPickupSensor(coordinator),
```

**4. `strings.json` + `translations/en.json`**

Add translation keys `pickup_date`, `pickup_week`, `days_until_pickup` under
`entity.sensor` with friendly names "Pickup date", "Pickup week", "Days until
pickup".

> **Note:** If the drop API does not return `trip-date` for your drop, the three
> sensors will show `Unknown` (None state). That is correct behavior — the
> delivery string sensor (`delivery_date`) remains as the fallback.

---

## Bug 2 — Product tracking shows SKU codes instead of names

### Problem
`config_flow.py` `AzureStandardOptionsFlowHandler.async_step_init()` builds
the candidate list from `coordinator.data.product_stats` using only the
packaging code:

```python
# Current (line 103-108 in config_flow.py)
candidate_options = [
    SelectOptionDict(
        value=s.code,
        label=f"{s.code} — ordered {s.order_count}× (last: {s.last_ordered})",
    )
    for s in candidates if s.is_candidate
]
```

User sees `"SW033 — ordered 20× (last: 2026-06-19)"` but wants
`"Raw Wildflower Honey — ordered 20× (last: 2026-06-19)"`.

Sensor entity names also use the code: `_attr_name = f"{code} {self._metric...}"`.

### What the API provides
`ProductStats` already stores `product_id` (the `productId` field from the
ordered-products API). `api.py` already has `get_product(product_id)` which
calls `GET /products/{id}`. The product response includes a `name` field.

### Fix — 3 files

**1. `discovery.py` — add `name` field to `ProductStats`**

```python
@dataclass
class ProductStats:
    code: str
    product_id: int
    order_count: int
    last_ordered: date | None
    last_order_id: int | None
    days_since_last_order: int | None
    is_candidate: bool
    name: str = ""          # ← add this; empty string until resolved
```

**2. `coordinator.py` — resolve product names during history fetch**

Inside `_async_update_data()`, after `stats = engine.analyze(ordered)`, add a
name-resolution pass. Resolve names for candidates only (to limit API calls):

```python
# Resolve product names for candidates (one GET /products/{id} per new code)
resolved_names: dict[str, str] = {}
if self.data:
    # Preserve previously resolved names to avoid re-fetching
    for code, prev in self.data.product_stats.items():
        if prev.name:
            resolved_names[code] = prev.name

for s in stats:
    if not s.is_candidate:
        continue
    if s.product_id and s.code not in resolved_names:
        try:
            prod = await self.client.get_product(s.product_id)
            name = str(prod.get("name") or prod.get("productName") or "").strip()
            if name:
                resolved_names[s.code] = name
        except Exception:  # noqa: BLE001
            pass  # name stays empty; code is shown as fallback

for s in stats:
    s.name = resolved_names.get(s.code, "")

result.product_stats = {s.code: s for s in stats}
```

This resolves names **once per code** and preserves them across coordinator
refreshes. The cache lives in the in-memory previous coordinator data.

**3. `config_flow.py` — use name in the label**

```python
# Updated (config_flow.py ~line 103-108)
candidate_options = [
    SelectOptionDict(
        value=s.code,
        label=(
            f"{s.name or s.code} — ordered {s.order_count}× (last: {s.last_ordered})"
        ),
    )
    for s in candidates if s.is_candidate
]
```

`s.name` falls back to `s.code` if name resolution hasn't run yet (first
coordinator update, no history cached). Subsequent opens of the options dialog
will show the resolved name.

**4. `sensor.py` — use name in product sensor entity name**

In `_ProductSensorBase.__init__`:
```python
# Current
self._attr_name = f"{code} {self._metric.replace('_', ' ').title()}"

# Updated
stats = coordinator.data.product_stats.get(code) if coordinator.data else None
display = (stats.name if stats and stats.name else code)
self._attr_name = f"{display} {self._metric.replace('_', ' ').title()}"
```

> **Note on entity_id:** HA derives the entity_id from the name at creation
> time. Since `unique_id` is already set (and uses the code, not the name),
> existing sensors will keep their entity_id even if the name changes. New
> sensors created after name resolution will get a friendlier entity_id if
> names are already resolved when the platform sets up.

---

## 0.1.0 MVP Release checklist

After both bugs are fixed:

1. Bump `manifest.json` version → `"version": "0.1.0"`
2. Add a `CHANGELOG.md` entry for `0.1.0`:
   ```
   ## [0.1.0] - YYYY-MM-DD

   ### Fixed
   - Pickup week/date sensors now populated from `trip-date` field in drop API
   - Product tracking options flow shows product names instead of SKU codes
   - Product sensor entity names use product name instead of code

   ### Added
   - `sensor.azure_standard_pickup_date` — ISO date of next drop pickup
   - `sensor.azure_standard_pickup_week` — ISO week string (e.g. 2026-W37)
   - `sensor.azure_standard_days_until_pickup` — integer countdown to pickup
   ```
3. Tag the commit `v0.1.0` in the Forgejo repo.
4. Verify in a real HA instance:
   - Pickup date sensor shows a date (not Unknown) — or Unknown with a log
     message if `trip-date` is absent from the drop record
   - Options flow shows product names in the checkbox list
   - Product sensor entity names in the HA entity list show product names

---

## Phase roadmap after 0.1.0

These are the planned enhancements after MVP is shipped, in priority order:

### Phase A — Custom panel (WashData-style)
Add a full-screen HA sidebar panel using the same pattern as
[ha_washdata](https://github.com/3dg1luk43/ha_washdata).

Files to add:
```
custom_components/azure_standard/
├── frontend.py           # panel registration + static path serving
├── ws_api.py             # WebSocket command handlers
├── translations/
│   └── panel/
│       └── en.json       # panel UI strings
└── www/
    └── az-standard-panel.js   # compiled Lit/vanilla Web Component
```

`manifest.json` needs:
```json
"after_dependencies": ["frontend", "http", "lovelace"]
```

Panel tabs: **Overview** (cutoff / pickup countdown, order status, credit
balance) · **Orders** (history list) · **Shopping Lists** · **Tracked Products**
(product cards with order history) · **Settings** (options flow mirrored in
panel).

Backend pattern: `frontend.async_register_built_in_panel(hass,
component_name="custom", ...)` in `__init__.py`'s `async_setup_entry`. All
panel↔backend comms via `@websocket_api.websocket_command` handlers in
`ws_api.py`. Teardown via `frontend.async_remove_panel` in
`async_unload_entry`. Effort: ~2 hrs Python, ~10–12 hrs frontend JS.

### Phase B — Pickup date fallback parsing
If `trip-date` is absent from the drop record, attempt to parse the
`estimatedDelivery` string (e.g. `"Week of Sep 13"`) to extract an
approximate date. Use the year from the next cutoff date to resolve the month.
This is a best-effort heuristic — log a warning and leave the sensor `Unknown`
if parsing fails.

### Phase C — Per-product reorder threshold config
`_REORDER_THRESHOLD_DAYS = 30` is currently hardcoded in `sensor.py`. Add a
per-product config field to the options flow and use it in
`ProductReorderDueSensor`.

### Phase D — `hacs.json` + HACS store listing
Ensure `hacs.json` is correct (already present, verify fields). Publish the
repo to the HACS default store or as a custom repository.

### Phase E — Spend metrics sensor
Wire up `api.get_spend_metrics()` (already implemented) to a
`sensor.azure_standard_total_spend` and `sensor.azure_standard_total_orders`
entity. Fetch on the 24 h history interval alongside `account_credit`.

---

## Key design decisions to preserve

| Decision | Reason |
|---|---|
| `unique_id` uses code (not name) for product sensors | Name can change; code is stable. Entity history is preserved. |
| `GET /drops/{id}` is **not used** — paginated list instead | Direct endpoint returns 404. See `api.get_drop_from_list()`. |
| Login payload uses `username` field (not `email`) | Confirmed from live 400 error body. See `api.login()` docstring. |
| Ordered products endpoint is `GET /person/{personId}/ordered-packaged-products` | Not `/ordered-packaged-products` — person-scoped. |
| Product lists endpoint is `/v2/products/product_lists?customerNumber={id}` | The `/v2/` prefix is required; without it the endpoint returns 404. |
| `delivery_date` stored as raw string, not a parsed date | API returns week-range strings, not ISO dates. |
| Session cookie key is `id`, domain `api.azurestandard.com` | See `api.py` `_SESSION_COOKIE_NAME`. |
