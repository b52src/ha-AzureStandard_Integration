/**
 * Azure Standard — Sidebar Panel
 * Phase 13 / v0.1.4
 *
 * Four tabs (account-mode tabs hidden in manual mode):
 *   1. Summary   — Drop & Cutoff + Active Order snapshot
 *   2. Lists     — Shopping lists with link-out to Azure Standard site
 *   3. Products  — Tracked products table; reorder-due badge on tab
 *   4. Account   — Credit, pending payment, order history
 *
 * Tab state (`this._tab`) persists across re-renders triggered by hass
 * state updates so the user's selected tab doesn't reset on every poll.
 *
 * Phase 12 notes:
 *   - No in-panel list editing; "Edit on Azure Standard" links open the
 *     site in a new tab.
 *   - Manual coordinator refresh button on every tab footer.
 *   - Products tab shows order frequency alongside last-ordered / days-since.
 */

const AZURE_STANDARD_URL  = "https://www.azurestandard.com";
const _LISTS_BASE   = `${AZURE_STANDARD_URL}/my-account/lists`;
const _ORDERS_BASE  = `${AZURE_STANDARD_URL}/my-account/order`;
const _SHOP_BASE    = `${AZURE_STANDARD_URL}/shop/product`;

class AzureStandardPanel extends HTMLElement {
  // ------------------------------------------------------------------ setup

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "summary";
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = config;
  }

  // ----------------------------------------------------------------- helpers

  _state(entityId, fallback = "—") {
    const e = this._hass?.states?.[entityId];
    return e ? e.state : fallback;
  }

  _attr(entityId, attr, fallback = "—") {
    return this._hass?.states?.[entityId]?.attributes?.[attr] ?? fallback;
  }

  _entitiesWithPrefix(prefix) {
    if (!this._hass?.states) return [];
    return Object.keys(this._hass.states)
      .filter((id) => id.startsWith(prefix))
      .sort();
  }

  _collectEntities() {
    const s = (key) => `sensor.azure_standard_${key}`;
    const b = (key) => `binary_sensor.azure_standard_${key}`;

    const dropName        = this._state(s("drop_name"));
    const nextCutoff      = this._state(s("next_cutoff"));
    const daysUntilCutoff = this._state(s("days_until_cutoff"));
    const deliveryDate    = this._state(s("delivery_date"));
    const pickupDate      = this._state(s("pickup_date"));
    const pickupWeek      = this._state(s("pickup_week"));
    const daysUntilPickup = this._state(s("days_until_pickup"));
    const windowOpen      = this._state(b("order_window_open"));

    const orderStatus    = this._state(s("active_order_status"));
    const orderItems     = this._state(s("active_order_item_count"));
    const orderTotal     = this._state(s("active_order_total"));
    const orderPlaced    = this._state(b("order_placed"));
    const lastOrderDate  = this._state(s("last_order_date"));
    const accountCredit  = this._state(s("account_credit"));
    const pendingPayment = this._state(s("pending_payment"));

    const listEntities = this._entitiesWithPrefix("sensor.azure_standard_")
      .filter((id) => id.endsWith("_list"));

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

    const windowOpen  = e.windowOpen === "on";
    const badgeClass  = windowOpen ? "badge-open" : "badge-closed";
    const badgeLabel  = windowOpen ? "OPEN" : "CLOSED";

    const days    = parseInt(e.daysUntilCutoff, 10);
    const urgency = isNaN(days) ? "" : days <= 1 ? "urgent" : days <= 3 ? "soon" : "";

    const hasAccount = e.orderStatus !== "—" ||
                       e.accountCredit !== "—" ||
                       e.listEntities.length > 0 ||
                       e.productEntities.length > 0;

    // Count reorder-due products for the Products tab badge
    const reorderCount = e.productEntities.filter((id) => {
      const code = id.replace("sensor.azure_standard_", "").replace("_last_ordered", "");
      return this._state(`sensor.azure_standard_${code}_reorder_due`) === "true";
    }).length;

    // ── Tab definitions ───────────────────────────────────────────────────
    const tabs = [
      { id: "summary", label: "Summary" },
      ...(hasAccount ? [
        { id: "lists",    label: "Lists",    badge: e.listEntities.length || null },
        { id: "products", label: "Products", badge: reorderCount || null },
        { id: "account",  label: "Account" },
      ] : []),
    ];

    if (!tabs.find((t) => t.id === this._tab)) this._tab = "summary";

    const tabBar = tabs.map((t) => `
      <button class="tab${this._tab === t.id ? " tab-active" : ""}" data-tab="${t.id}">
        ${this._escHtml(t.label)}
        ${t.badge ? `<span class="tab-badge">${t.badge}</span>` : ""}
      </button>`
    ).join("");

    // Active order ID — read from the status sensor's attributes
    const orderIdRaw = this._attr("sensor.azure_standard_active_order_status", "order_id", null);
    const orderId    = orderIdRaw && orderIdRaw !== "—" ? String(orderIdRaw) : null;
    const orderLink  = orderId ? `${_ORDERS_BASE}/${orderId}` : null;

    // ── Summary tab ───────────────────────────────────────────────────────
    const summaryTab = `
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
      <section class="card">
        <h2>Active Order</h2>
        <div class="kv-grid">
          <span class="label">Status</span>
          <span class="value">${e.orderStatus}${e.orderPlaced === "on"
            ? ' <span class="badge badge-open">placed</span>' : ""}</span>

          <span class="label">Items in cart</span>
          <span class="value">${e.orderItems}</span>

          <span class="label">Order total</span>
          <span class="value">${e.orderTotal !== "—" ? "$" + e.orderTotal : "—"}</span>

          <span class="label">Last order</span>
          <span class="value">${e.lastOrderDate}</span>

          <span class="label">Account credit</span>
          <span class="value">${e.accountCredit !== "—" ? "$" + e.accountCredit : "—"}</span>

          <span class="label">Pending payment</span>
          <span class="value">${e.pendingPayment !== "—" ? "$" + e.pendingPayment : "—"}</span>
        </div>
        ${orderLink ? `
        <div class="list-actions">
          <a class="btn-link" href="${orderLink}" target="_blank" rel="noopener noreferrer">
            View order on Azure Standard ↗
          </a>
        </div>` : ""}
      </section>` : ""}`;

    // ── Lists tab ─────────────────────────────────────────────────────────
    const listsTab = e.listEntities.length
      ? e.listEntities.map((id) => {
          const name    = this._attr(id, "friendly_name") ||
                          id.replace("sensor.azure_standard_", "").replace("_list", "").replace(/_/g, " ");
          const count   = this._state(id, "0");
          const items   = this._attr(id, "items", []);
          const listId  = this._attr(id, "list_id", null);
          const listUrl = listId && listId !== "—" ? `${_LISTS_BASE}/${listId}` : `${_LISTS_BASE}`;
          const preview = Array.isArray(items) && items.length
            ? items.slice(0, 5).map((i) =>
                `<li>${this._escHtml(String(i.name || i.product_name || i.code || i))}</li>`
              ).join("") +
              (items.length > 5
                ? `<li class="more">+${items.length - 5} more…</li>`
                : "")
            : "";
          return `
            <section class="card">
              <div class="list-header">
                <span class="list-name">${this._escHtml(name)} list</span>
                <span class="list-count">${count} items</span>
              </div>
              ${preview
                ? `<ul class="list-items">${preview}</ul>`
                : `<p class="empty">No items in this list.</p>`}
              <div class="list-actions">
                <a class="btn-link"
                   href="${listUrl}"
                   target="_blank" rel="noopener noreferrer">
                  Edit on Azure Standard ↗
                </a>
              </div>
            </section>`;
        }).join("")
      : `<p class="empty-state">No shopping lists found.</p>
         <div class="card-actions">
           <a class="btn-link"
              href="${_LISTS_BASE}"
              target="_blank" rel="noopener noreferrer">
             Manage lists on Azure Standard ↗
           </a>
         </div>`;

    // ── Products tab ──────────────────────────────────────────────────────
    const productRows = e.productEntities.map((id) => {
      const code        = id.replace("sensor.azure_standard_", "").replace("_last_ordered", "");
      const timesId     = `sensor.azure_standard_${code}_times_ordered`;
      const daysSinceId = `sensor.azure_standard_${code}_days_since`;
      const reorderId   = `sensor.azure_standard_${code}_reorder_due`;
      const name        = this._attr(id, "friendly_name") || code.replace(/_/g, " ");
      const last        = this._state(id);
      const times       = this._state(timesId);
      const daysSince   = this._state(daysSinceId);
      const reorder     = this._state(reorderId);
      // Avg cycle: days_since / (times − 1)
      const timesNum    = parseInt(times, 10);
      const daysNum     = parseInt(daysSince, 10);
      const avgDays     = (!isNaN(timesNum) && timesNum > 1 && !isNaN(daysNum))
                          ? Math.round(daysNum / (timesNum - 1))
                          : "—";
      // Product page link — product_id + code exposed as attrs on last_ordered sensor
      const productId   = this._attr(id, "product_id", null);
      const pkgCode     = this._attr(id, "code", code.toUpperCase());
      const nameSlug    = this._escHtml(name).toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
      const productLink = (productId && productId !== "—")
        ? `${_SHOP_BASE}/${nameSlug}/${productId}?package=${pkgCode}`
        : null;
      const nameCell    = productLink
        ? `<a class="product-link" href="${productLink}" target="_blank" rel="noopener noreferrer">${this._escHtml(name)}</a>`
        : this._escHtml(name);
      // Sparkline from price_history attribute
      const priceHistory = this._attr(id, "price_history", []);
      const sparkCell   = this._sparkline(priceHistory);
      return `
        <tr class="${reorder === "true" ? "reorder-due" : ""}">
          <td>${nameCell}</td>
          <td>${last}</td>
          <td class="sparkline-cell">${sparkCell}</td>
          <td class="num">${times}</td>
          <td class="num">${daysSince}</td>
          <td class="num">${avgDays !== "—" ? "~" + avgDays + "d" : "—"}</td>
          <td class="center">${reorder === "true" ? "✓" : ""}</td>
        </tr>`;
    }).join("");

    const productsTab = e.productEntities.length
      ? `
        <section class="card">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Last ordered</th>
                <th>Price</th>
                <th>Times</th>
                <th>Days since</th>
                <th>Avg cycle</th>
                <th>Reorder</th>
              </tr>
            </thead>
            <tbody>${productRows}</tbody>
          </table>
        </section>
        <div class="card-actions">
          <a class="btn-link"
             href="${AZURE_STANDARD_URL}/shop"
             target="_blank" rel="noopener noreferrer">
            Shop on Azure Standard ↗
          </a>
        </div>`
      : `<p class="empty-state">No tracked products found.</p>`;

    // ── Account tab ───────────────────────────────────────────────────────
    const accountTab = `
      <section class="card">
        <h2>Account</h2>
        <div class="kv-grid">
          <span class="label">Account credit</span>
          <span class="value">${e.accountCredit !== "—" ? "$" + e.accountCredit : "—"}</span>

          <span class="label">Pending payment</span>
          <span class="value">${e.pendingPayment !== "—" ? "$" + e.pendingPayment : "—"}</span>

          <span class="label">Last order date</span>
          <span class="value">${e.lastOrderDate}</span>

          <span class="label">Active order status</span>
          <span class="value">${e.orderStatus}</span>
        </div>
        ${orderLink ? `
        <div class="list-actions">
          <a class="btn-link" href="${orderLink}" target="_blank" rel="noopener noreferrer">
            View active order ↗
          </a>
        </div>` : ""}
      </section>
      <div class="card-actions">
        <a class="btn-link"
           href="${AZURE_STANDARD_URL}/my-account/order"
           target="_blank" rel="noopener noreferrer">
          Order history on Azure Standard ↗
        </a>
      </div>`;

    // ── Active tab content ────────────────────────────────────────────────
    const tabContent = (
      this._tab === "summary"  ? summaryTab  :
      this._tab === "lists"    ? listsTab    :
      this._tab === "products" ? productsTab :
      this._tab === "account"  ? accountTab  :
      summaryTab
    );

    // ── Assemble full panel ───────────────────────────────────────────────
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
          <button class="refresh-btn" id="refresh-btn" title="Refresh data">↻</button>
        </div>

        <div class="tab-bar">${tabBar}</div>
        <div class="tab-content">${tabContent}</div>

        <div class="footer">Azure Standard integration · v0.1.2</div>
      </div>
    `;

    // Tab click listeners
    this.shadowRoot.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._tab = btn.dataset.tab;
        this._render();
      });
    });

    // Refresh button — fires a persistent notification service call as a
    // lightweight way to trigger coordinator reload from the panel.
    this.shadowRoot.getElementById("refresh-btn")?.addEventListener("click", async () => {
      const btn = this.shadowRoot.getElementById("refresh-btn");
      if (btn) { btn.disabled = true; btn.textContent = "…"; }
      try {
        await this._hass.callService("homeassistant", "update_entity", {
          entity_id: `sensor.azure_standard_drop_name`,
        });
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = "↻"; }
      }
    });
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

      /* header */
      .panel-header {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 20px;
      }
      .logo { width: 40px; height: 40px; border-radius: 8px; }
      h1 { font-size: 22px; font-weight: 700; flex: 1; }
      .subtitle { font-size: 13px; color: var(--secondary-text-color, #57606a); }

      .refresh-btn {
        background: none;
        border: 1px solid var(--divider-color, #e5e7eb);
        border-radius: 8px;
        width: 36px; height: 36px;
        font-size: 18px;
        cursor: pointer;
        color: var(--secondary-text-color, #57606a);
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
        transition: background 0.15s;
      }
      .refresh-btn:hover { background: var(--secondary-background-color, #f7f8fa); }
      .refresh-btn:disabled { opacity: 0.4; cursor: default; }

      /* tab bar */
      .tab-bar {
        display: flex;
        gap: 2px;
        border-bottom: 2px solid var(--divider-color, #e5e7eb);
        margin-bottom: 20px;
      }
      .tab {
        background: none;
        border: none;
        border-bottom: 3px solid transparent;
        margin-bottom: -2px;
        padding: 8px 16px;
        font-size: 14px;
        font-weight: 500;
        color: var(--secondary-text-color, #57606a);
        cursor: pointer;
        border-radius: 6px 6px 0 0;
        display: flex; align-items: center; gap: 6px;
        transition: color 0.15s;
        font-family: inherit;
      }
      .tab:hover { color: var(--primary-text-color, #1f2328); }
      .tab-active {
        color: var(--primary-color, #16a34a);
        border-bottom-color: var(--primary-color, #16a34a);
        font-weight: 700;
      }
      .tab-badge {
        background: #dc2626;
        color: #fff;
        font-size: 10px;
        font-weight: 700;
        padding: 1px 5px;
        border-radius: 8px;
        min-width: 16px;
        text-align: center;
        line-height: 1.4;
      }

      /* cards */
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
      .label { font-size: 13px; color: var(--secondary-text-color, #57606a); }
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
      .list-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 8px;
      }
      .list-name  { font-weight: 600; font-size: 14px; text-transform: capitalize; }
      .list-count { font-size: 12px; color: var(--secondary-text-color, #57606a); }
      .list-items {
        list-style: disc;
        margin-left: 18px;
        font-size: 13px;
        color: var(--primary-text-color, #1f2328);
      }
      .list-items li { padding: 2px 0; }
      .list-items li.more {
        color: var(--secondary-text-color, #57606a);
        list-style: none;
        margin-left: -4px;
        font-style: italic;
      }

      /* link-out actions */
      .list-actions {
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid var(--divider-color, #e5e7eb);
      }
      .card-actions { margin-bottom: 16px; }
      .btn-link {
        display: inline-block;
        font-size: 13px;
        font-weight: 600;
        color: var(--primary-color, #16a34a);
        text-decoration: none;
        padding: 6px 12px;
        border: 1px solid var(--primary-color, #16a34a);
        border-radius: 8px;
        transition: background 0.15s;
      }
      .btn-link:hover { background: #d1fae5; }
      .product-link {
        color: var(--primary-color, #16a34a);
        text-decoration: none;
        font-weight: 500;
      }
      .product-link:hover { text-decoration: underline; }

      /* products table */
      table { width: 100%; border-collapse: collapse; font-size: 13px; }
      th {
        background: var(--secondary-background-color, #f7f8fa);
        text-align: left;
        padding: 7px 10px;
        border: 1px solid var(--divider-color, #e5e7eb);
        font-weight: 600;
        font-size: 11px;
        color: var(--secondary-text-color, #57606a);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      td {
        padding: 6px 10px;
        border: 1px solid var(--divider-color, #e5e7eb);
        vertical-align: middle;
      }
      td.num, td.center { text-align: center; }
      td.sparkline-cell { text-align: center; padding: 4px 8px; }
      tr:nth-child(even) td { background: var(--secondary-background-color, #fafbfc); }
      tr.reorder-due td { background: #fff7ed; }
      tr.reorder-due td:first-child { font-weight: 600; color: #c2410c; }

      /* empty states */
      .empty-state {
        color: var(--secondary-text-color, #57606a);
        font-style: italic;
        padding: 24px 0;
        text-align: center;
      }
      .empty {
        color: var(--secondary-text-color, #57606a);
        font-style: italic;
        font-size: 13px;
        margin-top: 4px;
      }

      /* footer */
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

  /**
   * Render an inline SVG sparkline (40×20 px) for an array of price floats.
   * Returns a '—' string when fewer than 2 data points are available.
   *
   * @param {number[]} history - Array of price floats, oldest first.
   * @returns {string} SVG markup or '—'.
   */
  _sparkline(history) {
    if (!Array.isArray(history) || history.length < 2) return "—";
    const W = 40, H = 20, PAD = 2;
    const min = Math.min(...history);
    const max = Math.max(...history);
    const range = max - min || 1;  // avoid divide-by-zero when all prices equal
    const xStep = (W - PAD * 2) / (history.length - 1);
    const points = history.map((v, i) => {
      const x = PAD + i * xStep;
      const y = PAD + (1 - (v - min) / range) * (H - PAD * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    // Highlight the rightmost (current) point
    const lastParts = points.split(" ").pop().split(",");
    const cx = parseFloat(lastParts[0]);
    const cy = parseFloat(lastParts[1]);
    return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="display:block">` +
      `<polyline points="${points}" fill="none" stroke="#16a34a" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>` +
      `<circle cx="${cx}" cy="${cy}" r="2" fill="#16a34a"/>` +
      `</svg>`;
  }

  _escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}

customElements.define("azure-standard-panel", AzureStandardPanel);
