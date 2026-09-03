/**
 * Azure Standard — Sidebar Panel
 * Phase 20 / v0.2.2
 *
 * Four content tabs (account-mode tabs hidden in manual mode):
 *   1. Summary   — Drop & Cutoff + Active Order snapshot
 *   2. Lists     — Shopping lists with link-out to Azure Standard site
 *   3. Products  — Tracked products table; reorder-due badge on tab
 *   4. Account   — Credit, pending payment, order history
 *
 * Plus one persistent tab:
 *   ⚙ Settings — toggle tab visibility, per-product show/hide, compact mode.
 *
 * Tab state (`this._tab`) persists across re-renders triggered by hass state
 * updates so the user's selected tab doesn't reset on every poll.
 *
 * Phase 20 additions:
 *   - Per-product show/hide: each tracked product can be hidden individually
 *     from the Products tab via checkboxes in Settings.
 *     Stored in localStorage under "azure_standard_panel_product_vis".
 *   - Compact / expanded Products view toggle: compact mode shows a condensed
 *     two-column view (name + reorder indicator only) instead of the full table.
 *     Stored in localStorage under "azure_standard_panel_compact".
 */

const AZURE_STANDARD_URL  = "https://www.azurestandard.com";
const _LISTS_BASE   = `${AZURE_STANDARD_URL}/my-account/lists`;
const _ORDERS_BASE  = `${AZURE_STANDARD_URL}/my-account/order`;
const _SHOP_BASE    = `${AZURE_STANDARD_URL}/shop/product`;

const _STORAGE_KEY         = "azure_standard_panel_tab_visibility";
const _PRODUCT_VIS_KEY     = "azure_standard_panel_product_vis";
const _COMPACT_KEY         = "azure_standard_panel_compact";
const _TAB_DEFAULTS        = { lists: true, products: true, account: true };

