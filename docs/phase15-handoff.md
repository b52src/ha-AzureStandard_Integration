# Phase 15 Handoff — Unseen Reorder Badge (v0.1.6)

## What changed

### `www/azure-standard-panel.js` only

No Python files were modified. All changes are UI-only.

---

## Feature: unseen reorder badge

**Problem:** In Phase 13/14 the Products tab showed a red badge with the raw
reorder-due count. Every hass update re-rendered the badge at the same value,
so it was always "red" once any product became overdue — there was no way to
acknowledge it.

**Solution:** Track how many reorder-due products the user last saw when they
visited the Products tab. Only show the badge when the current count *exceeds*
the last-seen count.

### How it works

| State | Badge shown? |
|---|---|
| 0 reorder-due products | No badge |
| Products tab never visited, 2 overdue | Badge: 2 |
| User visits Products tab (2 overdue) | Badge clears (`_seenReorderCount = 2`) |
| A 3rd product becomes overdue | Badge: 1 (3 − 2) |
| User re-orders 1 product (now 2 overdue) | No badge (2 ≤ 2 seen, clamped to 0) |

### Implementation

**`constructor()`** — new instance variable:
```js
this._seenReorderCount = 0;
```

**`_render()` — `unseenCount` computed after `reorderCount`:**
```js
const unseenCount = Math.max(0, reorderCount - this._seenReorderCount);
```
The tab badge uses `unseenCount` instead of `reorderCount`.

**Tab-click handler** — mark as seen when switching to Products:
```js
if (this._tab === "products") {
  this._seenReorderCount = reorderCount;
}
```

**`#go-products` button** — same mark-seen logic:
```js
this._tab = "products";
this._seenReorderCount = reorderCount;
this._render();
```

---

## Feature: reorder alert banner (Summary tab)

When `unseenCount > 0` and the user is on the Summary tab, an amber banner is
rendered at the bottom of the Summary tab content:

```html
<div class="reorder-alert">
  <span class="reorder-alert-icon">⚠</span>
  <span>2 products due for reorder</span>
  <button class="reorder-alert-btn" id="go-products">View Products →</button>
</div>
```

Clicking "View Products →" jumps to the Products tab and clears the badge in one
action — no extra click needed.

The banner is hidden when `unseenCount === 0` (no unseen overdue products).

### CSS

New rules added to `_css()`:

```css
.reorder-alert          — amber flex row (background #fff7ed, border #fed7aa)
.reorder-alert-icon     — ⚠ icon, slightly larger font
.reorder-alert-btn      — right-aligned ghost button, orange border/text
.reorder-alert-btn:hover — light red fill on hover
```

---

## Files changed

```
custom_components/azure_standard/
├── manifest.json                     — version 0.1.5 → 0.1.6
└── www/
    └── azure-standard-panel.js       — _seenReorderCount, unseenCount, alert banner, CSS

CHANGELOG.md                          — 0.1.6 entry added
docs/phase15-handoff.md               ← this file
```

---

## Behaviour summary

| Scenario | Result |
|---|---|
| No tracked products | No badge, no alert |
| Products overdue on first panel open | Badge shows count, Summary alert visible |
| User clicks Products tab | Badge clears, alert disappears |
| User clicks "View Products →" in alert | Navigates to Products, badge + alert clear |
| Product re-ordered (count drops) | No stale badge (clamped to 0) |
| New product becomes overdue after seen | Badge shows delta (new − seen) |

---

## Test steps

1. Deploy updated `custom_components/azure_standard/` and hard-refresh browser
   (Ctrl+Shift+R) to clear the JS cache.
2. Confirm `manifest.json` and panel footer both show **v0.1.6**.
3. If you have tracked products with `_reorder_due` = `true`:
   - Open the panel on Summary tab — amber alert banner should appear.
   - Products tab badge should show the count.
   - Click the Products tab — badge disappears, alert disappears on return to Summary.
   - Click "View Products →" in the alert — same result in one click.
4. If reorder-due count is 0 — no badge, no alert.
5. Verify the amber alert is absent when the user is already on the Products tab
   (the alert only appears on Summary when `unseenCount > 0`).

---

## Syntax check (no Python changes, but sanity-check anyway)

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
fj release create "v0.1.6" --tag v0.1.6 \
  --body "Phase 15: unseen reorder badge — Products tab badge only appears when reorder-due count increases since last visit; amber alert banner on Summary tab with direct jump to Products."
fj release list   # confirm v0.1.6 appears
```

---

## Next iteration ideas (Phase 16+)

| Phase | Name | Description |
|---|---|---|
| 16 | Automation blueprints | Blueprint YAML files for: notify on cutoff approaching, alert when order window opens, push reminder when reorder-due products appear. |
| 17 | Panel config UI | Options to show/hide individual tabs; persisted via HA storage. |
| 18 | Cutoff countdown widget | Compact HA card (lovelace) for dashboards showing days-until-cutoff with color coding, independent of the sidebar panel. |
