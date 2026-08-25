# Phase 17 Handoff — Panel Config UI (v0.1.8)

## What changed

### Modified: `custom_components/azure_standard/www/azure-standard-panel.js`

A permanent **⚙ Settings tab** was added to the sidebar panel. No Python files
were modified. No HA storage helpers were added. No existing entity sensors were
changed.

---

## Feature description

### Settings tab — show/hide content tabs

The Settings tab is always visible as a right-aligned gear icon (`⚙`) in the tab
bar. It renders a simple form with one checkbox per togglable tab:

| Tab | Default | Can be hidden |
|---|---|---|
| Summary | ✓ | No — always on |
| Lists | ✓ | Yes |
| Products | ✓ | Yes |
| Account | ✓ | Yes |

Changes take effect immediately: checking or unchecking a box re-renders the tab
bar in the same paint cycle. Hiding the currently active tab redirects the panel
to Summary.

A **Reset to defaults** button restores all three tabs to visible.

### Persistence

Preferences are stored in `localStorage` under the key
`azure_standard_panel_tab_visibility` as a compact JSON object, e.g.:

```json
{"lists": true, "products": false, "account": true}
```

`localStorage` is the correct primitive for HA custom panel state:
- It survives HA restarts and page reloads without any Python storage helper.
- It is scoped to the browser origin, so it does not leak between HA instances.
- It merges with hard-coded defaults on load, so future new tabs default to
  visible even if older persisted data omits them.

---

## Implementation details

### New constants (module scope)

```js
const _STORAGE_KEY = "azure_standard_panel_tab_visibility";
const _TAB_DEFAULTS = { lists: true, products: true, account: true };
```

### New instance members on `AzureStandardPanel`

| Member | Type | Purpose |
|---|---|---|
| `_tabVis` | `object` | Current visibility state (`{ lists, products, account }`) |

### New methods

| Method | Description |
|---|---|
| `_loadTabVis()` | Reads `localStorage`, merges with `_TAB_DEFAULTS`. Returns defaults on error. |
| `_saveTabVis()` | Writes `_tabVis` to `localStorage`. Silently ignores quota/security errors. |

### Tab bar change

Content tabs are now gated by both `hasAccount` **and** the relevant `_tabVis`
flag:

```js
...(hasAccount && this._tabVis.lists    ? [{ id: "lists",    … }] : []),
...(hasAccount && this._tabVis.products ? [{ id: "products", … }] : []),
...(hasAccount && this._tabVis.account  ? [{ id: "account",  … }] : []),
{ id: "settings", label: "⚙", title: "Panel settings" },  // always last
```

The Settings tab button gets the `.tab-settings` CSS class which applies
`margin-left: auto` to push it flush-right.

### Event listeners added in `_render()`

```js
// Checkbox change → save → re-render (auto-redirects if active tab was hidden)
["lists", "products", "account"].forEach((key) => {
  document.getElementById(`vis-${key}`)?.addEventListener("change", …);
});

// Reset → restore _TAB_DEFAULTS → save → re-render
document.getElementById("btn-reset-vis")?.addEventListener("click", …);
```

---

## Files changed

```
custom_components/azure_standard/
├── manifest.json                  — version 0.1.7 → 0.1.8
└── www/
    └── azure-standard-panel.js   — Settings tab added

CHANGELOG.md                       — 0.1.8 entry added
docs/phase17-handoff.md            ← this file
```

---

## Sanity check (no Python changes, but verify compile still passes)

```bash
cd /Users/seancrow/Forgejo/AzureStandard_Intigration
.venv/bin/python3 -m py_compile \
  custom_components/azure_standard/api.py \
  custom_components/azure_standard/coordinator.py \
  custom_components/azure_standard/config_flow.py \
  custom_components/azure_standard/sensor.py \
  custom_components/azure_standard/const.py \
  custom_components/azure_standard/discovery.py
```

---

## Release

```bash
fj release create "v0.1.8" --tag v0.1.8 \
  --body "Phase 17: panel config UI — ⚙ Settings tab to show/hide Lists, Products, and Account tabs; preferences saved to localStorage."
fj release list   # confirm v0.1.8 appears
```

---

## Next iteration ideas (Phase 18+)

| Phase | Name | Description |
|---|---|---|
| 18 | Cutoff countdown widget | Compact Lovelace card showing days-until-cutoff with color coding, independent of the sidebar panel. |
| 19 | On-sale push alert | Automation blueprint (or built-in notification) when a tracked product's price drops below the rolling average sale threshold. |
| 20 | Panel settings v2 | Per-product show/hide in the Products tab; optional compact/expanded view toggle. |
