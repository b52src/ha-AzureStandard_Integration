# Changelog

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
