# urbs energy-system models — Singuilucan ecotourism lodging (six scenarios)

Distributed-energy-system (DES) optimisation models built on [`urbs`](https://github.com/tum-ens/urbs)
(v1.0.1) for the study:

> **Integrated Building Energy Simulation and Energy Systems Optimisation Modelling
> for Low-Carbon Design under Uncertain Demand**
> Iván Puente Antonio (UNAM) and Iván García Kerdan (Tecnológico de Monterrey).

The models size and dispatch on-site generation and storage for a rural ecotourism
lodging unit in Singuilucan, Hidalgo, Mexico. Hourly demand profiles are produced with
IES VE (building physics) and passed to `urbs` (linear optimisation). Each scenario is
optimised over a representative week (120 hourly steps) for four planning years
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
    runme.py                run script (timesteps 2329–2449 = representative week)
    urbs/                   urbs source (GPL-3.0)
    result/                 outputs: *.xlsx, dispatch *.png  (large *.h5 not tracked)
Resultados.xlsx             consolidated cost comparison across scenarios
```

## Reproducing a scenario

Requires Python with `pyomo`, `pandas`, `openpyxl`, `matplotlib` and a MILP/LP solver
(e.g. GLPK or Gurobi), as used by urbs 1.0.1.

```bash
cd BAU/urbs-1.0.1-BAU
python runme.py
```

Outputs are written to `result/`. `Resultados.xlsx` aggregates the cost breakdown
(`Costs` sheet) used in the paper.

## Key results (system cost over the 15-year horizon, USD)

| | S1/S4 Grid | S2/S5 Off-grid | S3/S6 Carbon-priced |
|---|---|---|---|
| Reference (BAU) | 166,013 | 176,592 | 181,216 |
| Proposed (Passive) | 87,717 | 93,193 | 91,246 |

The passive envelope roughly halves every DER portfolio and cuts total cost by 47–50 %
(43–46 % including the estimated passive-construction premium).

## License

Code inherits the **GPL-3.0** license of `urbs` (see `LICENSE`). Input data and results
in this repository are released under the same terms for reproducibility.

## Citation

See `CITATION.cff`. Once archived on Zenodo, cite via the minted DOI.