class AzureStandardPanel extends HTMLElement {
  // ------------------------------------------------------------------ setup

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "summary";
    // Tracks how many reorder-due products the user last saw on the Products tab.
    // Badge only shows when current count exceeds this value.
    this._seenReorderCount = 0;
    // Per-tab visibility (lists / products / account).  Summary is always on.
    this._tabVis = this._loadTabVis();
    // Per-product visibility: object keyed by product code → bool (default true).
    this._productVis = this._loadProductVis();
    // Compact mode for Products tab (bool, default false).
    this._compact = this._loadCompact();
  }

  set hass(hass) {
    this._hass = hass;
    const fp = this._fingerprint();
    if (fp === this._lastFingerprint) return;
    this._lastFingerprint = fp;
    this._render();
  }

  setConfig(config) {
    this._config = config;
  }

  // -------------------------------------------------------- visibility storage

  _loadTabVis() {
    try {
      const raw = localStorage.getItem(_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        // Merge with defaults so newly-added tabs default to visible.
        return Object.assign({}, _TAB_DEFAULTS, parsed);
      }
    } catch (_) { /* ignore JSON/localStorage errors */ }
    return Object.assign({}, _TAB_DEFAULTS);
  }

  _saveTabVis() {
    try {
      localStorage.setItem(_STORAGE_KEY, JSON.stringify(this._tabVis));
    } catch (_) { /* ignore quota/security errors */ }
  }

  _loadProductVis() {
    try {
      const raw = localStorage.getItem(_PRODUCT_VIS_KEY);
      if (raw) return JSON.parse(raw);
    } catch (_) { /* ignore */ }
    return {};
  }

  _saveProductVis() {
    try {
      localStorage.setItem(_PRODUCT_VIS_KEY, JSON.stringify(this._productVis));
    } catch (_) { /* ignore */ }
  }

  _loadCompact() {
    try {
      const raw = localStorage.getItem(_COMPACT_KEY);
      if (raw !== null) return JSON.parse(raw) === true;
    } catch (_) { /* ignore */ }
    return false;
  }

  _saveCompact() {
    try {
      localStorage.setItem(_COMPACT_KEY, JSON.stringify(this._compact));
    } catch (_) { /* ignore */ }
  }

  // Returns true if the product with this code should be shown.
  // Defaults to visible when no explicit preference is stored.
  _isProductVisible(code) {
    return this._productVis[code] !== false;
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

  // Returns a string that changes whenever any azure_standard entity state or
  // attributes change, so the hass setter can skip full re-renders when nothing
  // relevant has updated.
  _fingerprint() {
    if (!this._hass?.states) return "";
    return Object.keys(this._hass.states)
      .filter((id) => id.startsWith("sensor.azure_standard_") ||
                      id.startsWith("binary_sensor.azure_standard_"))
      .sort()
      .map((id) => {
        const s = this._hass.states[id];
        return `${id}:${s.state}:${s.last_updated}`;
      })
      .join("|");
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

    // Unseen count: how many reorder-due products the user hasn't seen yet.
    // Clamp to zero so a decrease (product re-ordered) never shows a stale badge.
    const unseenCount = Math.max(0, reorderCount - this._seenReorderCount);

    // ── Tab definitions ───────────────────────────────────────────────────
    // Summary is always present; account tabs are gated by hasAccount AND
    // the user's per-tab visibility setting.
    const tabs = [
      { id: "summary", label: "Summary" },
      ...(hasAccount && this._tabVis.lists    ? [{ id: "lists",    label: "Lists",    badge: e.listEntities.length || null }] : []),
      ...(hasAccount && this._tabVis.products ? [{ id: "products", label: "Products", badge: unseenCount || null }] : []),
      ...(hasAccount && this._tabVis.account  ? [{ id: "account",  label: "Account" }] : []),
      { id: "settings", label: "⚙", title: "Panel settings" },
    ];

    if (!tabs.find((t) => t.id === this._tab)) this._tab = "summary";

    const tabBar = tabs.map((t) => `
      <button class="tab${this._tab === t.id ? " tab-active" : ""}${t.id === "settings" ? " tab-settings" : ""}" data-tab="${t.id}"${t.title ? ` title="${t.title}"` : ""}>
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
      </section>` : ""}

      ${unseenCount > 0 ? `
      <div class="reorder-alert" id="reorder-alert">
        <span class="reorder-alert-icon">⚠</span>
        <span>${unseenCount} product${unseenCount > 1 ? "s" : ""} due for reorder</span>
        <button class="reorder-alert-btn" id="go-products">View Products →</button>
      </div>` : ""}`;

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
    // Filter to only the products the user has chosen to show.
    const visibleProductEntities = e.productEntities
      .filter((id) => {
        const code = id.replace("sensor.azure_standard_", "").replace("_last_ordered", "");
        return this._isProductVisible(code);
      });

    const buildProductData = (id) => {
      const code        = id.replace("sensor.azure_standard_", "").replace("_last_ordered", "");
      const timesId     = `sensor.azure_standard_${code}_times_ordered`;
      const daysSinceId = `sensor.azure_standard_${code}_days_since`;
      const reorderId   = `sensor.azure_standard_${code}_reorder_due`;
      const name        = this._attr(id, "friendly_name") || code.replace(/_/g, " ");
      const last        = this._state(id);
      const times       = this._state(timesId);
      const daysSince   = this._state(daysSinceId);
      const reorder     = this._state(reorderId);
      const timesNum    = parseInt(times, 10);
      const daysNum     = parseInt(daysSince, 10);
      const avgDays     = (!isNaN(timesNum) && timesNum > 1 && !isNaN(daysNum))
                          ? Math.round(daysNum / (timesNum - 1)) : "—";
      const productId   = this._attr(id, "product_id", null);
      const pkgCode     = this._attr(id, "code", code.toUpperCase());
      const nameSlug    = this._escHtml(name).toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
      const productLink = (productId && productId !== "—")
        ? `${_SHOP_BASE}/${nameSlug}/${productId}?package=${pkgCode}` : null;
      const nameCell    = productLink
        ? `<a class="product-link" href="${productLink}" target="_blank" rel="noopener noreferrer">${this._escHtml(name)}</a>`
        : this._escHtml(name);
      const priceHistory = this._attr(id, "price_history", []);
      const sparkCell   = this._sparkline(priceHistory);
      return { code, name, nameCell, last, times, daysSince, reorder, avgDays, sparkCell };
    };

    // Compact view: two-column list — name + reorder badge
    const compactRows = visibleProductEntities.map((id) => {
      const d = buildProductData(id);
      return `
        <tr class="${d.reorder === "true" ? "reorder-due" : ""}">
          <td>${d.nameCell}</td>
          <td class="center">${d.reorder === "true" ? '<span class="badge badge-reorder">Reorder</span>' : ""}</td>
        </tr>`;
    }).join("");

    // Expanded view: full 7-column table
    const expandedRows = visibleProductEntities.map((id) => {
      const d = buildProductData(id);
      return `
        <tr class="${d.reorder === "true" ? "reorder-due" : ""}">
          <td>${d.nameCell}</td>
          <td>${d.last}</td>
          <td class="sparkline-cell">${d.sparkCell}</td>
          <td class="num">${d.times}</td>
          <td class="num">${d.daysSince}</td>
          <td class="num">${d.avgDays !== "—" ? "~" + d.avgDays + "d" : "—"}</td>
          <td class="center">${d.reorder === "true" ? "✓" : ""}</td>
        </tr>`;
    }).join("");

    const hiddenCount = e.productEntities.length - visibleProductEntities.length;
    const hiddenNote  = hiddenCount > 0
      ? `<p class="hidden-note">${hiddenCount} product${hiddenCount > 1 ? "s" : ""} hidden · <button class="btn-text" id="go-settings-products">Manage in Settings</button></p>`
      : "";

    const compactToggleBar = e.productEntities.length
      ? `<div class="compact-toggle-bar">
           <label class="compact-toggle-label">
             <input type="checkbox" id="toggle-compact" ${this._compact ? "checked" : ""} />
             Compact view
           </label>
         </div>`
      : "";

    const productsTab = e.productEntities.length
      ? `
        ${compactToggleBar}
        <section class="card">
          ${this._compact ? `
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Reorder</th>
              </tr>
            </thead>
            <tbody>${compactRows || '<tr><td colspan="2" class="empty-state">All products hidden.</td></tr>'}</tbody>
          </table>` : `
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
            <tbody>${expandedRows || '<tr><td colspan="7" class="empty-state">All products hidden.</td></tr>'}</tbody>
          </table>`}
        </section>
        ${hiddenNote}
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

    // ── Settings tab ──────────────────────────────────────────────────────
    // Per-product visibility checkboxes (generated from live entity list).
    const productVisRows = e.productEntities.length
      ? e.productEntities.map((id) => {
          const code = id.replace("sensor.azure_standard_", "").replace("_last_ordered", "");
          const name = this._attr(id, "friendly_name") || code.replace(/_/g, " ");
          const checked = this._isProductVisible(code) ? "checked" : "";
          return `
            <label class="settings-row settings-row-product">
              <input type="checkbox" class="product-vis-cb" data-code="${this._escHtml(code)}" ${checked} />
              <span class="settings-label">${this._escHtml(name)}</span>
            </label>`;
        }).join("")
      : `<p class="settings-no-products">No tracked products configured.</p>`;

    const settingsTab = `
      <section class="card">
        <h2>Panel settings</h2>

        <h3 class="settings-section-title">Tabs</h3>
        <p class="settings-desc">Choose which tabs appear in this panel.</p>
        <div class="settings-rows">
          <label class="settings-row settings-row-disabled">
            <input type="checkbox" checked disabled />
            <span class="settings-label">Summary</span>
            <span class="settings-note">Always shown</span>
          </label>
          <label class="settings-row">
            <input type="checkbox" id="vis-lists" ${this._tabVis.lists ? "checked" : ""} />
            <span class="settings-label">Lists</span>
            <span class="settings-note">Shopping lists (account mode only)</span>
          </label>
          <label class="settings-row">
            <input type="checkbox" id="vis-products" ${this._tabVis.products ? "checked" : ""} />
            <span class="settings-label">Products</span>
            <span class="settings-note">Tracked products &amp; reorder reminders</span>
          </label>
          <label class="settings-row">
            <input type="checkbox" id="vis-account" ${this._tabVis.account ? "checked" : ""} />
            <span class="settings-label">Account</span>
            <span class="settings-note">Credit, payments &amp; order history</span>
          </label>
        </div>

        <h3 class="settings-section-title">Products view</h3>
        <p class="settings-desc">Choose which products appear in the Products tab and how they are displayed.</p>
        <div class="settings-rows">
          <label class="settings-row">
            <input type="checkbox" id="toggle-compact-settings" ${this._compact ? "checked" : ""} />
            <span class="settings-label">Compact view</span>
            <span class="settings-note">Show only product name and reorder status</span>
          </label>
        </div>
        <div class="settings-rows settings-rows-products">
          ${productVisRows}
        </div>
        <div class="settings-footer">
          <button class="btn-reset" id="btn-reset-vis">Reset to defaults</button>
        </div>
      </section>`;

    // ── Active tab content ────────────────────────────────────────────────
    const tabContent = (
      this._tab === "summary"  ? summaryTab  :
      this._tab === "lists"    ? listsTab    :
      this._tab === "products" ? productsTab :
      this._tab === "account"  ? accountTab  :
      this._tab === "settings" ? settingsTab :
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

        <div class="footer">Azure Standard integration · v0.2.2</div>
      </div>
    `;

    // Tab click listeners — switching to Products marks all reorder-due as seen
    this.shadowRoot.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._tab = btn.dataset.tab;
        if (this._tab === "products") {
          this._seenReorderCount = reorderCount;
        }
        this._render();
      });
    });

    // "View Products →" button on the Summary alert banner
    this.shadowRoot.getElementById("go-products")?.addEventListener("click", () => {
      this._tab = "products";
      this._seenReorderCount = reorderCount;
      this._render();
    });

    // Products tab — compact toggle (in the Products tab bar itself)
    this.shadowRoot.getElementById("toggle-compact")?.addEventListener("change", (ev) => {
      this._compact = ev.target.checked;
      this._saveCompact();
      this._render();
    });

    // Products tab — "Manage in Settings" shortcut link
    this.shadowRoot.getElementById("go-settings-products")?.addEventListener("click", () => {
      this._tab = "settings";
      this._render();
    });

    // Settings — tab visibility checkboxes
    ["lists", "products", "account"].forEach((key) => {
      const el = this.shadowRoot.getElementById(`vis-${key}`);
      el?.addEventListener("change", () => {
        this._tabVis[key] = el.checked;
        this._saveTabVis();
        if (!el.checked && this._tab === key) this._tab = "summary";
        this._render();
      });
    });

    // Settings — compact toggle (mirror of the one on the Products tab)
    this.shadowRoot.getElementById("toggle-compact-settings")?.addEventListener("change", (ev) => {
      this._compact = ev.target.checked;
      this._saveCompact();
      this._render();
    });

    // Settings — per-product visibility checkboxes
    this.shadowRoot.querySelectorAll(".product-vis-cb").forEach((cb) => {
      cb.addEventListener("change", () => {
        const code = cb.dataset.code;
        this._productVis[code] = cb.checked;
        this._saveProductVis();
        this._render();
      });
    });

    // Settings — reset button (resets tabs + product vis + compact)
    this.shadowRoot.getElementById("btn-reset-vis")?.addEventListener("click", () => {
      this._tabVis    = Object.assign({}, _TAB_DEFAULTS);
      this._productVis = {};
      this._compact   = false;
      this._saveTabVis();
      this._saveProductVis();
      this._saveCompact();
      this._render();
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
      /* Settings tab is visually separate — pushed to the right */
      .tab-settings { margin-left: auto; font-size: 16px; padding: 8px 12px; }
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

      /* reorder alert banner (Summary tab) */
      .reorder-alert {
        display: flex;
        align-items: center;
        gap: 10px;
        background: #fff7ed;
        border: 1px solid #fed7aa;
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 16px;
        font-size: 13px;
        color: #c2410c;
        font-weight: 500;
      }
      .reorder-alert-icon { font-size: 16px; flex-shrink: 0; }
      .reorder-alert-btn {
        margin-left: auto;
        background: none;
        border: 1px solid #c2410c;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
        color: #c2410c;
        cursor: pointer;
        font-family: inherit;
        flex-shrink: 0;
        transition: background 0.15s;
      }
      .reorder-alert-btn:hover { background: #fee2e2; }

      /* settings tab */
      .settings-desc {
        font-size: 13px;
        color: var(--secondary-text-color, #57606a);
        margin-bottom: 16px;
        line-height: 1.5;
      }
      .settings-rows {
        display: flex;
        flex-direction: column;
        gap: 2px;
        margin-bottom: 20px;
      }
      .settings-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.12s;
      }
      .settings-row:hover { background: var(--secondary-background-color, #f7f8fa); }
      .settings-row-disabled { opacity: 0.55; cursor: default; }
      .settings-row-disabled:hover { background: none; }
      .settings-row input[type="checkbox"] {
        width: 16px; height: 16px;
        accent-color: var(--primary-color, #16a34a);
        cursor: pointer;
        flex-shrink: 0;
      }
      .settings-row-disabled input[type="checkbox"] { cursor: default; }
      .settings-label {
        font-weight: 600;
        font-size: 14px;
        min-width: 80px;
      }
      .settings-note {
        font-size: 12px;
        color: var(--secondary-text-color, #57606a);
      }
      .settings-footer {
        padding-top: 14px;
        border-top: 1px solid var(--divider-color, #e5e7eb);
      }
      .btn-reset {
        background: none;
        border: 1px solid var(--divider-color, #e5e7eb);
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 500;
        color: var(--secondary-text-color, #57606a);
        cursor: pointer;
        font-family: inherit;
        transition: background 0.15s, border-color 0.15s;
      }
      .btn-reset:hover {
        background: var(--secondary-background-color, #f7f8fa);
        border-color: var(--primary-text-color, #1f2328);
        color: var(--primary-text-color, #1f2328);
      }

      /* compact toggle bar (Products tab) */
      .compact-toggle-bar {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        margin-bottom: 8px;
      }
      .compact-toggle-label {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: var(--secondary-text-color, #57606a);
        cursor: pointer;
        user-select: none;
      }
      .compact-toggle-label input[type="checkbox"] {
        accent-color: var(--primary-color, #16a34a);
        width: 14px; height: 14px;
        cursor: pointer;
      }

      /* reorder badge in compact view */
      .badge-reorder {
        background: #fee2e2;
        color: #991b1b;
        font-size: 10px;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 8px;
        white-space: nowrap;
      }

      /* hidden products note */
      .hidden-note {
        font-size: 12px;
        color: var(--secondary-text-color, #57606a);
        margin-bottom: 8px;
        text-align: right;
      }
      .btn-text {
        background: none;
        border: none;
        padding: 0;
        font-size: 12px;
        font-family: inherit;
        color: var(--primary-color, #16a34a);
        cursor: pointer;
        text-decoration: underline;
      }

      /* settings — section titles */
      .settings-section-title {
        font-size: 13px;
        font-weight: 700;
        color: var(--secondary-text-color, #57606a);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
        margin-top: 20px;
        padding-bottom: 4px;
        border-bottom: 1px solid var(--divider-color, #e5e7eb);
      }

      /* settings — product rows */
      .settings-rows-products .settings-row-product {
        padding: 7px 12px;
      }
      .settings-no-products {
        font-size: 13px;
        color: var(--secondary-text-color, #57606a);
        font-style: italic;
        padding: 8px 12px;
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
