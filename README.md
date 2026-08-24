# Azure Standard — Home Assistant Integration

A custom Home Assistant integration for [Azure Standard](https://www.azurestandard.com), a natural/organic food co-op delivery service. Monitor your drop location cutoff dates, active orders, shopping lists, and order history directly from Home Assistant.

## Status

> ⚠️ **Pre-development** — This repository is in the planning and documentation phase. No working integration exists yet.

## What This Does

- **Drop & Cutoff Sensors** — tracks your pickup drop location and shows days until the next order cutoff date
- **Order Window Binary Sensor** — ON when an order cycle is open, OFF after cutoff passes
- **Active Order Sensors** — item count, dollar total, and status of your current open order
- **Shopping List Sensors** — dynamically-created item count sensors for each of your saved Azure Standard shopping lists
- **Smart Product Discovery** — analyzes your purchase history, identifies frequently ordered products, and proposes creating dedicated sensors for them
- **Per-Product Sensors** — last ordered date, times ordered, average order interval, days until suggested reorder, current price, on-sale alert
- **On-Sale Binary Sensors** — alerts when a tracked product's price drops significantly below its rolling average
- **Account Credit** — current Azure Cash / credit balance

## Setup Modes

### Mode A: Manual (No Login Required)
Enter your drop's numeric ID. Get drop/cutoff sensors only. No Azure Standard credentials stored.

### Mode B: Account Login (Full Access)
Login with your Azure Standard email and password. Drop auto-detected from your account. Unlocks all sensors including order history, shopping lists, and smart product discovery.

## Repository Structure

```
AzureStandard_Intigration/
├── docs/
│   ├── proposal.md          # Full integration proposal (v0.2)
│   ├── architecture.md      # Developer architecture reference
│   ├── api-reference.md     # Discovered API endpoints and data shapes
│   └── api-findings.md      # Raw API research notes
├── custom_components/
│   └── azure_standard/      # Integration source (to be built)
└── README.md
```

## Documents

- [Integration Proposal](docs/proposal.md) — goals, entities, discovery engine, build plan
- [Architecture Reference](docs/architecture.md) — file map, class interfaces, data models, sequences
- [API Reference](docs/api-reference.md) — all confirmed endpoints with request/response shapes
- [API Research Notes](docs/api-findings.md) — raw reverse-engineering notes, live response samples

## Key Technical Facts

- **API Base URL:** `https://api.azurestandard.com`
- **Auth:** Cookie-based (`POST /login` → session cookie `id`)
- **Public endpoints:** Drop locations, cutoff dates, product catalogue, prices — no auth needed
- **Auth-required:** Orders, shopping lists, ordered products, account info
- **No official API docs** — API reverse-engineered from JavaScript source bundles

## License

MIT
