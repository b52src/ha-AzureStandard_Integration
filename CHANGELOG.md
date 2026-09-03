# Changelog

## [0.2.3] - 2025-08-10

### Fixed
- **Panel JS browser cache** — the `www/` static path is now served with
  `cache_headers=False` so HA sends no-cache headers. The panel `module_url` now
  includes `?v={version}` (read from `manifest.json` at load time) so each version
  bump produces a distinct URL, forcing the browser to discard any cached copy of
  the panel JS and fetch the updated file.

## [0.2.2] - 2025-08-10

### Added
- **Panel settings v2 — per-product show/hide** — individual tracked products
  can now be hidden from the Products tab via checkboxes in the ⚙ Settings tab.
  - Hidden products are excluded from the Products table and the reorder-due
    badge count, but remain fully tracked by the integration.
  - Preferences are stored in `localStorage` under
    `azure_standard_panel_product_vis` (keyed by product code, default visible).
  - A "N products hidden · Manage in Settings" note appears at the bottom of the
    Products tab when any product is hidden, with a button that jumps directly
    to the Settings tab.
- **Panel settings v2 — compact Products view** — a toggle switches the
  Products tab between the existing full 7-column table and a compact 2-column
  view showing only the product name and a reorder badge.
  - The toggle is available both directly in the Products tab (top-right) and
    in the Settings tab under the new "Products view" section.
  - State is stored in `localStorage` under `azure_standard_panel_compact`
    (boolean, default `false`).
- **Settings tab redesign** — the Settings tab now has two clearly labelled
  sections: **Tabs** (existing show/hide controls) and **Products view** (new
  compact toggle + per-product checkboxes).
- **Reset to defaults** now also resets product visibility and compact mode in
  addition to tab visibility.

## [0.2.1] - 2025-08-10

### Added
- **Auto-register Lovelace resources** — both `azure-standard-cutoff-card.js`
  and `azure-standard-panel.js` are now automatically registered as Lovelace
  `module` resources when the integration sets up. Users no longer need to
  manually add them via **Settings → Dashboards → Resources** before the
  cutoff card appears in the card picker.
  - Registration is idempotent: URLs already registered (from a previous run
    or a manual addition) are left unchanged and not duplicated.
  - Resources registered by the integration are removed when the last config
    entry for the domain is unloaded.
  - Gracefully degrades: if the Lovelace resource storage API is not available
    (e.g. YAML-mode Lovelace), a debug log is emitted and setup continues
    normally — manual resource addition still works as before.

## [0.2.0] - 2025-08-10

### Added
- **Price drop alert blueprint** (`azure_standard_price_drop.yaml`) — fires a
  notification when a tracked product's `last_price` drops to or below a
  configurable fraction of its rolling average (`price_history`).
  - Single-product input: user selects one `sensor.azure_standard_*_last_ordered`
    entity per automation instance.
  - `threshold_pct` input (default `0.95`) controls how far below the average
    the price must fall before the alert fires (e.g. 0.95 = 5% discount).
  - `min_samples` input (default `3`) guards against firing on insufficient
    history — alert is suppressed until at least N price history entries exist.
  - Notification body and title are fully templated; default message includes
    product name, current price, rolling average, percentage off, and next
    cutoff date (`sensor.azure_standard_next_cutoff`).
  - Trigger uses `state` on `last_price` attribute; dynamic threshold
    comparison is done in the condition via `value_template`.

## [0.1.9] - 2025-08-10

### Added
- **Cutoff countdown Lovelace card** (`azure-standard-cutoff-card`) — a
  compact, standalone card that displays days-until-cutoff with urgency
  color coding independently of the sidebar panel.
  - Green when the order window is open and days > 3.
  - Amber when days ≤ 3.
  - Red when days ≤ 1 or the order window is closed.
  - Subtitle shows the next cutoff date; optional pickup date row
    (controlled by `show_pickup`, default `true`).
  - Optional `title` config key (default `"Azure Standard"`).
  - Registers itself in `window.customCards` so it appears in the
    Lovelace card picker.
  - Served at `/azure_standard_panel/azure-standard-cutoff-card.js`
    (same static path as the sidebar panel JS — no additional Python
    changes required).
  - Full Shadow DOM, pure vanilla JS, no external dependencies.
  - Targets ~120 px tall in default state for grid layouts.

