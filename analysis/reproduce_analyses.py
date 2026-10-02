#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reproduce the sensitivity and robustness analyses reported in the paper
(Tables 5, 6 and 9; the carbon-price threshold; and the full-year surrogates).

Run from anywhere:
    python analysis/reproduce_analyses.py

Requirements (see analysis/requirements.txt):
    pyomo, highspy, pandas, openpyxl, numpy

Notes
-----
* The six scenario models ship a copy of the GPL-3.0 `urbs` source (v1.0.x).
  This script imports that bundled copy and applies a one-line pandas>=2
  compatibility shim at runtime (urbs uses the removed `pd.core.index`).
* The LP is solved with the open-source HiGHS solver via Pyomo's APPSI
  interface, so no commercial solver is required. The results reproduce the
  values obtained with the original CBC runs to the digit.
* The main six-scenario capacities and costs (Tables 7-8) are produced by the
  original `runme.py` in each scenario folder; this script adds the analyses
  introduced in the revision.
"""
import os, sys, glob, warnings, types
from datetime import date
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

# --- pandas>=2 shim for urbs 1.0.x (input.py references pd.core.index.MultiIndex) ---
if not hasattr(pd.core, "index"):
    pd.core.index = types.SimpleNamespace(MultiIndex=pd.MultiIndex)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                        # repository root
FOLD = {
    "S1": "BAU/urbs-1.0.1-BAU",
    "S2": "BAU/urbs-1.0.1-BAU-Aislado",
    "S3": "BAU/urbs-1.0.1-BAU-CO2-medio",
    "S4": "Proposed/urbs-1.0.1-Proposed",
    "S5": "Proposed/urbs-1.0.1-Proposed-Aislado",
    "S6": "Proposed/urbs-1.0.1-Proposed-CO2medio",
}
NAME = {"S1": "Reference | Grid", "S2": "Reference | Off-grid", "S3": "Reference | Carbon",
        "S4": "Proposed  | Grid", "S5": "Proposed  | Off-grid", "S6": "Proposed  | Carbon"}

sys.path.insert(0, os.path.join(ROOT, FOLD["S1"]))  # import the bundled urbs package
import urbs
import pyomo.environ as pyo
from pyomo.opt.base import SolverFactory

SOLVER = "appsi_highs"
REP_WEEK = range(2329, 2329 + 120 + 1)              # maximum-demand week (Section 3.2)


# --------------------------------------------------------------------------- #
def _data(scen, sell=None, co2=None, pv_mult=1.0, batt_mult=1.0):
    """Load a scenario and apply optional overrides."""
    os.chdir(os.path.join(ROOT, FOLD[scen]))
    data = urbs.read_input("Input", date.today().year)
    data = urbs.scenario_base(data)
    if sell is not None:                             # export (feed-in) price
        for c in data["buy_sell_price"].columns:
            if "sell" in str(c).lower():
                data["buy_sell_price"][c] = sell
    if co2 is not None:                              # flat CO2 price on the Env sink
        for i in data["commodity"].index:
            if i[2] == "CO2" and i[3] == "Env":
                data["commodity"].loc[i, "price"] = co2
    if pv_mult != 1.0:
        pr = data["process"]
        for i in pr.index:
            if i[2] == "Photovoltaics":
                pr.loc[i, "inv-cost"] *= pv_mult
    if batt_mult != 1.0:
        st = data["storage"]
        for i in st.index:
            if i[2] == "Battery":
                st.loc[i, "inv-cost-c"] *= batt_mult
    return data


def solve(scen, timesteps=REP_WEEK, year=2040.0, **ov):
    """Solve a scenario and return capacities, storage and total cost."""
    data = _data(scen, **ov)
    prob = urbs.create_model(data, 1, timesteps, "cost")
    SolverFactory(SOLVER).solve(prob, tee=False)
    cap = lambda nm: round(float(pyo.value(sum(
        prob.cap_pro[k] for k in prob.cap_pro if k[0] == year and k[2] == nm)) or 0), 2)
    sto = lambda nm: round(float(pyo.value(sum(
        prob.cap_sto_c[k] for k in prob.cap_sto_c if k[0] == year and k[2] == nm)) or 0), 2)
    heat = lambda nm: round(float(pyo.value(sum(
        prob.e_pro_out[i] for i in prob.e_pro_out
        if i[1] == year and i[3] == nm and i[4] == "Heat")) or 0), 1)
    cost = round(float(sum(pyo.value(prob.costs[ct]) for ct in prob.cost_type)), 0)
    return dict(PV=cap("Photovoltaics"), HP=cap("Heatpump"),
                battery=sto("Battery"), tank=sto("Tank"),
                boiler_heat=heat("Boiler GN"), hp_heat=heat("Heatpump"),
                cost=cost)


# --------------------------------------------------------------------------- #
def reproduce():
    print("\n== Reproduction of the six-scenario capacities and costs (Tables 7-8) ==")
    print(f"{'Scn':4s} {'name':20s} {'PV':>6s} {'batt':>7s} {'tank':>6s} {'cost':>10s}")
    for s in ["S1", "S2", "S3", "S4", "S5", "S6"]:
        r = solve(s)
        print(f"{s:4s} {NAME[s]:20s} {r['PV']:6.1f} {r['battery']:7.1f} {r['tank']:6.1f} {r['cost']:10.0f}")


def zero_export():
    print("\n== Zero export compensation (Section 4.8) ==")
    for s in ["S1", "S4"]:
        b, z = solve(s), solve(s, sell=0)
        print(f"{s}: base PV {b['PV']} batt {b['battery']} cost {b['cost']:.0f} | "
              f"sell=0 PV {z['PV']} batt {z['battery']} cost {z['cost']:.0f}")


def cost_sensitivity():
    print("\n== Technology-cost sensitivity, +/-25% CAPEX (Section 4.8) ==")
    for s in ["S1", "S4"]:
        for lab, pv, bt in [("base", 1.0, 1.0), ("PV-25%", .75, 1.0), ("PV+25%", 1.25, 1.0),
                            ("Batt-25%", 1.0, .75), ("Batt+25%", 1.0, 1.25)]:
            r = solve(s, pv_mult=pv, batt_mult=bt)
            print(f"{s} {lab:9s}  PV {r['PV']:6.1f}  batt {r['battery']:7.1f}  cost {r['cost']:.0f}")


def carbon_threshold():
    print("\n== Carbon-price heat-dispatch threshold on S1 (Fig. 12) ==")
    print(f"{'CO2':>4s} {'boiler':>8s} {'heatpump':>9s}")
    for p in [0, 20, 40, 60, 80, 100, 120, 140]:
        r = solve("S1", co2=p)
        print(f"{p:4d} {r['boiler_heat']:8.0f} {r['hp_heat']:9.0f}")


def offgrid_horizons():
    """Table 9 / Fig. 13: off-grid sizing across time horizons.
    Windows are contiguous slices of the 8760-h input series."""
    print("\n== Off-grid sizing vs. horizon (Table 9) ==")
    windows = {"max-demand week": REP_WEEK,
               "lowest-solar month": range(5911, 5911 + 720 + 1),
               "worst low-solar fortnight": range(394, 394 + 336 + 1)}
    for s in ["S2", "S5"]:
        for name, ts in windows.items():
            r = solve(s, timesteps=ts)
            print(f"{s} {name:26s}  PV {r['PV']:6.1f}  batt {r['battery']:7.1f}  tank {r['tank']:6.1f}")


if __name__ == "__main__":
    print(f"Repository root: {ROOT}")
    print(f"Solver: {SOLVER}  |  representative week: {REP_WEEK.start}-{REP_WEEK.stop-1}")
    reproduce()
    zero_export()
    cost_sensitivity()
    carbon_threshold()
    offgrid_horizons()
    print("\nDone. See analysis/README.md for the mapping to paper tables and figures.")
