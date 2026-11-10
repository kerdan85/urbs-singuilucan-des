# urbs energy-system models — Singuilucan ecotourism lodging (six scenarios)

[![DOI](https://zenodo.org/badge/1302255996.svg)](https://doi.org/10.5281/zenodo.21387231)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

Distributed-energy-system (DES) optimisation models built on [`urbs`](https://github.com/tum-ens/urbs)
(v1.0.1) for the study:

> **Building demand-side strategies reshape distributed energy system sizing,
> storage and cost in a data-scarce rural development**
> Iván Puente Antonio (UNAM) and Iván García Kerdan (Tecnológico de Monterrey).

The models size and dispatch on-site generation and storage for a rural ecotourism
development in Singuilucan, Hidalgo, Mexico. Hourly demand profiles are produced with
IES VE (building physics) and passed to `urbs` (linear optimisation). Each scenario is
optimised over four seasonal representative weeks (480 hourly steps) for four planning years
(2025, 2030, 2035, 2040).

## Scenario design (2 × 3)

Two envelope configurations × three operating settings:

| Scenario | Folder | Envelope | Setting |
|----------|--------|----------|---------|
| S1 | `BAU/urbs-1.0.1-BAU`               | Reference (conventional) | Grid-connected (import/export) |
| S2 | `BAU/urbs-1.0.1-BAU-Aislado`       | Reference | Off-grid (autonomous) |
| S3 | `BAU/urbs-1.0.1-BAU-CO2-medio`     | Reference | Carbon-priced (25→120 USD/tCO₂) |
| S4 | `Proposed/urbs-1.0.1-Proposed`         | Proposed (passive) | Grid-connected (import/export) |
| S5 | `Proposed/urbs-1.0.1-Proposed-Aislado` | Proposed | Off-grid (autonomous) |
| S6 | `Proposed/urbs-1.0.1-Proposed-CO2medio`| Proposed | Carbon-priced (25→120 USD/tCO₂) |

The carbon-priced scenarios apply a rising CO₂ price of 25, 60, 90 and 120 USD/tCO₂
in 2025, 2030, 2035 and 2040 respectively.

## Repository layout

```
BAU/ , Proposed/            one urbs copy per scenario
  urbs-1.0.1-*/
    Input/2025..2040.xlsx   model inputs per planning year
    runme.py                single-week run script (see analysis/ for the four-season main results)
    urbs/                   urbs source (GPL-3.0)
    result/                 outputs: *.xlsx, dispatch *.png  (large *.h5 not tracked)
Resultados.xlsx             consolidated cost comparison across scenarios
```

## Reproducing a scenario

Requires Python with `pyomo`, `pandas`, `openpyxl`, `matplotlib` and an LP solver.
The analyses in this repository use the open-source **HiGHS** solver (`pip install
highspy`, called through Pyomo's `appsi_highs`); any solver supported by urbs 1.0.1
(e.g. GLPK, CBC, Gurobi) also works.

```bash
cd BAU/urbs-1.0.1-BAU
python runme.py
```

Outputs are written to `result/`. Each scenario's `runme.py` solves the single
maximum-demand week (`timesteps 2329–2449`), which corresponds to the single-week
*sensitivity* case in the paper. **The paper's main results use four seasonal
representative weeks and are reproduced by `analysis/reproduce_analyses.py`** (see
`analysis/README.md`), which rebuilds the four-week input series and solves with HiGHS.

> **pandas >= 2 note.** urbs 1.0.1 was written for pandas 1.x. Under pandas >= 2,
> replace `pd.core.index.MultiIndex` with `pd.MultiIndex` in `urbs/input.py`
> (a one-line change). The reproduction script in `analysis/` applies the
> equivalent shim automatically.

## Analysis & reproducibility

The `analysis/` folder contains two self-contained scripts that solve with the
open-source HiGHS solver and map each output to the corresponding paper table/figure
(see `analysis/README.md` for details and `analysis/requirements.txt` for the environment):

- `reproduce_analyses.py` — the sizing sensitivity and robustness results (zero
  export-compensation, +/-25% technology-cost sensitivity, the carbon-price
  heat-dispatch threshold, and off-grid sizing across time horizons).
- `full_year_operation.py` — the chronological full-year (8,760-hour) operational
  simulation of each fixed design: annual self-sufficiency, self-consumption,
  grid exchange, off-grid loss-of-load and battery cycles (Section 4.9, Table 11, Fig. 15).

```bash
pip install -r analysis/requirements.txt
python analysis/reproduce_analyses.py
python analysis/full_year_operation.py
```

## Key results (system cost over the 15-year horizon, USD)

| | S1/S4 Grid | S2/S5 Off-grid | S3/S6 Carbon-priced |
|---|---|---|---|
| Reference (BAU) | 164,860 | 202,455 | 209,890 |
| Proposed (Passive) | 89,077 | 106,817 | 94,315 |

The demand-side (passive-envelope + LED) design roughly halves every DER portfolio and cuts
the energy-system cost by 46–55 %; including the estimated ~50,000 USD passive-envelope + LED
construction premium for the development, the whole-life saving is 16–31 %. (Values on the
four-season representative-period basis; see `analysis/`.)

## License

Code inherits the **GPL-3.0** license of `urbs` (see `LICENSE`). Input data and results
in this repository are released under the same terms for reproducibility.

## Citation

See `CITATION.cff`. Once archived on Zenodo, cite via the minted DOI.