## [0.1.8] - 2025-08-10

### Added
- **Panel config UI** — a permanent ⚙ Settings tab in the sidebar panel lets
  users show or hide the Lists, Products, and Account tabs independently.
  - Summary tab is always visible (cannot be hidden).
  - Preferences are saved to `localStorage` under
    `azure_standard_panel_tab_visibility` and survive HA restarts and browser
    reloads with no Python or HA storage changes required.
  - Hiding the currently active tab automatically returns the view to Summary.
  - A "Reset to defaults" button restores all three tabs to visible in one click.
  - Settings tab is visually distinct (right-aligned gear icon) so it never
    crowds the content tabs.

## [0.1.7] - 2025-08-10

### Added
- **Automation blueprints** — three ready-to-import YAML blueprints in
  `custom_components/azure_standard/blueprints/`:
  - `azure_standard_cutoff_approaching.yaml` — notify N days before the
    order cutoff; configurable threshold (1–14 days), message template,
    and notify target.  Fires only while the order window is still open.
  - `azure_standard_order_window_opened.yaml` — notify the moment the
    order window opens (rising-edge trigger on
    `binary_sensor.azure_standard_order_window_open`).
  - `azure_standard_reorder_due.yaml` — notify when tracked products are
    overdue for reorder; configurable minimum count, message template, and
    optional hourly repeat cadence (0 = once, 24 = daily, etc.).

## [0.1.6] - 2025-08-10

### Added
- **Unseen reorder badge** — the Products tab badge now only appears when the
  reorder-due count has *increased* since the user last visited the Products tab.
  Visiting the tab clears the badge. Re-ordering a product (which lowers the count)
  never shows a stale badge.
- **Reorder alert banner** — a soft amber banner appears on the Summary tab when
  there are unseen reorder-due products. Includes a "View Products →" button that
  jumps directly to the Products tab and marks all items as seen.

### Changed
- `_seenReorderCount` instance variable added to `AzureStandardPanel`; initialised
  to `0` in `constructor()`.
- Tab-click handler now sets `_seenReorderCount = reorderCount` when switching to
  the Products tab.

## [0.1.5] - 2025-08-09

### Added
- **Persistent price history** — price history is now saved to HA's
  `.storage/azure_standard.price_history` file after every daily refresh and
  reloaded on startup. Data survives Home Assistant restarts; the sparkline
  populates immediately after reboot without waiting for the next 24 h cycle.

### Changed
- `AzureStandardCoordinator` now creates a `homeassistant.helpers.storage.Store`
  instance on `__init__` and schedules `_async_load_price_history()` as a task so
  the restored data is available before the first coordinator update runs.
- `_async_save_price_history()` is called once per history-fetch cycle (after all
  tracked-product prices have been appended to the rolling window).
- Invalid or non-numeric entries in the stored data are silently discarded; entries
  beyond `_PRICE_HISTORY_MAX` are clamped so changing the constant is safe.

## [0.1.4] - 2025-08-09

### Added
- **Price history sparkline** in the Products tab — each tracked product row now
  shows an inline 40×20 px SVG sparkline in a new "Price" column, displaying up
  to 12 historical price samples with the current price highlighted by a dot.
  Renders `—` until at least 2 price points have been collected.
- **`price_history` and `last_price` attributes** on `ProductLastOrderedSensor` —
  `price_history` is a list of floats (oldest first, capped at 12), `last_price`
  is the most recent sampled price or `null` if none yet.
- **Price accumulation in coordinator** — during each `_history_due()` refresh
  (daily cadence), the coordinator calls `get_product_price(code)` for every
  tracked product and appends the result to a rolling list stored in
  `AzureStandardData.price_history`.  The in-memory accumulator
  (`_price_history`) persists across refreshes so history is never reset.
- **`STORAGE_KEY_PRICE_HISTORY` / `STORAGE_VERSION`** constants were already
  present in `const.py`; now imported by the coordinator.

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
