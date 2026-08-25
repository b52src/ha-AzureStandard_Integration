/**
 * Azure Standard — Sidebar Panel
 * Phase 11 / v0.1.1
 *
 * Registered by panel_custom as a Web Component. HA injects the `hass`
 * property whenever entity states change, so the panel re-renders live.
 *
 * Sections rendered:
 *   1. Drop & cutoff countdown card
 *   2. Active order card (account mode only)
 *   3. Shopping lists (account mode only)
 *   4. Tracked products table (account mode only)
 */

class AzureStandardPanel extends HTMLElement {
  // ------------------------------------------------------------------ setup

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  /** HA calls this setter every time any entity state changes. */
  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  /** HA injects panel config (url_path, title, icon, config). */
  setConfig(config) {
    this._config = config;
  }

  // ----------------------------------------------------------------- helpers

  /** Return the state string for an entity, or a fallback. */
  _state(entityId, fallback = "—") {
    const e = this._hass?.states?.[entityId];
    return e ? e.state : fallback;
  }

  /** Return a single attribute value. */
  _attr(entityId, attr, fallback = "—") {
    return this._hass?.states?.[entityId]?.attributes?.[attr] ?? fallback;
  }

  /**
   * Find all entity IDs whose entity_id starts with a prefix.
   * Used to discover per-product and per-list sensors dynamically.
   */
  _entitiesWithPrefix(prefix) {
    if (!this._hass?.states) return [];
    return Object.keys(this._hass.states)
      .filter((id) => id.startsWith(prefix))
      .sort();
  }

  /** Collect all azure_standard entities grouped by role. */
  _collectEntities() {
    const s = (key) => `sensor.azure_standard_${key}`;
    const b = (key) => `binary_sensor.azure_standard_${key}`;

    // Core drop/cutoff
    const dropName        = this._state(s("drop_name"));
    const nextCutoff      = this._state(s("next_cutoff"));
    const daysUntilCutoff = this._state(s("days_until_cutoff"));
    const deliveryDate    = this._state(s("delivery_date"));
    const pickupDate      = this._state(s("pickup_date"));
    const pickupWeek      = this._state(s("pickup_week"));
    const daysUntilPickup = this._state(s("days_until_pickup"));
    const windowOpen      = this._state(b("order_window_open"));

    // Order (account mode)
    const orderStatus    = this._state(s("active_order_status"));
    const orderItems     = this._state(s("active_order_item_count"));
    const orderTotal     = this._state(s("active_order_total"));
    const orderPlaced    = this._state(b("order_placed"));
    const lastOrderDate  = this._state(s("last_order_date"));
    const accountCredit  = this._state(s("account_credit"));
    const pendingPayment = this._state(s("pending_payment"));

    // Shopping lists — discover dynamically (sensor.azure_standard_*_list)
    const listEntities = this._entitiesWithPrefix("sensor.azure_standard_")
      .filter((id) => id.endsWith("_list"));

    // Tracked product sensors — discover by _last_ordered / _times_ordered suffix
    const productEntities = this._entitiesWithPrefix("sensor.azure_standard_")
      .filter((id) => id.endsWith("_last_ordered"));

    return {
      dropName, nextCutoff, daysUntilCutoff, deliveryDate,
      pickupDate, pickupWeek, daysUntilPickup, windowOpen,
      orderStatus, orderItems, orderTotal, orderPlaced,
      lastOrderDate, accountCredit, pendingPayment,
      listEntities, productEntities,
    };
  }

  // ---------------------------------------------------------------- rendering

