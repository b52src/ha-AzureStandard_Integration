# Integration Architecture — Developer Reference

## File Map

```
custom_components/azure_standard/
├── __init__.py               # async_setup_entry / async_unload_entry
├── manifest.json             # domain, version, HA version requirement
├── config_flow.py            # all config + options flow steps (incl. options/product mgmt)
├── const.py                  # constants, URLs, default values
├── api.py                    # AzureStandardApiClient (aiohttp, cookie auth)
├── coordinator.py            # DataUpdateCoordinator subclass
├── discovery.py              # ProductDiscoveryEngine + ProductStats
├── sensor.py                 # all sensor entities (static + dynamic product/list sensors)
├── binary_sensor.py          # order window + on-sale binary sensors
├── entity.py                 # AzureStandardEntity base class
├── icon.png                  # 256×256 integration icon (HA integrations list)
├── icon@2x.png               # 512×512 HiDPI icon
├── strings.json              # translatable UI strings
└── translations/
    └── en.json
```

---

## Module Responsibilities

### `api.py` — AzureStandardApiClient

Single class handling all HTTP communication. No business logic — just fetch and return raw dicts.

```python
class AzureStandardApiClient:
    BASE_URL = "https://api.azurestandard.com"

    # Public (no auth)
    async def get_drop(self, drop_id: int) -> dict
    async def get_drops(self) -> list[dict]
    async def get_product(self, product_id: int) -> dict
    async def get_products_by_category(self, category_id: int, limit: int = 50) -> list[dict]
    async def get_product_price(self, packaging_code: str) -> float | None

    # Auth-required
    async def login(self, email: str, password: str) -> bool
    async def logout(self) -> None
    async def validate_session(self) -> bool
    async def get_session(self) -> dict
    async def get_person(self, person_id: int) -> dict
    async def get_ordered_products(self) -> list[dict]
    async def get_orders(self) -> list[dict]
    async def get_order(self, order_id: int) -> dict
    async def get_product_lists(self) -> list[dict]
    async def get_account_entries(self) -> list[dict]
    async def get_spend_metrics(self) -> dict
    async def get_pending_payments(self) -> dict
```

Auth mechanism: `aiohttp.CookieJar` persisted in the coordinator. On `aiohttp.ClientResponseError` with status 401: call `login()` once, retry, then raise `UpdateFailed` if still failing.

---

### `coordinator.py` — AzureStandardCoordinator

Subclasses `DataUpdateCoordinator`. Holds two separate update intervals:

- **Public data** (drop, prices) — `timedelta(hours=6)`
- **Account data** (orders, lists, products, credit) — multiple intervals managed via timestamps

```python
@dataclass
class AzureStandardData:
    # Public
    drop: dict | None
    next_cutoff: date | None
    delivery_date: date | None

    # Account (None if mode=manual or not yet fetched)
    active_order: dict | None
    orders: list[dict]
    product_lists: list[dict]
    ordered_products: list[dict]
    account_credit: float | None
    pending_payment: float | None

    # Discovery
    product_stats: dict[str, ProductStats]        # keyed by packaging_code
    suggested_products: list[ProductStats]        # pending user approval
    tracked_products: list[str]                   # approved packaging codes
    newly_confirmed_products: list[str]           # codes to spawn entities for this update
```

The coordinator holds a dict of `async_add_entities` callbacks registered by each platform (`sensor.py`, `binary_sensor.py`) via `coordinator.register_platform_callback(platform, callback)`. When `newly_confirmed_products` is non-empty, those callbacks are invoked to create entities live.

---

### `discovery.py` — ProductDiscoveryEngine

Pure logic — no HA imports except `homeassistant.helpers.storage` for persistence.

