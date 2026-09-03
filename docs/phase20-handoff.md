# Phase 20 Handoff — Panel Settings v2 (v0.2.2)

## What changed

### Modified: `custom_components/azure_standard/www/azure-standard-panel.js`

- **New `localStorage` keys**:
  - `azure_standard_panel_product_vis` — object keyed by product code → bool;
    `false` hides that product from the Products tab. Keys absent from the object
    default to visible (no migration needed for existing users).
  - `azure_standard_panel_compact` — boolean (default `false`); switches the
    Products tab to a compact 2-column view.
- **New class instance variables**:
  - `this._productVis` — loaded from `_PRODUCT_VIS_KEY` via `_loadProductVis()`.
  - `this._compact` — loaded from `_COMPACT_KEY` via `_loadCompact()`.
- **New helper methods**: `_loadProductVis()`, `_saveProductVis()`,
  `_loadCompact()`, `_saveCompact()`, `_isProductVisible(code)`.
- **Products tab**: filters `productEntities` to `visibleProductEntities` before
  rendering. `buildProductData(id)` factored out to serve both compact and
  expanded row renderers. New compact-toggle bar rendered above the table card.
  "N products hidden" note with a "Manage in Settings" button appears when any
  product is hidden.
- **Settings tab**: reorganised into two named sections ("Tabs" and "Products
  view"). Products view section has a compact-mode checkbox plus per-product
  show/hide checkboxes dynamically generated from the live entity list.
- **Reset to defaults**: now also resets `_productVis = {}` and `_compact = false`
  in addition to the existing tab visibility reset.
- Footer version string updated to `v0.2.2`.
- File header comment updated to Phase 20.

### Modified: `custom_components/azure_standard/manifest.json`

Version bumped `0.2.1` → `0.2.2`.

---

## Feature descriptions

### Per-product show/hide

Users with many tracked products can de-clutter the Products tab by hiding
individual products they don't want to monitor in the panel.

**How it works**:
- The Settings tab now shows a "Products view" section. Below the compact-mode
  toggle there is one checkbox per tracked product (populated dynamically from
  the live `sensor.azure_standard_*_last_ordered` entity list).
- Unchecking a product sets `this._productVis[code] = false` and saves it to
  `localStorage`.
- On render, `visibleProductEntities` is computed by filtering the full entity
  list through `_isProductVisible(code)`, which returns `true` unless the code is
  explicitly set to `false` in `_productVis`.
- If any products are hidden, a `hidden-note` paragraph appears at the bottom of
  the Products tab: _"N product(s) hidden · Manage in Settings"_ — the button is
  a click handler that switches `this._tab = "settings"` and re-renders.

**Reorder badge**: the badge on the Products tab counts only visible products that
are reorder-due (computed from `visibleProductEntities`), so hidden products do
not inflate the badge.

**Defaults**: the `_productVis` object starts empty (loaded from localStorage or
defaulting to `{}`). An absent key means visible, so new products appear
automatically without requiring any settings action.

### Compact Products view

Users who want a quick glance at reorder status without the full table can switch
to compact mode.

**How it works**:
- A "Compact view" checkbox appears at the top-right of the Products tab and is
  mirrored in the Settings tab "Products view" section.
- In compact mode, only a 2-column table is rendered: product name (with the
  existing deep-link) and a red `Reorder` badge for products due.
- In expanded mode (default), the full 7-column table is shown as before.
- The `_compact` boolean is persisted to `localStorage`; both checkboxes (in the
  Products tab and Settings tab) are kept in sync because both read `this._compact`
  at render time.

---

## localStorage keys summary

| Key | Type | Default | Purpose |
|---|---|---|---|
| `azure_standard_panel_tab_visibility` | `{lists,products,account: bool}` | all `true` | Show/hide content tabs (Phase 17, unchanged) |
| `azure_standard_panel_product_vis` | `{[code]: bool}` | `{}` (all visible) | Per-product show/hide in Products tab |
| `azure_standard_panel_compact` | `bool` | `false` | Compact vs expanded Products view |

---

## Files changed

```
custom_components/azure_standard/
├── www/
│   └── azure-standard-panel.js   — ~100 lines added (helpers, compact renderer,
│                                    settings redesign, CSS, event handlers)
└── manifest.json                  — version 0.2.1 → 0.2.2

CHANGELOG.md                       — 0.2.2 entry added
docs/phase20-handoff.md            ← this file
```

No Python files were changed. No entities, sensors, or coordinator logic were
modified. No new HA dependencies.

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

All files pass `py_compile` with no errors or warnings.

---

## Release

```bash
fj release create "v0.2.2" --tag v0.2.2 \
  --body "Phase 20: Panel settings v2 — per-product show/hide and compact view toggle in the Products tab."
fj release list   # confirm v0.2.2 appears
```

---

## Next iteration ideas (Phase 21+)

Phase 21 (Lovelace resource auto-registration) was already implemented before
this phase. Remaining ideas:

| Phase | Name | Description |
|---|---|---|
| 22 | Multi-product price drop | Extend the price drop blueprint to watch all tracked products at once using a sensor group or the `reorder_due_count` pattern. |
| 23 | Price history chart card | A Lovelace card that renders a sparkline of `price_history` for a selected product alongside its rolling average line. |
| 24 | Products tab search/filter | A text input on the Products tab to filter the product list by name. |
