/**
 * azure-standard-cutoff-card  (v0.1.9)
 *
 * Compact Lovelace card showing days until the Azure Standard order cutoff.
 *
 * Card config schema:
 *   type: custom:azure-standard-cutoff-card
 *   title: "Order Cutoff"   # optional, default "Azure Standard"
 *   show_pickup: true        # optional, default true
 *
 * Served at: /azure_standard_panel/azure-standard-cutoff-card.js
 */

const DAYS_SENSOR    = "sensor.azure_standard_days_until_cutoff";
const WINDOW_SENSOR  = "binary_sensor.azure_standard_order_window_open";
const CUTOFF_SENSOR  = "sensor.azure_standard_next_cutoff";
const PICKUP_SENSOR  = "sensor.azure_standard_pickup_date";

class AzureStandardCutoffCard extends HTMLElement {
  // ── Lovelace card lifecycle ──────────────────────────────────────────────

  setConfig(config) {
    this._config = {
      title:       config.title       ?? "Azure Standard",
      show_pickup: config.show_pickup ?? true,
    };
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  // ── Static helpers expected by Lovelace ──────────────────────────────────

  static getConfigElement() {
    // No custom editor — return undefined to use the generic YAML editor.
    return undefined;
  }

  static getStubConfig() {
    return {
      type: "custom:azure-standard-cutoff-card",
      title: "Order Cutoff",
      show_pickup: true,
    };
  }

  // ── Rendering ────────────────────────────────────────────────────────────

  _render() {
    if (!this.shadowRoot) return;

    const hass   = this._hass;
    const config = this._config ?? { title: "Azure Standard", show_pickup: true };

    // Gather state values (gracefully handle missing entities)
    const daysState   = hass?.states?.[DAYS_SENSOR];
    const windowState = hass?.states?.[WINDOW_SENSOR];
    const cutoffState = hass?.states?.[CUTOFF_SENSOR];
    const pickupState = hass?.states?.[PICKUP_SENSOR];

    const daysRaw     = daysState   ? Number(daysState.state)          : null;
    const windowOpen  = windowState ? windowState.state === "on"       : false;
    const cutoffDate  = cutoffState ? cutoffState.state                : "—";
    const pickupDate  = pickupState ? pickupState.state                : "—";
    const isUnknown   = daysRaw === null || isNaN(daysRaw);

    const days        = isUnknown ? null : daysRaw;
    const urgency     = this._urgencyLevel(days, windowOpen, isUnknown);

    const accentColor = urgency === "green" ? "var(--success-color, #4caf50)"
                      : urgency === "amber" ? "var(--warning-color, #ff9800)"
                      :                       "var(--error-color,   #f44336)";

    const daysLabel  = isUnknown  ? "—"
                     : days === 1 ? "1 day"
                     :              `${days} days`;

    const statusText = isUnknown              ? "Status unavailable"
                     : !windowOpen            ? "Order window closed"
                     : days <= 0             ? "Cutoff today!"
                     :                         "until cutoff";

    const pickupRow = config.show_pickup
      ? `<div class="row pickup">
           <span class="label">Pickup</span>
           <span class="value">${pickupDate}</span>
         </div>`
      : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          --card-bg: var(--ha-card-background, var(--card-background-color, #fff));
          --card-radius: var(--ha-card-border-radius, 12px);
          --text-primary: var(--primary-text-color, #212121);
          --text-secondary: var(--secondary-text-color, #727272);
          --card-padding: 14px 16px;
        }
        .card {
          background: var(--card-bg);
          border-radius: var(--card-radius);
          padding: var(--card-padding);
          box-sizing: border-box;
          min-height: 120px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .title {
          font-size: 0.78rem;
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--text-secondary);
        }
        .badge {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: ${accentColor};
          flex-shrink: 0;
        }
        .countdown {
          display: flex;
          align-items: baseline;
          gap: 6px;
        }
        .days-number {
          font-size: 2rem;
          font-weight: 700;
          line-height: 1;
          color: ${accentColor};
        }
        .days-status {
          font-size: 0.82rem;
          color: var(--text-secondary);
          line-height: 1.2;
        }
        .divider {
          border: none;
          border-top: 1px solid var(--divider-color, rgba(0,0,0,0.08));
          margin: 4px 0;
        }
        .row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.78rem;
        }
        .label {
          color: var(--text-secondary);
        }
        .value {
          color: var(--text-primary);
          font-weight: 500;
        }
        .unavailable {
          font-size: 0.78rem;
          color: var(--text-secondary);
          font-style: italic;
        }
      </style>

      <ha-card>
        <div class="card">
          <div class="header">
            <span class="title">${config.title}</span>
            <span class="badge" title="${urgency}"></span>
          </div>

          <div class="countdown">
            <span class="days-number">${daysLabel}</span>
            <span class="days-status">${statusText}</span>
          </div>

          <hr class="divider" />

          <div class="row cutoff">
            <span class="label">Next cutoff</span>
            <span class="value">${cutoffDate}</span>
          </div>

          ${pickupRow}
        </div>
      </ha-card>
    `;
  }

  /**
   * Returns "green" | "amber" | "red" based on days-until-cutoff and
   * whether the order window is open.
   */
  _urgencyLevel(days, windowOpen, isUnknown) {
    if (isUnknown || !windowOpen) return "red";
    if (days <= 1)                return "red";
    if (days <= 3)                return "amber";
    return "green";
  }
}

customElements.define("azure-standard-cutoff-card", AzureStandardCutoffCard);

// Inform Lovelace about this card so it appears in the card picker.
window.customCards = window.customCards ?? [];
window.customCards.push({
  type:        "azure-standard-cutoff-card",
  name:        "Azure Standard Cutoff",
  description: "Compact countdown to the next Azure Standard order cutoff date.",
  preview:     false,
});
