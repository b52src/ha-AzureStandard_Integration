# Phase 18 Handoff — Cutoff Countdown Lovelace Card (v0.1.9)

## What changed

### New: `custom_components/azure_standard/www/azure-standard-cutoff-card.js`

A standalone Lovelace custom card element (`azure-standard-cutoff-card`) that
shows days-until-cutoff with urgency colour coding. No Python sensor code was
changed. No HA storage helpers were added. No existing entities were modified.

### Modified: `custom_components/azure_standard/__init__.py`

Added a `_CUTOFF_CARD_JS` module-level constant documenting the new card file.
No functional Python changes — the new JS file is already served automatically
because the entire `www/` directory is registered as a static path in
`async_setup`.

---

## Feature description

### `azure-standard-cutoff-card` Lovelace card

A compact (~120 px tall) Lovelace card intended to sit alongside other cards in
a dashboard grid.

#### Entities read

| Entity | Used for |
|---|---|
| `sensor.azure_standard_days_until_cutoff` | Large countdown number |
| `binary_sensor.azure_standard_order_window_open` | Urgency colour + status text |
| `sensor.azure_standard_next_cutoff` | "Next cutoff" subtitle row |
| `sensor.azure_standard_pickup_date` | Optional "Pickup" row |

#### Urgency colour coding

| Condition | Colour |
|---|---|
| Window open **and** days > 3 | Green (`--success-color`) |
| Days ≤ 3 | Amber (`--warning-color`) |
| Days ≤ 1 **or** window closed **or** entity unavailable | Red (`--error-color`) |

CSS custom property fallbacks ensure both light and dark HA themes look correct.

#### Card config schema

```yaml
type: custom:azure-standard-cutoff-card
title: "Order Cutoff"   # optional — default "Azure Standard"
show_pickup: true        # optional — default true
```

#### Card picker integration

The card self-registers in `window.customCards` so it appears in the Lovelace
"Add Card" picker with the name **"Azure Standard Cutoff"**.

---

## How to add to a dashboard

1. Register the resource in HA (once per install):

   **Settings → Dashboards → Resources → + Add resource**

   ```
   URL:   /azure_standard_panel/azure-standard-cutoff-card.js
   Type:  JavaScript module
   ```

2. Add the card to any Lovelace dashboard (manual YAML or the card picker):

   ```yaml
   type: custom:azure-standard-cutoff-card
   title: "Order Cutoff"
   show_pickup: true
   ```

---

## Implementation details

### Shadow DOM

The card attaches a shadow root with `{ mode: "open" }` and writes the full
`<style>` + `<ha-card>` markup on every `set hass()` call. This keeps state
logic trivially simple — there is no incremental DOM patching.

### Lovelace card contract methods

| Method | Notes |
|---|---|
| `setConfig(config)` | Stores `title` and `show_pickup`; attaches shadow root if not yet present; triggers initial render. |
| `set hass(hass)` | Stores `hass`; triggers re-render on every state push. |
| `static getConfigElement()` | Returns `undefined` — the generic YAML editor is used. |
| `static getStubConfig()` | Returns a minimal stub config for the card picker. |

### Private methods

| Method | Description |
|---|---|
| `_render()` | Reads the four entity states, determines urgency, writes shadow DOM `innerHTML`. |
| `_urgencyLevel(days, windowOpen, isUnknown)` | Pure function returning `"green"` \| `"amber"` \| `"red"`. |

### CSS architecture

All colour values are referenced through HA CSS custom properties with
hardcoded fallbacks:

```
--success-color  →  #4caf50
--warning-color  →  #ff9800
--error-color    →  #f44336
--ha-card-background / --card-background-color  →  #fff
--primary-text-color    →  #212121
--secondary-text-color  →  #727272
```

---

## Files changed

```
custom_components/azure_standard/
├── manifest.json                        — version 0.1.8 → 0.1.9
├── __init__.py                          — _CUTOFF_CARD_JS constant added
└── www/
    └── azure-standard-cutoff-card.js   ← NEW (188 lines)

CHANGELOG.md                             — 0.1.9 entry added
docs/phase18-handoff.md                 ← this file
```

---

## Sanity check

```bash
cd /Users/seancrow/Forgejo/AzureStandard_Intigration
.venv/bin/python3 -m py_compile \
  custom_components/azure_standard/__init__.py \
  custom_components/azure_standard/api.py \
  custom_components/azure_standard/coordinator.py \
  custom_components/azure_standard/config_flow.py \
  custom_components/azure_standard/sensor.py \
  custom_components/azure_standard/const.py \
  custom_components/azure_standard/discovery.py
# Expected output: (none — exit 0)
```

---

## Release

```bash
fj release create "v0.1.9" --tag v0.1.9 \
  --body "Phase 18: azure-standard-cutoff-card — compact Lovelace countdown card with urgency colour coding."
fj release list   # confirm v0.1.9 appears
```

---

## Next iteration ideas (Phase 19+)

| Phase | Name | Description |
|---|---|---|
| 19 | On-sale push alert | Automation blueprint (or built-in notification) when a tracked product's price drops below the rolling average sale threshold. |
| 20 | Panel settings v2 | Per-product show/hide in the Products tab; optional compact/expanded view toggle. |
| 21 | Resource auto-registration | Register the cutoff card JS as a Lovelace resource automatically on integration setup, removing the manual "Settings → Dashboards → Resources" step. |