  _render() {
    if (!this._hass) return;

    const e = this._collectEntities();

    // Window status badge
    const windowOpen = e.windowOpen === "on";
    const badgeClass  = windowOpen ? "badge-open" : "badge-closed";
    const badgeLabel  = windowOpen ? "Order window OPEN" : "Order window CLOSED";

    // Cutoff urgency colour
    const days = parseInt(e.daysUntilCutoff, 10);
    const urgency =
      isNaN(days)  ? ""          :
      days <= 1    ? "urgent"    :
      days <= 3    ? "soon"      : "";

    // Build shopping list rows
    const listRows = e.listEntities.map((id) => {
      const name  = this._attr(id, "friendly_name") ||
                    id.replace("sensor.azure_standard_", "").replace("_list", "").replace(/_/g, " ");
      const count = this._state(id, "0");
      const items = this._attr(id, "items", []);
      const itemList = Array.isArray(items) && items.length
        ? items.slice(0, 5).map((i) =>
            `<li>${this._escHtml(String(i.name || i.product_name || i.code || i))}</li>`
          ).join("") + (items.length > 5 ? `<li class="more">+${items.length - 5} more…</li>` : "")
        : "";
      return `
        <div class="list-card">
          <div class="list-header">
            <span class="list-name">${this._escHtml(name)} list</span>
            <span class="list-count">${count} items</span>
          </div>
          ${itemList ? `<ul class="list-items">${itemList}</ul>` : ""}
        </div>`;
    }).join("");

    // Build tracked-products table rows
    const productRows = e.productEntities.map((id) => {
      const code       = id.replace("sensor.azure_standard_", "").replace("_last_ordered", "");
      const lastId     = id;
      const timesId    = `sensor.azure_standard_${code}_times_ordered`;
      const daysSinceId= `sensor.azure_standard_${code}_days_since`;
      const reorderId  = `sensor.azure_standard_${code}_reorder_due`;
      const name       = this._attr(lastId, "friendly_name") || code.replace(/_/g, " ");
      const last       = this._state(lastId);
      const times      = this._state(timesId);
      const daysSince  = this._state(daysSinceId);
      const reorder    = this._state(reorderId);
      const reorderClass = reorder === "true" ? "reorder-due" : "";
      return `
        <tr class="${reorderClass}">
          <td>${this._escHtml(name)}</td>
          <td>${last}</td>
          <td>${times}</td>
          <td>${daysSince}</td>
          <td>${reorder === "true" ? "✓" : ""}</td>
        </tr>`;
    }).join("");

    // Has account-mode data?
    const hasAccount = e.orderStatus !== "—" ||
                       e.accountCredit !== "—" ||
                       e.listEntities.length > 0 ||
                       e.productEntities.length > 0;

    this.shadowRoot.innerHTML = `
      <style>${this._css()}</style>
      <div class="panel">
        <div class="panel-header">
          <img class="logo" src="/api/hassio/static/icons/icon-192x192.png"
               onerror="this.style.display='none'" alt="" />
          <div>
            <h1>Azure Standard</h1>
            <div class="subtitle">${this._escHtml(e.dropName)}</div>
          </div>
        </div>

        <!-- Drop / Cutoff card -->
        <section class="card">
          <h2>Drop &amp; Cutoff</h2>
          <div class="kv-grid">
            <span class="label">Order window</span>
            <span class="badge ${badgeClass}">${badgeLabel}</span>

            <span class="label">Next cutoff</span>
            <span class="value ${urgency}">${e.nextCutoff}</span>

            <span class="label">Days until cutoff</span>
            <span class="value ${urgency}">${e.daysUntilCutoff}</span>

            <span class="label">Delivery</span>
            <span class="value">${e.deliveryDate}</span>

            <span class="label">Pickup date</span>
            <span class="value">${e.pickupDate}</span>

            <span class="label">Pickup week</span>
            <span class="value">${e.pickupWeek}</span>

            <span class="label">Days until pickup</span>
            <span class="value">${e.daysUntilPickup}</span>
          </div>
        </section>

        ${hasAccount ? `
        <!-- Active order card -->
        <section class="card">
          <h2>Active Order</h2>
          <div class="kv-grid">
            <span class="label">Status</span>
            <span class="value">${e.orderStatus}${e.orderPlaced === "on" ? ' <span class="badge badge-open">placed</span>' : ""}</span>

            <span class="label">Items in cart</span>
            <span class="value">${e.orderItems}</span>

            <span class="label">Order total</span>
            <span class="value">${e.orderTotal !== "—" ? "$" + e.orderTotal : "—"}</span>

            <span class="label">Last order date</span>
            <span class="value">${e.lastOrderDate}</span>

            <span class="label">Account credit</span>
            <span class="value">${e.accountCredit !== "—" ? "$" + e.accountCredit : "—"}</span>

            <span class="label">Pending payment</span>
            <span class="value">${e.pendingPayment !== "—" ? "$" + e.pendingPayment : "—"}</span>
          </div>
        </section>

        ${e.listEntities.length ? `
        <!-- Shopping lists -->
        <section class="card">
          <h2>Shopping Lists</h2>
          <div class="lists">${listRows}</div>
        </section>` : ""}

        ${e.productEntities.length ? `
        <!-- Tracked products -->
        <section class="card">
          <h2>Tracked Products</h2>
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Last ordered</th>
                <th>Times</th>
                <th>Days since</th>
                <th>Reorder due</th>
              </tr>
            </thead>
            <tbody>${productRows}</tbody>
          </table>
        </section>` : ""}

        ` : ""}

        <div class="footer">Azure Standard integration · v0.1.1</div>
      </div>
    `;
  }

