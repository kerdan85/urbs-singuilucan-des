#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Full-year (8,760-hour) chronological operational simulation of each scenario's
2040 least-cost design (Section 4.7 of the paper: Table 10 and Figure 14).

For every scenario this script:
  1. solves the representative-week model to obtain the 2040 design capacities;
  2. fixes those capacities and simulates the hourly dispatch of the full TMY
     year, month by month, with the real solar resource and demand;
  3. reports annual self-sufficiency, self-consumption, grid import/export,
     off-grid loss-of-load, curtailment and battery cycles.

Run from anywhere:
    python analysis/full_year_operation.py

Requirements: see analysis/requirements.txt (pyomo, highspy, pandas, numpy, openpyxl).
Solver: open-source HiGHS via Pyomo's appsi_highs.

Method notes
------------
* A single chronological 8,760-hour *co-optimisation* of the mixed demand-supply
  model is computationally prohibitive, so capacities are first sized on the four
  seasonal representative weeks (via design_caps, which imports the medoid-week
  selection from reproduce_analyses) and then fixed, with only the dispatch
  simulated over the full chronological year.
* The dispatch is solved month by month (storage cyclic within each month).
  Consequently the off-grid loss-of-load is a *conservative upper bound*: the
  hydrogen store is not carried across month boundaries.
* Four auxiliary balancing processes are added so the operation is always
  well-posed and the shortfalls/surpluses are measured explicitly:
    - HeatDump / ElecDump : reject surplus heat / curtail surplus electricity
      (real solar-thermal and off-grid PV systems can shed surplus);
    - ElecSlack / HeatSlack : last-resort unmet-load meters (very high penalty,
      so the grid is always preferred where available).
  The co-producing "Slack powerplant" is disabled so electricity and heat
  shortfalls are measured independently.
* Solar-thermal is treated as curtailable (its must-run heat output would
  otherwise overproduce in summer, where there is no heat demand to absorb it);
  this does not affect the electricity indicators.
