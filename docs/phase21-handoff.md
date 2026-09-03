# Phase 21 Handoff — Lovelace Resource Auto-Registration (v0.2.1)

## What changed

### Modified: `custom_components/azure_standard/__init__.py`

- **Removed** the old `_CUTOFF_CARD_JS` string constant (it was a dead comment —
  no code used it after Phase 18).
- **Added** `_LOVELACE_RESOURCES` — a list of the two JS resource descriptors
  (`res_type`, `url`) that must be registered for both the cutoff card and the
  panel JS to be available in Lovelace.
- **Added** `_RESOURCE_IDS_KEY` — a `hass.data` key used to track which resource
  IDs this integration registered, so they can be cleaned up on unload.
- **`async_setup_entry`** — after registering the sidebar panel, calls
  `_async_register_lovelace_resources(hass)` the first time any config entry
  sets up (guarded by `_RESOURCE_IDS_KEY not in hass.data`).
- **`async_unload_entry`** — calls `_async_remove_lovelace_resources(hass)` when
  the last config entry is unloaded (same guard as the existing panel-removal
  block).
- **`_async_register_lovelace_resources(hass)`** — new helper. Loads the Lovelace
  resource storage, skips any URL already present, creates new entries for the
  rest, and stores the resulting IDs in `hass.data[_RESOURCE_IDS_KEY]`.
- **`_async_remove_lovelace_resources(hass)`** — new helper. Pops the stored IDs
  from `hass.data` and calls `async_delete_item` for each one.

### Modified: `custom_components/azure_standard/manifest.json`

Version bumped `0.2.0` → `0.2.1`.

---

## Feature description

### Problem solved

Before this phase, users had to manually navigate to **Settings → Dashboards →
Resources** and add two entries:

```
/azure_standard_panel/azure-standard-cutoff-card.js  (type: JavaScript Module)
/azure_standard_panel/azure-standard-panel.js         (type: JavaScript Module)
```

Without this step, the `azure-standard-cutoff-card` would not appear in the
Lovelace card picker and could not be used in a dashboard.

### Solution

`async_setup_entry` now calls into `hass.data["lovelace"].resources` — the same
storage object HA's built-in Lovelace UI writes to — to register the two JS
files automatically when the integration loads.

### Idempotency

`resources.async_items()` is checked before every `async_create_item` call. A
URL that is already registered (from a previous install, a failed reload, or a
manual user addition) is silently skipped. The operation is safe to call on every
HA restart.

### Degraded mode (YAML Lovelace / unusual HA setups)

If `hass.data["lovelace"]` is absent or lacks a `resources` attribute (e.g. when
Lovelace is configured in YAML mode), the helper logs a DEBUG message and returns
without error. Setup proceeds normally. Users in this configuration can still add
the resources manually as before.

### Cleanup on unload

Resource IDs returned by `async_create_item` are stored in
`hass.data[_RESOURCE_IDS_KEY]`. When the integration's last config entry is
unloaded, `_async_remove_lovelace_resources` iterates those IDs and calls
`async_delete_item` for each. Any ID that has already been removed (manually or
by a previous unload) raises an exception that is caught and logged at DEBUG
level — unload always succeeds.

---

## API surface used

```
hass.data["lovelace"].resources          # LovelaceResources storage object
  .async_load(force=True)                # refresh from storage
  .async_items()                         # list[dict] — current resources
  .async_create_item({"res_type", "url"})# returns str ID
  .async_delete_item(id: str)            # removes resource
```

This API has been stable since HA 2022.12. No import is required — the object is
accessed through `hass.data`, matching the pattern used by other custom
integrations (e.g. `browser_mod`, `custom-sidebar`).

---

## Files changed

```
custom_components/azure_standard/
└── __init__.py    — resource auto-registration helpers added (~60 lines)
└── manifest.json  — version 0.2.0 → 0.2.1

CHANGELOG.md       — 0.2.1 entry added
docs/phase21-handoff.md  ← this file
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

All files pass `py_compile` with no errors or warnings.

---

## Release

```bash
fj release create "v0.2.1" --tag v0.2.1 \
  --body "Phase 21: Auto-register Lovelace resources on integration setup — cutoff card now works immediately after install without a manual Resources step."
fj release list   # confirm v0.2.1 appears
```

---

## Next iteration ideas (Phase 22+)

| Phase | Name | Description |
|---|---|---|
| 20 | Panel settings v2 | Per-product show/hide in the Products tab; optional compact/expanded view toggle. |
| 22 | Multi-product price drop | Extend the price drop blueprint (or add a companion) to watch all tracked products at once using a sensor group or the `reorder_due_count` pattern. |
| 23 | Price history chart card | A Lovelace card that renders a sparkline of `price_history` for a selected product alongside its rolling average line. |
