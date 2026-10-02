# Reproducing the analyses

This folder contains a single self-contained script, `reproduce_analyses.py`,
that regenerates the sensitivity and robustness results reported in the revised
manuscript. The six base-case scenario models themselves are run with the
original `runme.py` inside each scenario folder; this script adds the analyses
introduced during revision.

## Setup

```bash
pip install -r analysis/requirements.txt
python analysis/reproduce_analyses.py
```

No commercial solver is required: the linear programs are solved with the
open-source **HiGHS** solver through Pyomo's `appsi_highs` interface.

The bundled `urbs` source is version 1.0.x, written for pandas 1.x. Rather than
editing that source, the script applies a **one-line runtime shim** for
pandas >= 2 at import time:

```python
import pandas as pd, types
if not hasattr(pd.core, "index"):
    pd.core.index = types.SimpleNamespace(MultiIndex=pd.MultiIndex)
```

If you prefer to run the original `runme.py` scripts under pandas >= 2, make the
equivalent one-line edit in `urbs/input.py` (replace `pd.core.index.MultiIndex`
with `pd.MultiIndex`).

## What the script produces, and where it appears in the paper

| Function in `reproduce_analyses.py` | Paper reference |
|---|---|
| `reproduce()`          | Six-scenario capacities and costs (Tables 7-8) |
| `zero_export()`        | Zero export-compensation sensitivity (Section 4.8) |
| `cost_sensitivity()`   | +/-25% PV and battery CAPEX sensitivity (Section 4.8) |
| `carbon_threshold()`   | Carbon-price heat-dispatch switch point (Fig. 12) |
| `offgrid_horizons()`   | Off-grid sizing across time horizons (Table 9, Fig. 13) |

## Representative-period approach

The dispatch problems are solved over a representative period rather than the
full 8760 hours. A full-year, multi-stage co-optimisation of generation,
storage and dispatch for all six scenarios is computationally prohibitive on
commodity hardware, so the model uses the maximum-demand week
(`timesteps = range(2329, 2450)`, i.e. the 120 hours following hour 2329) with
cyclic storage state-of-charge. urbs rescales fixed and variable costs by the
period weight `w = 8760 / (len(timesteps) * dt)` automatically, so annual costs
remain consistent. The off-grid analysis (`offgrid_horizons()`) additionally
re-solves over longer contiguous windows (a low-solar month and a worst-case
low-solar fortnight) to confirm that autonomy sizing is governed by the
critical low-generation stretch rather than by the representative week.