"""
import os, sys, glob, shutil, tempfile, warnings, types, json
from datetime import date
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

if not hasattr(pd.core, "index"):                       # pandas>=2 shim for urbs 1.0.x
    pd.core.index = types.SimpleNamespace(MultiIndex=pd.MultiIndex)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FOLD = {"S1": "BAU/urbs-1.0.1-BAU",            "S2": "BAU/urbs-1.0.1-BAU-Aislado",
        "S3": "BAU/urbs-1.0.1-BAU-CO2-medio",  "S4": "Proposed/urbs-1.0.1-Proposed",
        "S5": "Proposed/urbs-1.0.1-Proposed-Aislado", "S6": "Proposed/urbs-1.0.1-Proposed-CO2medio"}
NAME = {"S1": "Reference, grid", "S2": "Reference, off-grid", "S3": "Reference, carbon",
        "S4": "Proposed, grid", "S5": "Proposed, off-grid", "S6": "Proposed, carbon"}

sys.path.insert(0, os.path.join(ROOT, FOLD["S1"]))
import urbs
import pyomo.environ as pyo
from pyomo.opt.base import SolverFactory

SOLVER = "appsi_highs"
YEAR = 2040
# four-season sizing basis, imported from the companion reproduction script
sys.path.insert(0, HERE)
from reproduce_analyses import select_seasonal_weeks as _season_weeks, _reindex as _season_reindex
_SEASON = None
# calendar-month hour boundaries over 8760 h (non-leap year)
_MD = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
BND = [0]
for _d in _MD:
    BND.append(BND[-1] + _d * 24)
GRID = {"Purchase", "Feed-in", "Slack powerplant"}


# --------------------------------------------------------------------------- #
def design_caps(scen):
    """Four-season least-cost design capacities at 2040."""
    global _SEASON
    if _SEASON is None:
        _SEASON = _season_weeks()
    os.chdir(os.path.join(ROOT, FOLD[scen]))
    data = urbs.scenario_base(urbs.read_input("Input", date.today().year))
    data, ts = _season_reindex(data, _SEASON)
    prob = urbs.create_model(data, 1, ts, "cost")
    SolverFactory(SOLVER).solve(prob, tee=False)
    y = float(YEAR)
    pro = {k[2]: float(pyo.value(prob.cap_pro[k])) for k in prob.cap_pro if k[0] == y}
    stoc = {k[2]: float(pyo.value(prob.cap_sto_c[k])) for k in prob.cap_sto_c if k[0] == y}
    stop = {k[2]: float(pyo.value(prob.cap_sto_p[k])) for k in prob.cap_sto_p if k[0] == y}
    return pro, stoc, stop


def _add_proc(data, name, cin, cout, new_com, new_type, new_price, stf, sit="Site1"):
    """Add a 1:1 auxiliary process (cin -> cout), registering only the *new* commodity.

    Dumps:  new commodity is the Env output (cout).   Slacks: new commodity is the Stock input (cin).
    """
    C = data["commodity"]
    C.loc[(stf, sit, new_com, new_type), ["price", "max", "maxperhour"]] = [new_price, float("inf"), float("inf")]
    P = data["process"]
    for c in P.columns:
        P.loc[(stf, sit, name), c] = 0.0
    P.loc[(stf, sit, name), ["inst-cap", "cap-up", "cap-lo", "lifetime", "max-grad",
                             "min-fraction", "wacc", "depreciation", "area-per-cap"]] = \
        [1000.0, 1000.0, 0.0, 20.0, float("inf"), 0.0, 0.07, 20.0, float("nan")]
    PC = data["process_commodity"]
    PC.loc[(stf, name, cin, "In"), ["ratio", "ratio-min"]] = [1.0, float("nan")]
    PC.loc[(stf, name, cout, "Out"), ["ratio", "ratio-min"]] = [1.0, float("nan")]


def _prepare(scen, caps):
    """Single-year 2040 model with fixed design + auxiliary balancing processes."""
    pro, stoc, stop = caps
    src = os.path.join(ROOT, FOLD[scen], "Input", f"{YEAR}.xlsx")
    td = tempfile.mkdtemp(prefix=f"fy_{scen}_")
    os.makedirs(os.path.join(td, "Input"))
    shutil.copy(src, os.path.join(td, "Input", f"{YEAR}.xlsx"))
    os.chdir(td)
    data = urbs.scenario_base(urbs.read_input("Input", YEAR))
    data["process"]["inst-cap"] = 0.0
    data["storage"]["inst-cap-c"] = 0.0
    data["storage"]["inst-cap-p"] = 0.0
    stf = float(YEAR)
    P, S = data["process"], data["storage"]
    for i in P.index:
        nm = i[2]
        if nm == "Slack powerplant":
            P.loc[i, ["inst-cap", "cap-up", "cap-lo"]] = [0.0, 0.0, 0.0]        # disable co-producing slack
        elif nm in GRID:
            continue                                                            # leave grid import/export as defined
        elif nm == "Solarthermal":
            P.loc[i, ["inst-cap", "cap-up", "cap-lo"]] = [0.0, max(pro.get(nm, 0.0), 0.0), 0.0]  # curtailable
        else:
            c = max(pro.get(nm, 0.0), 0.0)
            P.loc[i, ["inst-cap", "cap-up", "cap-lo"]] = [c, c, 0.0]
    for i in S.index:
        nm = i[2]; ec = max(stoc.get(nm, 0.0), 0.0); pc = max(stop.get(nm, 0.0), 0.0)
        S.loc[i, ["inst-cap-c", "cap-up-c", "cap-lo-c"]] = [ec, ec, 0.0]
        S.loc[i, ["inst-cap-p", "cap-up-p", "cap-lo-p"]] = [pc, pc, 0.0]
    # dumps: register the Env output; slacks: register the high-penalty Stock input
    _add_proc(data, "HeatDump",  "Heat",        "ElWasteH",    "ElWasteH", "Env",   0.0,    stf)
    _add_proc(data, "ElecDump",  "Electricity", "ElWasteE",    "ElWasteE", "Env",   0.0,    stf)
    _add_proc(data, "ElecSlack", "UnmetE",      "Electricity", "UnmetE",   "Stock", 9999.0, stf)
    _add_proc(data, "HeatSlack", "UnmetH",      "Heat",        "UnmetH",   "Stock", 9999.0, stf)
    return data


def run_scenario(scen):
    caps = design_caps(scen)
    data = _prepare(scen, caps)
    stf, sit = float(YEAR), "Site1"
    keys = ["dem", "pv", "buy", "sell", "fc", "elyz", "bchg", "bdis", "unmet", "curt"]
    tot = {k: 0.0 for k in keys}
    monthly = {k: [] for k in keys}
    for mi in range(12):
        a, b = BND[mi], BND[mi + 1]
        prob = urbs.create_model(data, 1, range(a, b + 1), "cost")
        SolverFactory(SOLVER).solve(prob, tee=False)
        ts = list(range(a + 1, b + 1))

        def po(pro, com):
            return np.array([float(pyo.value(prob.e_pro_out[(t, stf, sit, pro, com)]))
                             if (t, stf, sit, pro, com) in prob.e_pro_out else 0.0 for t in ts])

        def pin(pro, com):
            return np.array([float(pyo.value(prob.e_pro_in[(t, stf, sit, pro, com)]))
                             if (t, stf, sit, pro, com) in prob.e_pro_in else 0.0 for t in ts])

        def so(sto, com):
            return np.array([float(pyo.value(prob.e_sto_out[(t, stf, sit, sto, com)]))
                             if (t, stf, sit, sto, com) in prob.e_sto_out else 0.0 for t in ts])

        def si(sto, com):
            return np.array([float(pyo.value(prob.e_sto_in[(t, stf, sit, sto, com)]))
                             if (t, stf, sit, sto, com) in prob.e_sto_in else 0.0 for t in ts])

        vals = dict(dem=np.array([float(data["demand"].loc[(stf, t), (sit, "Electricity")]) for t in ts]),
                    pv=po("Photovoltaics", "Electricity"), buy=po("Purchase", "Electricity"),
                    sell=pin("Feed-in", "Electricity"), fc=po("Hydrogen FC", "Electricity"),
                    elyz=pin("Electrolizer", "Electricity"), bchg=si("Battery", "Electricity"),
                    bdis=so("Battery", "Electricity"), unmet=po("ElecSlack", "Electricity"),
                    curt=pin("ElecDump", "Electricity"))
        for k in keys:
            s = float(vals[k].sum()); monthly[k].append(s); tot[k] += s
    ss = 100 * (tot["dem"] - tot["buy"] - tot["unmet"]) / tot["dem"]
    sc = 100 * (tot["pv"] - tot["sell"] - tot["curt"]) / tot["pv"] if tot["pv"] > 0 else 0.0
    cycles = tot["bdis"] / max(caps[1].get("Battery", 1e-9), 1e-9)
    offgrid = tot["buy"] < 1.0
    return dict(scen=scen, name=NAME[scen], self_sufficiency=round(ss, 1), self_consumption=round(sc, 1),
                import_MWh=round(tot["buy"] / 1000, 1), export_MWh=round(tot["sell"] / 1000, 1),
                loss_of_load_pct=round(100 * tot["unmet"] / tot["dem"], 1) if offgrid else 0.0,
                curtailment_pct=round(100 * tot["curt"] / (tot["pv"] + 1e-9), 1),
                batt_cycles=round(cycles), offgrid=offgrid,
                monthly={k: [round(x / 1000, 3) for x in monthly[k]] for k in keys})


def main():
    print(f"Repository root: {ROOT}\nSolver: {SOLVER}\n")
    hdr = f"{'Scenario':22s}{'SelfSuff%':>10s}{'SelfCons%':>10s}{'Imp MWh':>9s}{'Exp MWh':>9s}{'LoL%':>7s}{'cyc/yr':>8s}"
    print(hdr); print("-" * len(hdr))
    out = {}
    for s in ["S1", "S4", "S3", "S6", "S2", "S5"]:
        r = run_scenario(s); out[s] = r
        lol = f"{r['loss_of_load_pct']}" if r["offgrid"] else "--"
        imp = "--" if r["offgrid"] else f"{r['import_MWh']}"
        exp = "--" if r["offgrid"] else f"{r['export_MWh']}"
        print(f"{r['name']:22s}{r['self_sufficiency']:>10}{r['self_consumption']:>10}{imp:>9}{exp:>9}{lol:>7}{r['batt_cycles']:>8}")
    with open(os.path.join(HERE, "full_year_operation_results.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("\nSaved monthly series to analysis/full_year_operation_results.json")
    print("(Table 10 = annual columns above; Figure 14 = annual bars + monthly loss-of-load.)")


if __name__ == "__main__":
    main()
