# Azure Standard — Home Assistant Integration

A custom Home Assistant integration for [Azure Standard](https://www.azurestandard.com), a natural/organic food co-op delivery service. Monitor your drop location cutoff dates, active orders, shopping lists, and order history directly from Home Assistant.

## Status

> ⚠️ **Pre-development** — This repository is in the planning and documentation phase. No working integration exists yet.

## What This Does

- **Drop & Cutoff Sensors** — tracks your pickup drop location and shows days until the next order cutoff date
- **Order Window Binary Sensor** — ON when an order cycle is open, OFF after cutoff
- **Active Order Sensors** — item count, total, and status of your current open order
- **Shopping List Sensors** — item counts for each of your saved Azure Standard shopping lists
- **Order History** — last-ordered date and order count for tracked products
- **Account Credit** — current Azure Cash / credit balance

## Repository Structure

```
AzureStandard_Intigration/
├── docs/
│   ├── proposal.md          # Full integration proposal
│   ├── api-reference.md     # Discovered API endpoints and data shapes
│   └── api-findings.md      # Raw API research notes
├── custom_components/
│   └── azure_standard/      # Integration source (to be built)
└── README.md
```

## Documents

- [Integration Proposal](docs/proposal.md)
- [API Reference](docs/api-reference.md)
- [API Research Notes](docs/api-findings.md)

## Key Technical Facts

- **API Base URL:** `https://api.azurestandard.com`
- **Auth:** Cookie-based (`POST /login` → session cookie `id`)
- **Public endpoints:** Drop locations, cutoff dates, product catalogue — no auth needed
- **Auth-required endpoints:** Orders, shopping lists, ordered products, account info

## Setup (Future)

Will be installable via HACS or manual copy into `custom_components/azure_standard/`.

## License

MIT
