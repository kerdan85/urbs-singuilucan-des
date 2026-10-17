# Reproducing the analyses

This folder contains two self-contained scripts that regenerate the main results
and the sensitivity/robustness analyses of the paper on the **four-season
representative-period basis** used throughout, solved with the open-source
**HiGHS** solver (no commercial solver required).

## Setup

```bash
pip install -r analysis/requirements.txt
python analysis/reproduce_analyses.py      # Tables 6-9, Fig. B.1 (sizing + attribution + sensitivities)
python analysis/full_year_operation.py     # Section 4.7 / Table 10 / Fig. 14 (full-year operation)
python analysis/make_figures.py            # Figs. 6, 7, 8 (season-shaded dispatch), 9, 10
```

The bundled `urbs` source is version 1.0.x, written for pandas 1.x. Rather than
editing that source, both scripts apply a **one-line runtime shim** for
pandas >= 2 at import time:

```python
import pandas as pd, types
if not hasattr(pd.core, "index"):
    pd.core.index = types.SimpleNamespace(MultiIndex=pd.MultiIndex)
```

If you prefer to run the original `runme.py` scripts under pandas >= 2, make the
equivalent one-line edit in `urbs/input.py` (replace `pd.core.index.MultiIndex`
with `pd.MultiIndex`).

## Temporal basis: four seasonal representative weeks

Each planning year is represented by **four seasonal characteristic weeks** (one
per meteorological season). Each is a contiguous 120-hour window selected
systematically as the **medoid** week of its season — the window whose mean
electricity demand and mean solar resource most closely match the season's own
means (minimum normalised distance). The four weeks are concatenated (480 h/year)
and solved with cyclic storage per week; urbs rescales costs and energy to annual
operation by the weight `w = 8760 / 480 ≈ 18.3`.

`reproduce_analyses.select_seasonal_weeks()` computes the four week-start hours
from the reference building's demand and solar, so they are reproduced rather than
hard-coded (they come out at roughly early-February, late-March, early-August and
late-November). Long-duration hydrogen storage is the one quantity sensitive to any
non-chronological representative scheme; it is bracketed between the single
maximum-demand week and the worst contiguous low-solar fortnight.

## Scripts and where they appear in the paper

`reproduce_analyses.py` — main sizing results and robustness:

| Function | Paper reference |
|---|---|
| `reproduce()`        | Six-scenario capacities and costs on the four-season basis (Tables 7-8) |
| `attribution()`      | Envelope vs. LED attribution from the two IES VE intermediate configurations in `intermediate_demand.csv` (Tables 5-6); the lighting-only case shows the space-heating rebound |
| `zero_export()`      | Zero export-compensation sensitivity (Section 4.6) |
| `cost_sensitivity()` | +/-25% PV and battery CAPEX sensitivity, cost-sensitivity tornado (Fig. B.1) |
| `offgrid_bounds()`   | Off-grid hydrogen store across temporal bases — seasonal vs single week vs worst fortnight (Table 9, Fig. 13) |

`make_figures.py` — regenerates the main data-driven figures from a fresh four-season solve:

| Output file | Paper figure |
|---|---|
| `figures/comp_capacity_scenarios.png` | DER capacities by scenario (Fig. 6) |
| `figures/comp_cost_scenarios.png`     | System-cost composition (Fig. 7) |
| `figures/disp_grid_all.png`           | Season-shaded electricity dispatch over the four representative weeks (Fig. 8) |
| `figures/tech_mix.png`                | Energy-system technology mix, 2040 (Fig. 9) |
| `figures/interperiod_s6.png`          | Inter-period evolution of S6 (Fig. 10) |

The dispatch figure shades each of the four non-contiguous seasonal weeks (winter,
spring, summer, autumn) so the discontinuity is explicit. Figures use Matplotlib's
default font rather than the manuscript's; the data are identical.

`full_year_operation.py` — chronological full-year (8,760 h) operational validation:

| Output | Paper reference |
|---|---|
| Annual self-sufficiency, self-consumption, import/export, loss-of-load, battery cycles | Section 4.7, Table 10 |
| Monthly series (`full_year_operation_results.json`) for the annual bars and monthly loss-of-load | Fig. 14 |

Each scenario's 2040 design is first sized on the four seasonal weeks (via
`design_caps`, which imports the medoid-week selection from `reproduce_analyses`),
then fixed, and its hourly dispatch is simulated month by month over the full TMY
year. Auxiliary heat/electricity dump and high-penalty unmet-load processes make
the operation well-posed and measure surplus/shortfall explicitly; solar-thermal is
treated as curtailable. Off-grid loss-of-load is a conservative upper bound (no
inter-month hydrogen carryover) and comes out small (~0.5-1% of annual demand),
confirming that the four-season sizing is operationally adequate. Run time is a few
minutes per scenario on commodity hardware.