  // ------------------------------------------------------------------- styles

  _css() {
    return `
      :host { display: block; }
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

      .panel {
        max-width: 860px;
        margin: 0 auto;
        padding: 24px 20px 48px;
        font-family: var(--paper-font-body1_-_font-family, -apple-system, "Segoe UI", sans-serif);
        font-size: 14px;
        line-height: 1.6;
        color: var(--primary-text-color, #1f2328);
      }

      .panel-header {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 24px;
      }
      .logo { width: 40px; height: 40px; border-radius: 8px; }
      h1 { font-size: 22px; font-weight: 700; }
      .subtitle { font-size: 13px; color: var(--secondary-text-color, #57606a); }

      .card {
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e5e7eb);
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 16px;
      }
      h2 {
        font-size: 15px;
        font-weight: 700;
        margin-bottom: 14px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--divider-color, #e5e7eb);
        color: var(--primary-text-color, #1f2328);
      }

      /* key-value grid */
      .kv-grid {
        display: grid;
        grid-template-columns: 160px 1fr;
        gap: 6px 12px;
        align-items: baseline;
      }
      .label {
        font-size: 13px;
        color: var(--secondary-text-color, #57606a);
      }
      .value { font-weight: 500; }
      .value.urgent { color: #dc2626; font-weight: 700; }
      .value.soon   { color: #d97706; font-weight: 600; }

      /* badges */
      .badge {
        display: inline-block;
        font-size: 11px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 10px;
        white-space: nowrap;
      }
      .badge-open   { background: #d1fae5; color: #065f46; }
      .badge-closed { background: #fee2e2; color: #991b1b; }

      /* shopping lists */
      .lists { display: flex; flex-direction: column; gap: 10px; }
      .list-card {
        background: var(--secondary-background-color, #f7f8fa);
        border: 1px solid var(--divider-color, #e5e7eb);
        border-radius: 8px;
        padding: 10px 14px;
      }
      .list-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 6px;
      }
      .list-name  { font-weight: 600; font-size: 13px; text-transform: capitalize; }
      .list-count { font-size: 12px; color: var(--secondary-text-color, #57606a); }
      .list-items {
        list-style: disc;
        margin-left: 18px;
        font-size: 13px;
        color: var(--primary-text-color, #1f2328);
      }
      .list-items li { padding: 1px 0; }
      .list-items li.more { color: var(--secondary-text-color, #57606a); list-style: none; margin-left: -4px; }

      /* products table */
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th {
        background: var(--secondary-background-color, #f7f8fa);
        text-align: left;
        padding: 7px 10px;
        border: 1px solid var(--divider-color, #e5e7eb);
        font-weight: 600;
        font-size: 12px;
        color: var(--secondary-text-color, #57606a);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      td {
        padding: 6px 10px;
        border: 1px solid var(--divider-color, #e5e7eb);
        vertical-align: middle;
      }
      tr:nth-child(even) td { background: var(--secondary-background-color, #fafbfc); }
      tr.reorder-due td { background: #fff7ed; }
      tr.reorder-due td:first-child { font-weight: 600; color: #c2410c; }

      .footer {
        margin-top: 32px;
        text-align: center;
        font-size: 12px;
        color: var(--secondary-text-color, #9ca3af);
        border-top: 1px solid var(--divider-color, #e5e7eb);
        padding-top: 12px;
      }
    `;
  }

  // ---------------------------------------------------------------- utilities

  _escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}

customElements.define("azure-standard-panel", AzureStandardPanel);
