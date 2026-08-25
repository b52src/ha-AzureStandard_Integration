# Phase 19 Handoff — Price Drop Alert Blueprint (v0.2.0)

## What changed

### New: `custom_components/azure_standard/blueprints/azure_standard_price_drop.yaml`

A HA automation blueprint that fires a notification when a tracked product's
`last_price` attribute drops to or below a configurable fraction of its rolling
average (`price_history`). No Python code was changed. No sensors or entities
were added or modified.

### Modified: `custom_components/azure_standard/manifest.json`

Version bumped `0.1.9` → `0.2.0` to mark the completion of the v0.2 blueprint
suite (all four blueprints are now in place).

---

## Feature description

### `azure_standard_price_drop` blueprint

#### How it works

The integration stores purchase prices in the `price_history` attribute of each
`sensor.azure_standard_*_last_ordered` entity — a list of floats, oldest first,
capped at 12 samples. The `last_price` attribute always holds the most recently
sampled price.

The blueprint watches a single user-selected product sensor. Each time
`last_price` changes, two conditions are evaluated:

1. **Minimum samples guard** — `price_history` must have at least `min_samples`
   entries (default 3) before the rolling average is considered meaningful.
2. **Price-drop condition** — `last_price` must be ≤ `threshold_pct` × rolling
   average. Default `threshold_pct` is `0.95`, meaning the price must be at
   least 5% below the average before the alert fires.

If both conditions pass, a `notify.*` service call is made with a fully
templated title and message.

#### Blueprint inputs

| Input | Type | Default | Description |
|---|---|---|---|
| `product_sensor` | `entity` (domain: sensor) | — | `sensor.azure_standard_*_last_ordered` to watch |
| `notify_target` | `text` | — | `notify.*` service to call |
| `threshold_pct` | `number` (0.50–1.00, step 0.01) | `0.95` | Fire when price ≤ this fraction of rolling avg |
| `min_samples` | `number` (2–12, step 1) | `3` | Minimum history entries before alert can fire |
| `message_template` | `text` (multiline) | See below | Jinja2 notification body |
| `title_template` | `text` | `"Azure Standard price drop"` | Jinja2 notification title |

#### Default message template

```
{{ name }} is on sale for ${{ price }} (avg ${{ avg }}, {{ pct_off }}% off). Order window: {{ cutoff }}.
```

#### Template variables available in message/title

| Variable | Value |
|---|---|
| `{{ name }}` | `state_attr(product_sensor, 'friendly_name')` (falls back to entity ID) |
| `{{ price }}` | `last_price` attribute, rounded to 2 dp |
| `{{ avg }}` | Rolling average of `price_history`, rounded to 2 dp |
| `{{ pct_off }}` | `(avg - price) / avg × 100`, rounded to 1 dp |
| `{{ cutoff }}` | State of `sensor.azure_standard_next_cutoff` |

#### Trigger approach

HA's `numeric_state` trigger cannot evaluate a dynamic `below:` threshold
(it only accepts a static number or a `value_template` that must evaluate to a
number, not a comparison). The blueprint uses a `state` trigger on the
`last_price` attribute instead, then performs the full comparison in a
`condition: template` block using `value_template`. This is more explicit and
avoids the risk of the trigger firing on every sub-threshold value change
without the condition gate.

---

## Usage

### Import the blueprint

**Settings → Automations & Scenes → Blueprints → Import Blueprint**

Paste the raw URL:

```
https://forgejo.crow-nest.xyz/scrow/AzureStandard_Intigration/raw/branch/main/custom_components/azure_standard/blueprints/azure_standard_price_drop.yaml
```

Or, because the file ships inside the integration directory, it is available
locally at:

```
custom_components/azure_standard/blueprints/azure_standard_price_drop.yaml
```

### Create an automation from the blueprint

1. Open the imported blueprint and click **Create Automation**.
2. Set **Product sensor** to the desired `sensor.azure_standard_*_last_ordered` entity.
3. Set **Notification target** (e.g. `notify.mobile_app_my_phone`).
4. Adjust **Price drop threshold** and **Minimum samples** as desired.
5. Save. Repeat for each product you want to monitor.

### Example YAML (manual automation)

```yaml
alias: "Price drop — Whole Wheat Flour"
use_blueprint:
  path: azure_standard/azure_standard_price_drop.yaml
  input:
    product_sensor: sensor.azure_standard_whole_wheat_flour_last_ordered
    notify_target: notify.mobile_app_my_phone
    threshold_pct: 0.95
    min_samples: 3
    title_template: "Azure Standard price drop"
    message_template: >-
      {{ name }} is on sale for ${{ price }} (avg ${{ avg }},
      {{ pct_off }}% off). Order window: {{ cutoff }}.
```

---

## Implementation details

### Trigger

```yaml
- trigger: state
  entity_id: !input product_sensor
  attribute: last_price
  id: "price_changed"
```

A `state` trigger on `last_price` fires on every attribute change. The
conditions below gate on the actual price comparison.

### Condition 1 — minimum samples

```yaml
- condition: template
  value_template: >-
    {% set history = state_attr(product_sensor, 'price_history') %}
    {{ history is not none and (history | length) >= (min_samples | int(3)) }}
```

### Condition 2 — price drop

```yaml
- condition: template
  value_template: >-
    {% set history = state_attr(product_sensor, 'price_history') %}
    {% set price = state_attr(product_sensor, 'last_price') | float(-1) %}
    {% if history is none or (history | length) == 0 or price < 0 %}
      false
    {% else %}
      {% set avg = (history | map('float') | sum) / (history | length) %}
      {{ price <= avg * (threshold_pct | float(0.95)) }}
    {% endif %}
```

### Action — variables + notify

Template variables (`name`, `price`, `avg`, `pct_off`, `cutoff`) are computed
in an `action: variables` block before the `notify.*` call. All `!input`
references (`product_sensor`, `threshold_pct`, `min_samples`) are also
re-hoisted into the variables block so they resolve correctly inside the
template evaluation context.

---

## Blueprint inventory (complete as of v0.2.0)

| File | Description |
|---|---|
| `azure_standard_cutoff_approaching.yaml` | Notify N days before the order cutoff |
| `azure_standard_order_window_opened.yaml` | Notify when the order window opens |
| `azure_standard_reorder_due.yaml` | Notify when tracked products go overdue for reorder |
| `azure_standard_price_drop.yaml` | ← **NEW** — Notify when a product price drops below its rolling average |

---

## Files changed

```
custom_components/azure_standard/
├── manifest.json                                      — version 0.1.9 → 0.2.0
└── blueprints/
    └── azure_standard_price_drop.yaml                ← NEW (122 lines)

CHANGELOG.md                                          — 0.2.0 entry added
docs/phase19-handoff.md                              ← this file
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
fj release create "v0.2.0" --tag v0.2.0 \
  --body "Phase 19: azure_standard_price_drop blueprint — notify when a tracked product price drops below its rolling average."
fj release list   # confirm v0.2.0 appears
```

---

## Next iteration ideas (Phase 20+)

| Phase | Name | Description |
|---|---|---|
| 20 | Panel settings v2 | Per-product show/hide in the Products tab; optional compact/expanded view toggle. |
| 21 | Resource auto-registration | Register cutoff-card JS as a Lovelace resource automatically on integration setup, removing the manual "Settings → Dashboards → Resources" step. |
| 22 | Multi-product price drop | Extend the price drop blueprint (or add a companion) to watch all tracked products at once using a sensor group or the `reorder_due_count` pattern. |
| 23 | Price history chart card | A Lovelace card that renders a sparkline of `price_history` for a selected product alongside its rolling average line. |
