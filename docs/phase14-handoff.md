# Phase 14 Handoff — Persistent Price History (v0.1.5)

## What changed

### `coordinator.py`
- **New import**: `homeassistant.helpers.storage.Store`.
- **`__init__`** — creates `self._store: Store` using `STORAGE_KEY_PRICE_HISTORY`
  (`"azure_standard.price_history"`) and `STORAGE_VERSION` (`1`), then immediately
  schedules `self._async_load_price_history()` as an `hass.async_create_task` so
  stored data is ready before the first coordinator update fires.
- **`_async_load_price_history()`** (new method) — awaits `self._store.async_load()`,
  validates the result is a `dict`, skips non-numeric entries, and clamps each list
  to `_PRICE_HISTORY_MAX` entries. Silently swallows any exception (missing file,
  schema mismatch) so a fresh install starts clean without raising.
- **`_async_save_price_history()`** (new method) — awaits
  `self._store.async_save(dict(self._price_history))`. Silently logs a warning on
  failure rather than raising so a write error doesn't abort the coordinator update.
- **`_async_update_data()`** — inside the `_history_due()` block, after
  `result.price_history` is assigned, calls `await self._async_save_price_history()`.

### `manifest.json`
- `"version"` bumped from `"0.1.4"` to `"0.1.5"`.

### `CHANGELOG.md`
- `[0.1.5]` entry added at the top.

### `www/azure-standard-panel.js`
- Phase comment updated to `Phase 14 / v0.1.5`.
- Footer version fixed from the stale `v0.1.2` to `v0.1.5`.

---

## Storage file

HA writes the data to:
```
<config dir>/.storage/azure_standard.price_history
```

Sample content after two refresh cycles:
```json
{
  "version": 1,
  "minor_version": 1,
  "key": "azure_standard.price_history",
  "data": {
    "BK603": [4.79, 4.89],
    "SW033": [12.49, 12.49]
  }
}
```

The `data` dict is keyed by packaging code with values of floats, oldest first,
capped at 12 entries.

---

## Behaviour on HA restart

| Scenario | Result |
|---|---|
| Normal restart after ≥ 1 price fetch | History restored; sparklines visible immediately on first panel render |
| Fresh install / no storage file yet | `async_load()` returns `None`; `_price_history` stays `{}` |
| Storage file is corrupt / unreadable | Exception caught; `_price_history` stays `{}`; warning logged |
| `_PRICE_HISTORY_MAX` lowered between versions | Excess entries clamped from the front on load |

---

## Test steps

1. **Confirm v0.1.5** — check `manifest.json` or the panel footer after loading.
2. Allow at least one history-fetch cycle (or lower `SCAN_INTERVAL_HISTORY` to
   `timedelta(minutes=1)` in `const.py` for testing).
3. **Restart HA**.
4. Open the sidebar panel → Products tab — sparklines should be visible immediately
   (no waiting for the 24 h cadence).
5. Verify the storage file exists:
   ```bash
   cat <ha-config>/.storage/azure_standard.price_history
   ```
6. Check HA logs at `DEBUG` level for:
   ```
   Loaded price history for N product(s) from storage.
   ```
7. **Edge case — empty store**: delete the file, restart HA, confirm the panel
   shows `—` for all sparklines and no errors appear in the log.

---

## Known limitations / next steps

- The storage format uses version `1` (`STORAGE_VERSION`). Future schema changes
  should increment this and add a migration handler in
  `_async_load_price_history()`.
- Price is still sampled once per `SCAN_INTERVAL_HISTORY` (default 24 h). Users
  with few tracked products won't accumulate 2+ points quickly in production.
- The sparkline shows no price labels or hover tooltips. These can be added in a
  future phase (e.g. a `<title>` element on each SVG circle for native browser
  tooltips, or a custom tooltip overlay).

---

## Release

```bash
fj release create "v0.1.5" --tag v0.1.5 \
  --body "Phase 14: price history now persists across HA restarts via homeassistant.helpers.storage.Store."
fj release list   # confirm v0.1.5 appears
```