```python
class ProductDiscoveryEngine:
    MIN_PURCHASE_COUNT: int = 3
    MIN_DATE_SPAN_DAYS: int = 30
    SALE_THRESHOLD: float = 0.95
    PRICE_HISTORY_DAYS: int = 90

    def analyze(
        self,
        ordered_products: list[dict],
        current_prices: dict[str, float],    # packaging_code → current_price
        already_tracked: set[str],           # codes already having sensors
    ) -> tuple[list[ProductStats], list[ProductStats]]:
        """Returns (suggestions, updated_tracked_stats)."""
        ...

    def _compute_interval(
        self, first_ordered: date, last_ordered: date, total_orders: int
    ) -> float | None:
        """Mean days between orders. Returns None if < 2 orders or span < MIN_DATE_SPAN_DAYS."""
        if total_orders < 2:
            return None
        span = (last_ordered - first_ordered).days
        if span < self.MIN_DATE_SPAN_DAYS:
            return None
        return span / (total_orders - 1)

    def _is_on_sale(self, current_price: float, price_history: list[float]) -> tuple[bool, float | None]:
        """Returns (is_on_sale, discount_pct)."""
        if len(price_history) < 3:
            return False, None
        avg = sum(price_history) / len(price_history)
        if avg == 0:
            return False, None
        ratio = current_price / avg
        discount = (1 - ratio) * 100
        return ratio < self.SALE_THRESHOLD, round(discount, 1) if ratio < self.SALE_THRESHOLD else None
```

Price history is persisted via `homeassistant.helpers.storage.Store` under key `azure_standard.price_history`. Shape:

```json
{
  "CT123": [["2025-06-01", 3.49], ["2025-07-01", 3.49], ["2025-08-01", 2.99]],
  "OO456": [["2025-05-15", 12.99], ["2025-07-15", 10.99]]
}
```

---

### `config_flow.py` — ConfigFlow + OptionsFlowHandler

#### ConfigFlow steps

```
async_step_user
  Shows: "Setup mode" radio — Manual | Account Login
  ↓
  ├─ async_step_manual
  │    Shows: Drop ID (number input), optional friendly name
  │    Creates entry: {mode: "manual", drop_id: N, name: "..."}
  │
  └─ async_step_account
       Shows: Email, Password
       Action: validates login via api.login()
       Errors: "invalid_auth" on failure
       ↓
       async_step_drop_confirm
         Shows: Detected drop name + ID (from /session → /person/{id})
                Option to override drop ID manually
         Creates entry: {mode: "account", email: "...", drop_id: N, ...}
```

#### OptionsFlowHandler steps

```
async_step_init
  Shows: Email/password re-auth, drop override, discovery on/off, min_purchase_count slider
  ↓
  async_step_products  (only shown in account mode)
    Shows: Checkbox table
      Columns: Product Name | Code | Orders | Avg Interval | Current Price | On Sale | Track
      Pre-checked: already tracked
      New suggestions: pre-checked by default
    Action: saves tracked_products list to entry options
            newly confirmed codes trigger entity creation on next coordinator update
```

---

### `sensor.py` — Sensor Entities

**Static sensors** (created once at setup):
- `NextCutoffSensor`
- `DaysUntilCutoffSensor`
- `DropNameSensor`
- `DeliveryDateSensor`
- `ActiveOrderStatusSensor` *(account mode)*
- `ActiveOrderItemCountSensor` *(account mode)*
- `ActiveOrderTotalSensor` *(account mode)*
- `LastOrderDateSensor` *(account mode)*
- `AccountCreditSensor` *(account mode)* — reads `coordinator.data.account_credit`; `device_class=MONETARY`
- `PendingPaymentSensor` *(account mode)* — currently `unavailable`; no API endpoint exposes open-order totals

**Dynamic sensors** (one set per shopping list, account mode):
- `ShoppingListSensor` — unique_id includes `list_uid`; state = item count

**Dynamic sensors** (one set per tracked product, account mode):
- `ProductLastOrderedSensor`
- `ProductTimesOrderedSensor`
- `ProductDaysSinceSensor`
- `ProductReorderDueSensor`

All extend `AzureStandardEntity` which extends `CoordinatorEntity`.
Product sensors additionally extend `_ProductSensorBase` which uses a separate `DeviceInfo`
per packaging code, so each tracked product appears as its own device in HA.

---

### `binary_sensor.py`

**Static:**
- `OrderWindowOpenBinarySensor` — `is_on` when `now() < next_cutoff`

**Dynamic (one per tracked product, account mode):**
- `ProductOnSaleBinarySensor` — `is_on` when `product_stats[code].is_on_sale`
  Extra state attributes: `current_price`, `average_price`, `discount_percent`, `price_history`

---

### `entity.py` — AzureStandardEntity

