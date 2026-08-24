# Azure Standard Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-0.0.4-blue.svg)](https://forgejo.crow-nest.xyz/scrow/AzureStandard_Intigration/releases)
[![HA Version](https://img.shields.io/badge/HA-2024.1%2B-brightgreen.svg)](https://www.home-assistant.io/)

Monitor your [Azure Standard](https://www.azurestandard.com/) organic food co-op drop from Home Assistant.

Track cutoff dates, active orders, shopping lists, account credit, and get smart reorder suggestions for your most-ordered products.

---

## Features

- **Drop & cutoff sensors** — next cutoff date, days remaining, delivery date, drop name
- **Order sensors** — active order status, item count, total, last order date
- **Shopping list sensors** — one sensor per list showing item count (updates every 30 min)
- **Account credit sensor** — current account balance in USD
- **Product tracking sensors** — per-product group: last ordered, times ordered, days since last order, reorder due
- **Order window binary sensor** — `on` while the drop is still accepting orders
- **Product on-sale binary sensor** — detects price drops vs 90-day average for each tracked product
- **Smart product discovery** — automatically suggests products you order regularly (≥ 3 times) via HA persistent notifications

---

## Requirements

- Home Assistant 2024.1 or newer
- An Azure Standard account (for order/list/credit sensors) **or** just your Drop ID (for public drop/cutoff sensors only)

---

## Installation

### HACS (recommended)

1. In Home Assistant, go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://forgejo.crow-nest.xyz/scrow/AzureStandard_Intigration` as type **Integration**
3. Search for **Azure Standard** and install
4. Restart Home Assistant

### Manual

1. Copy `custom_components/azure_standard/` from this repo into your HA `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

Go to **Settings → Devices & Services → Add Integration** and search for **Azure Standard**.

### Manual mode

Requires only your **Drop ID** — no account needed. Find your Drop ID at [api.azurestandard.com/drops](https://api.azurestandard.com/drops) by matching your drop name and location.

Provides: drop name, next cutoff date, days until cutoff, delivery date, order window binary sensor.

### Account login mode

Requires your Azure Standard email and password. Your password is used once to obtain a session token — it is not stored.

Provides: everything in manual mode, plus active order sensors, shopping list sensors, account credit, and smart product tracking.

---

## Sensors Reference

### Drop & Cutoff (both modes)

| Sensor | Description | Unit |
|---|---|---|
| Next cutoff | Date of the next order cutoff | date |
| Days until cutoff | Days remaining until the cutoff | days |
| Drop name | Name of your assigned drop location | — |
| Delivery date | Expected delivery date for the next drop | date |

### Order & Account (account mode only)

| Sensor | Description | Unit |
|---|---|---|
| Active order status | Status of your current open order | — |
| Active order items | Number of items in your active order | items |
| Active order total | Total value of your active order | USD |
| Last order date | Date of your most recent completed order | date |
| Account credit | Your current Azure Standard account credit balance | USD |
| Pending payment | Outstanding payment on open orders | USD |

> **Note:** Pending payment currently shows `unavailable` — the Azure Standard API does not expose an open-order total endpoint at this time.

### Shopping Lists (account mode only)

One sensor per shopping list, named after the list (e.g. `{List Name} list`). State = item count.

### Product Sensors (account mode, per tracked product)

For each tracked product you select in the options flow:

| Sensor | Description |
|---|---|
| `{Code} Last Ordered` | Date you last ordered this product |
| `{Code} Times Ordered` | Total times ordered |
| `{Code} Days Since Last Ordered` | Days since last order |
| `{Code} Reorder Due` | Estimated days until you'll need to reorder (based on average interval) |

### Binary Sensors

| Sensor | Description |
|---|---|
| Order window open | `on` when the drop is currently accepting orders |
| `{Code} On Sale` | `on` when current price is ≥ 5% below 90-day average |

---

## Product Tracking Setup

After setting up with account login:

1. Go to **Settings → Devices & Services → Azure Standard → Configure**
2. The **Product tracking** options screen shows every product you've ordered at least 3 times
3. Check the products you want to track
4. Dedicated sensor groups are created live — no restart required

To change the minimum order count threshold, adjust **Minimum order count to show as candidate** in the same options screen.

When new products become eligible (after enough reorders), a **persistent notification** appears in HA suggesting you add them.

---

## Update Intervals

| Data | Interval |
|---|---|
| Drop / cutoff info | Every 6 hours |
| Active order | Every 1 hour |
| Shopping lists | Every 30 minutes |
| Order history / product stats | Every 24 hours |
| Session validation | Every 12 hours |

---

## Known Limitations

- **Pending payment** — Azure Standard's API does not expose open-order totals. The `Pending payment` sensor will show `unavailable` until this changes.
- **Delivery date** — derived from the drop's scheduled delivery window; not guaranteed to match actual delivery.
- **Product prices** — fetched per product on coordinator update; prices update on the 6-hour public data interval.

---

## Contributing

Issues and PRs welcome at [forgejo.crow-nest.xyz/scrow/AzureStandard_Intigration](https://forgejo.crow-nest.xyz/scrow/AzureStandard_Intigration).
