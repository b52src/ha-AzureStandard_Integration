# Phase 16 Handoff — Automation Blueprints (v0.1.7)

## What changed

### New directory: `custom_components/azure_standard/blueprints/`

Three Home Assistant automation blueprint YAML files. No Python files were
modified, no JS files were modified, no existing files were touched beyond
`manifest.json` and `CHANGELOG.md`.

---

## Blueprints

### 1. `azure_standard_cutoff_approaching.yaml`

**Purpose:** Notify N days before the Azure Standard order cutoff so the user
has time to add items before the window closes.

**Trigger:** `sensor.azure_standard_days_until_cutoff` drops below the
configured threshold (`days_threshold`, default **2**).

**Condition:** `binary_sensor.azure_standard_order_window_open` is `on` — the
notification is suppressed if the cutoff has already passed.

**Inputs:**

| Input | Default | Description |
|---|---|---|
| `days_threshold` | 2 | Days before cutoff to fire |
| `notify_target` | — | `notify.*` service (required) |
| `message_template` | See file | Supports `{{ days }}` and `{{ cutoff }}` |
| `title_template` | "Azure Standard order closing soon" | Same variables |

---

### 2. `azure_standard_order_window_opened.yaml`

**Purpose:** Notify the moment the order window opens, so the user knows they
can start building their order.

**Trigger:** `binary_sensor.azure_standard_order_window_open` transitions from
`off` → `on` (rising edge only — no repeated fire on HA restart while already
open).

**Inputs:**

| Input | Default | Description |
|---|---|---|
| `notify_target` | — | `notify.*` service (required) |
| `message_template` | See file | Supports `{{ cutoff }}` and `{{ days }}` |
| `title_template` | "Azure Standard order window open" | Same variables |
| `trigger_only_on_rising_edge` | `true` | Documented option (rising-edge is the trigger by design) |

---

### 3. `azure_standard_reorder_due.yaml`

**Purpose:** Remind the user when tracked products are overdue for reorder.
Optionally repeats on a configurable hourly cadence.

**Trigger:**
- `sensor.azure_standard_reorder_due_count` goes above `minimum_overdue`
- `time_pattern` every hour (guarded by `repeat_hours` input — set to `0` to
  suppress the periodic repeat)

**Condition:** Count must be ≥ `minimum_overdue` at time of execution.

**Inputs:**

| Input | Default | Description |
|---|---|---|
| `notify_target` | — | `notify.*` service (required) |
| `message_template` | See file | Supports `{{ count }}` and `{{ plural }}` |
| `title_template` | "Azure Standard reorder reminder" | Same variables |
| `minimum_overdue` | 1 | Minimum overdue count before notifying |
| `repeat_hours` | 24 | Re-notify every N hours (0 = once per event) |

---

## Files changed

```
custom_components/azure_standard/
├── manifest.json                     — version 0.1.6 → 0.1.7
└── blueprints/                       ← NEW DIRECTORY
    ├── azure_standard_cutoff_approaching.yaml
    ├── azure_standard_order_window_opened.yaml
    └── azure_standard_reorder_due.yaml

CHANGELOG.md                          — 0.1.7 entry added
docs/phase16-handoff.md               ← this file
```

---

## How to import a blueprint

**Method A — file copy (recommended for this integration):**

1. Copy the desired `.yaml` file from `blueprints/` to
   `<HA config>/blueprints/automation/azure_standard/` (create the directory
   if it doesn't exist).
2. In HA, go to **Settings → Automations & Scenes → Blueprints**. The
   blueprint will appear automatically.
3. Click **Create automation from blueprint**, fill in the inputs, and save.

**Method B — import by URL (if the repo is publicly accessible):**

In HA, go to **Settings → Automations & Scenes → Blueprints → Import
Blueprint** and paste the raw URL of the desired `.yaml` file, e.g.:
```
https://forgejo.crow-nest.xyz/scrow/AzureStandard_Intigration/raw/branch/main/custom_components/azure_standard/blueprints/azure_standard_cutoff_approaching.yaml
```

---

## No Python changes — sanity-check anyway

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
fj release create "v0.1.7" --tag v0.1.7 \
  --body "Phase 16: three automation blueprints — cutoff approaching, order window opened, reorder due reminder."
fj release list   # confirm v0.1.7 appears
```

---

## Next iteration ideas (Phase 17+)

| Phase | Name | Description |
|---|---|---|
| 17 | Panel config UI | Options to show/hide individual tabs; persisted via HA storage. |
| 18 | Cutoff countdown widget | Compact Lovelace card showing days-until-cutoff with color coding, independent of the sidebar panel. |
| 19 | On-sale push alert | Automation blueprint (or built-in notification) when a tracked product's price drops below the rolling average sale threshold. |