```python
class AzureStandardEntity(CoordinatorEntity[AzureStandardCoordinator]):
    """Base entity for all Azure Standard entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="Azure Standard",
            manufacturer="Azure Standard",
            model="Co-op Delivery",
            configuration_url="https://www.azurestandard.com",
        )
```

Product-specific entities use a separate `DeviceInfo` per product so each product appears as its own device in HA.

---

## Constants (const.py)

```python
DOMAIN = "azure_standard"
API_BASE = "https://api.azurestandard.com"

# Config entry keys
CONF_MODE = "mode"
CONF_DROP_ID = "drop_id"
CONF_EMAIL = "email"
CONF_SESSION_COOKIE = "session_cookie"   # stored in entry.data, not options
CONF_TRACKED_PRODUCTS = "tracked_products"
CONF_DISCOVERY_ENABLED = "discovery_enabled"
CONF_MIN_PURCHASE_COUNT = "min_purchase_count"
CONF_SALE_THRESHOLD = "sale_threshold"

# Modes
MODE_MANUAL = "manual"
MODE_ACCOUNT = "account"

# Defaults
DEFAULT_MIN_PURCHASE_COUNT = 3
DEFAULT_SALE_THRESHOLD = 0.95
DEFAULT_PRICE_HISTORY_DAYS = 90

# Poll intervals
SCAN_INTERVAL_PUBLIC = timedelta(hours=6)
SCAN_INTERVAL_ORDERS = timedelta(hours=1)
SCAN_INTERVAL_LISTS = timedelta(minutes=30)
SCAN_INTERVAL_HISTORY = timedelta(hours=24)
SCAN_INTERVAL_SESSION = timedelta(hours=12)

# Storage keys
STORAGE_KEY_PRICE_HISTORY = f"{DOMAIN}.price_history"
STORAGE_VERSION = 1
```

---

## HA Storage Layout

The price history for on-sale detection is persisted via `homeassistant.helpers.storage`:

```
.storage/azure_standard.price_history
{
  "version": 1,
  "data": {
    "CT123": [["2025-06-01", 3.49], ["2025-07-01", 3.49], ["2025-08-01", 2.99]],
    "OO456": [["2025-05-15", 12.99], ["2025-07-15", 10.99]]
  }
}
```

Price snapshots are appended on every 6-hour coordinator update and pruned to the last `PRICE_HISTORY_DAYS` days.

---

## Sequence: First-run account setup

```
1. User adds integration → config flow → async_step_account
2. api.login(email, password) → session cookie stored in entry.data
3. api.get_session() → person ID extracted
4. api.get_person(person_id) → default drop_id extracted
5. async_step_drop_confirm → user confirms drop
6. async_create_entry → HA calls async_setup_entry
7. Coordinator first refresh:
   a. api.get_drop(drop_id) → next_cutoff, delivery_date computed
   b. api.get_ordered_products() → ProductDiscoveryEngine.analyze()
   c. Suggestions with count >= 3 → HA persistent notification raised
   d. Static entities registered and available (incl. AccountCreditSensor)
   e. api.get_account_entries() → account_credit populated
8. User opens options → async_step_products → checks boxes
9. Coordinator update → newly_confirmed_products populated
10. async_add_entities called for product sensor groups → live in HA
```

---

## Phase History

| Phase | Description |
|---|---|
| 1 | Scaffold: manifest, const, __init__, entity, api, strings |
| 2 | Drop & cutoff sensors: NextCutoff, DaysUntilCutoff, DropName, DeliveryDate |
| 3 | Account login: config flow (mode select, manual, account, drop_confirm, reauth) |
| 4 | Order sensors: ActiveOrderStatus, ActiveOrderItemCount, ActiveOrderTotal, LastOrderDate |
| 5 | Shopping list sensors: ShoppingListSensor (dynamic, one per list) |
| 6 | Product discovery engine: discovery.py, ProductStats, HA persistent notification |
| 7 | Per-product sensor groups: last_ordered, times_ordered, days_since, reorder_due |
| 8 | Options flow product management: checkbox UI, dynamic entity creation via callback registry |
| 9 | Account sensors: AccountCreditSensor + PendingPaymentSensor; icons added |
| 10 | Polish: README, hacs.json, architecture update, translations audit |
