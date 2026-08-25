# Changelog

## [0.1.3] - 2025-08-09

### Added
- **Real link-out URLs** in the sidebar panel — links now deep-link to exact pages
  on the Azure Standard website rather than generic paths:
  - **Lists tab** — each "Edit on Azure Standard ↗" button links to
    `/my-account/lists/{list_id}` using the `list_id` attribute on the list sensor.
  - **Summary & Account tabs** — "View order" button links to
    `/my-account/order/{order_id}` using the `order_id` attribute on the order
    status sensor (shown only when an active order exists).
  - **Products tab** — each product name is a clickable link to
    `/shop/product/{slug}/{product_id}?package={code}` using the new `product_id`
    and `code` attributes added to `ProductLastOrderedSensor`.
- **`product_id`, `code`, `last_order_id` attributes** on
  `ProductLastOrderedSensor` — sourced from `ProductStats`; enables deep-links
  without any extra API calls.

## [0.1.2] - 2025-08-09

### Fixed
- **`register_static_path` AttributeError on startup** — `HomeAssistantHTTP` removed this
  synchronous method in HA 2024.x. Replaced with the async equivalent:
  `await hass.http.async_register_static_paths([StaticPathConfig(...)])`.
  The integration now starts cleanly on current HA releases.

### Changed
- **Sidebar panel redesigned with four tabs** (Phase 12):
  - **Summary** — Drop & Cutoff countdown + Active Order snapshot on one screen.
  - **Lists** — Shopping lists with item previews; each list card has an
    "Edit on Azure Standard ↗" link that opens the site in a new tab.
    No in-panel list editing.
  - **Products** — Tracked products table now includes an **Avg cycle** column
    (estimated days between orders = days_since ÷ (times − 1)). Reorder-due
    products are highlighted in amber; the tab shows a red badge with the count.
  - **Account** — Credit, pending payment, last order date, and a link to the
    Azure Standard order history page.
- **↻ Refresh button** in the panel header triggers `homeassistant.update_entity`
  on the drop-name sensor, forcing a coordinator refresh without a full HA reload.
- Tab selection persists across hass state-change re-renders (no tab-reset on poll).
- Account-only tabs (Lists, Products, Account) are hidden when in manual mode.

## [0.1.1] - 2025-07-20

### Added
- **Sidebar panel** — a dedicated Home Assistant sidebar entry ("Azure Standard", `mdi:sprout` icon) that renders a live dashboard of all integration data without needing a Lovelace card:
  - Drop name, order window status badge, cutoff countdown with urgency colouring
  - Pickup date, pickup week, days until pickup
  - Active order status, item count, order total, last order date, account credit, pending payment (account mode)
  - Shopping lists with inline item previews (account mode)
  - Tracked products table with last ordered, times ordered, days since, and reorder-due highlight (account mode)
- **`www/azure-standard-panel.js`** — self-contained Web Component registered via `panel_custom`; reads entity states live via the `hass` property, no extra API calls.
- **`async_setup`** hook in `__init__.py` — registers `www/` as a static path at `/azure_standard_panel/` so the JS file is served by HA's HTTP server.
- **`frontend` dependency** added to `manifest.json` so HA loads the frontend integration before this one.

## [0.1.0] - 2025-07-19

### Fixed
- **Pickup date/week sensors always `Unknown`** — the `trip-date` field from the drop's `order-frequency` array was never extracted. `_find_next_cutoff` now returns it as a third value; the coordinator derives `pickup_week` (ISO week string, e.g. `2025-W37`) and `days_until_pickup` from it.
- **Product tracking shows raw SKU codes** — the options flow and per-product sensor names now display the human-readable product name (e.g. "Raw Wildflower Honey (SW033)") instead of just the SKU code. Names are resolved via `GET /products/{id}` on first encounter and cached across coordinator updates.

### Added
- **`Pickup date` sensor** (`sensor.azure_standard_pickup_date`) — DATE device class, sourced from `trip-date` in the drop schedule.
- **`Pickup week` sensor** (`sensor.azure_standard_pickup_week`) — ISO week identifier string, e.g. `2025-W37`.
- **`Days until pickup` sensor** (`sensor.azure_standard_days_until_pickup`) — integer countdown from today to the structured pickup date.
- **Product name cache in coordinator** — `_product_name_cache` (dict[product_id → name]) persists for the lifetime of the config entry, so product names are fetched only once per product.

## [0.0.7] - 2025-07-15

### Fixed
- **Delivery date shown as `Unknown`** — `DeliveryDateSensor` used `SensorDeviceClass.DATE` but Azure Standard returns a week-range string like "Week of Sep 13", not an ISO date. Device class removed; sensor now shows the raw string.
- **Active order status showing "shipped" for the open cart** — `_find_active_order` did not treat "shipped" as a terminal status, so a recently shipped prior order was selected instead of the open cart. "ship" added to the terminal set.
- **Active order item count showing 0** — the `/orders` list endpoint does not embed line items; the coordinator now fetches `GET /order/{id}` when the item count is absent from the list response to get the true count.

### Added
- **`Order placed` binary sensor** (`binary_sensor.azure_standard_order_placed`) — `ON` once the active order has been checked out / submitted. While building your cart (order status "open", no `placed` timestamp) it stays `OFF`.
- **Richer order attributes on every active-order sensor** — all three active-order sensors (`status`, `item count`, `total`) and the new `order_placed` binary sensor now expose `order_id`, `order_placed`, `cutoff`, and `delivery` as extra attributes, matching the data shown in the Azure Standard Orders GUI.
- **`cart_order_id`, `cart_total`, `cart_cutoff`, `cart_delivery` coordinator fields** — extracted directly from the orders list response so no extra API call is needed for metadata the list already provides.
- **`_find_active_order` prefers `open` status** — explicitly selects the unplaced cart (status `open`) over other non-terminal orders, then falls back to highest order ID.

## [0.0.6] - 2025-07-14

### Fixed
- **`hass.components` removed in HA 2025.1** — replaced deprecated `hass.components.persistent_notification.async_create(...)` with the modern `persistent_notification.async_create(hass, ...)` import. This was causing "Failed setup, will retry" on every integration load.
- **Auth failures silently swallowed** — `_authenticated_get` now correctly raises `ConfigEntryAuthFailed` when the post-reauth retry also receives a 401/403, instead of raising a raw `aiohttp.ClientResponseError` that was caught and logged as a transient network warning ("Failed to refresh orders; keeping previous data.").
- **`_authenticated_get` never retried** — the docstring said "retry once after re-auth" but the code re-raised the original error immediately after calling `_reauth()`. The request is now retried after a successful re-login.
- **Network errors triggered unnecessary reauth** — a `ClientError` during `validate_session()` (e.g. a momentary network blip) incorrectly set `valid = False`, which then called `_reauth()`. Network errors are now treated as transient and the session check is skipped until the next interval.

## [0.0.5] - 2025-07-13

### Added
- Silent re-authentication using stored password when session cookie expires.
- `CONF_PASSWORD` stored in config entry data on initial setup and reauth flow.
- `_reauth()` coordinator helper: re-logs in and persists the fresh session cookie.
- Reauth config flow (`async_step_reauth` / `async_step_reauth_confirm`) prompts the user via the HA repair UI when no password is stored.
