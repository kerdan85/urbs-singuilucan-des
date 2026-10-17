#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reproduce the main six-scenario results and the sensitivity/robustness analyses
of the paper, on the four-season representative-period basis used throughout.

Run from anywhere:
    python analysis/reproduce_analyses.py

Requirements (see analysis/requirements.txt): pyomo, highspy, pandas, numpy, openpyxl.
Solver: open-source HiGHS via Pyomo's appsi_highs (no commercial solver needed).

Temporal basis
--------------
Each planning year is represented by FOUR seasonal characteristic weeks (one per
meteorological season), each a contiguous 120-hour window selected systematically
as the *medoid* week of its season: the window whose mean electricity demand and
mean solar resource most closely match the season's own means (minimum normalised
distance). The four weeks are concatenated (480 h/year) and solved with cyclic
storage per week; urbs rescales costs/energy to annual operation by the weight
w = 8760 / 480 ~= 18.3. The medoid selection is computed here from the reference
building's demand and solar, so the four week-start hours are reproduced, not
hard-coded (they come out as roughly early-Feb, late-Mar, early-Aug, late-Nov).

Notes
-----
* The bundled urbs source (v1.0.x) is imported with a one-line pandas>=2 shim.
* Long-duration hydrogen storage is the one quantity sensitive to any
  non-chronological representative scheme; offgrid_bounds() brackets it between
  the single maximum-demand week and the worst contiguous low-solar fortnight.
"""
import os, sys, glob, warnings, types
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
NAME = {"S1": "Reference | grid", "S2": "Reference | off-grid", "S3": "Reference | carbon",
        "S4": "Proposed  | grid", "S5": "Proposed  | off-grid", "S6": "Proposed  | carbon"}

sys.path.insert(0, os.path.join(ROOT, FOLD["S1"]))
import urbs
import pyomo.environ as pyo
from pyomo.opt.base import SolverFactory

SOLVER = "appsi_highs"
LEN = 120                               # hours per representative week
YEAR = float(date.today().year)         # urbs stamps read_input with the current year as base
# bounding windows for the off-grid hydrogen store (contiguous slices of the 8760-h series)
MAXWK = 2329                            # maximum-demand week start (early April)
FORTNIGHT = range(394, 394 + 336 + 1)   # worst consecutive low-solar fortnight


# --------------------------------------------------------------------------- #
def select_seasonal_weeks():
    """Medoid 120-h week per meteorological season, from the reference demand+solar."""
    os.chdir(os.path.join(ROOT, FOLD["S1"]))
    d = urbs.read_input("Input", date.today().year)
    stf0 = sorted(set(d["demand"].index.get_level_values(0)))[0]
    dem = d["demand"].xs(stf0, level=0)[("Site1", "Electricity")]
    sol = d["supim"].xs(stf0, level=0).iloc[:, 0]
    demv = dem.loc[list(range(1, 8761))].values
    solv = sol.loc[list(range(1, 8761))].values
    md = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    cum = np.cumsum([0] + md) * 24
    mh = lambda a, b: list(range(cum[a] + 1, cum[b + 1] + 1))
    seasons = {"winter": mh(11, 11) + mh(0, 1), "spring": mh(2, 4),
               "summer": mh(5, 7), "autumn": mh(8, 10)}
    starts = []
    for hrs in seasons.values():
        sd = np.mean([demv[h - 1] for h in hrs]); ss = np.mean([solv[h - 1] for h in hrs])
        hs = set(hrs); best = None
        for st in range(min(hrs), max(hrs) - LEN + 2, 24):
            win = range(st, st + LEN)
            if not all(h in hs for h in win):
                continue
            wd = np.mean([demv[h - 1] for h in win]); ws = np.mean([solv[h - 1] for h in win])
            dist = ((wd - sd) / sd) ** 2 + ((ws - ss) / ss) ** 2
            if best is None or dist < best[0]:
                best = (dist, st)
        starts.append(best[1])
    return sorted(starts)


def _reindex(data, starts):
    """Concatenate the representative weeks into contiguous timesteps for every year."""
    hours = []
    for ws in starts:
        hours += list(range(ws, ws + LEN))
    n = len(hours)
    for key in ["demand", "supim", "buy_sell_price", "eff_factor"]:
        df = data[key]; parts = []
        for stf in sorted(set(df.index.get_level_values(0))):
            sub = df.xs(stf, level=0).loc[hours].copy()
            sub.index = pd.MultiIndex.from_arrays([[stf] * n, list(range(1, n + 1))], names=df.index.names)
            parts.append(sub)
        data[key] = pd.concat(parts)
    return data, range(0, n + 1)


def _load(scen, sell=None, pv_mult=1.0, batt_mult=1.0):
    os.chdir(os.path.join(ROOT, FOLD[scen]))
    data = urbs.scenario_base(urbs.read_input("Input", date.today().year))
    if sell is not None:
        for c in data["buy_sell_price"].columns:
            if "sell" in str(c).lower():
                data["buy_sell_price"][c] = sell
    if pv_mult != 1.0:
        for i in data["process"].index:
            if i[2] == "Photovoltaics":
                data["process"].loc[i, "inv-cost"] *= pv_mult
    if batt_mult != 1.0:
        for i in data["storage"].index:
            if i[2] == "Battery":
                data["storage"].loc[i, "inv-cost-c"] *= batt_mult
    return data


def solve(scen, starts, **ov):
    """Solve a scenario on the given representative-week starts; return 2040 sizing + cost."""
    data = _load(scen, **ov)
    data, ts = _reindex(data, starts)
    prob = urbs.create_model(data, 1, ts, "cost")
    SolverFactory(SOLVER).solve(prob, tee=False)
    y = 2040.0; v = lambda x: float(pyo.value(x))
    cap = lambda nm: round(sum(v(prob.cap_pro[k]) for k in prob.cap_pro if k[0] == y and k[2] == nm), 2)
    sto = lambda nm: round(sum(v(prob.cap_sto_c[k]) for k in prob.cap_sto_c if k[0] == y and k[2] == nm), 2)
    cost = round(sum(v(prob.costs[ct]) for ct in prob.cost_type), 0)
    return dict(PV=cap("Photovoltaics"), battery=sto("Battery"), tank=sto("Tank"),
                FC=cap("Hydrogen FC"), cost=cost)


def solve_window(scen, timesteps):
    """Solve a scenario over a single contiguous window (for the off-grid hydrogen bounds)."""
    data = _load(scen)
    prob = urbs.create_model(data, 1, timesteps, "cost")
    SolverFactory(SOLVER).solve(prob, tee=False)
    y = 2040.0; v = lambda x: float(pyo.value(x))
    return round(sum(v(prob.cap_sto_c[k]) for k in prob.cap_sto_c if k[0] == y and k[2] == "Tank"), 1)


# --------------------------------------------------------------------------- #
def reproduce(starts):
    print("\n== Six-scenario capacities and costs on the four-season basis (Tables 7-8) ==")
    print(f"{'Scn':4s} {'name':22s} {'PV':>6s} {'batt':>7s} {'tank':>7s} {'cost':>10s}")
    for s in ["S1", "S2", "S3", "S4", "S5", "S6"]:
        r = solve(s, starts)
        print(f"{s:4s} {NAME[s]:22s} {r['PV']:6.1f} {r['battery']:7.1f} {r['tank']:7.1f} {r['cost']:10.0f}")


def zero_export(starts):
    print("\n== Zero export compensation, grid cases (Section 4.6) ==")
    for s in ["S1", "S4"]:
        b, z = solve(s, starts), solve(s, starts, sell=0)
        print(f"{s}: base PV {b['PV']} batt {b['battery']} cost {b['cost']:.0f} | "
              f"sell=0 PV {z['PV']} batt {z['battery']} cost {z['cost']:.0f}")


def attribution(starts):
    """Envelope vs. LED supply-side attribution on the four-season basis (Tables 5-6).

    The two intermediate configurations requested by the reviewers were simulated
    independently in IES VE:
      * envelope-only : improved envelope, conventional (BAU) lighting
      * lighting-only : conventional (BAU) envelope, reduced (LED) lighting
    Their hourly electricity demand (reproducing the IES VE outputs, including the
    space-heating rebound of the lighting-only case) is read from
    analysis/intermediate_demand.csv and optimised on the same four-season basis as
    the grid-connected reference (S1). The envelope-only hourly series is normalised to
    its IES VE end-use annual total (54.6 MWh) so that it is consistent with the end-use
    breakdown reported in Table 5; the other configurations are used as exported. The envelope delivers most of the cost
    reduction; the LED upgrade achieves little on its own because cutting lighting
    removes internal heat gains and raises space heating; the two combine
    super-additively.
    """
    prof = os.path.join(HERE, "intermediate_demand.csv")
    rows = [ln.split(",") for ln in open(prof).read().splitlines()[1:]]
    env = [float(r[1]) for r in rows]          # envelope-only hourly kW (t = 1..8760)
    lig = [float(r[2]) for r in rows]          # lighting-only hourly kW

    def solve_profile(elec):
        data = _load("S1")
        dem = data["demand"]; col = ("Site1", "Electricity")
        for stf in sorted(set(dem.index.get_level_values(0))):
            for t in range(1, 8761):
                dem.loc[(stf, t), col] = elec[t - 1]
        data, ts = _reindex(data, starts)
        prob = urbs.create_model(data, 1, ts, "cost")
        SolverFactory(SOLVER).solve(prob, tee=False)
        y = 2040.0; v = lambda x: float(pyo.value(x))
        pv = sum(v(prob.cap_pro[k]) for k in prob.cap_pro if k[0] == y and k[2] == "Photovoltaics")
        bt = sum(v(prob.cap_sto_c[k]) for k in prob.cap_sto_c if k[0] == y and k[2] == "Battery")
        cost = sum(v(prob.costs[ct]) for ct in prob.cost_type)
        return round(pv, 1), round(bt, 1), round(cost, 0)

    print("\n== Envelope vs. LED supply-side attribution, four-season basis (Table 6) ==")
    print(f"{'Configuration':36s} {'PV':>6s} {'batt':>7s} {'cost':>9s}")
    ref = solve("S1", starts); prop = solve("S4", starts)
    eo = solve_profile(env); lo = solve_profile(lig)
    print(f"{'Reference (conv env + conv light)':36s} {ref['PV']:6.1f} {ref['battery']:7.1f} {ref['cost']:9.0f}")
    print(f"{'Envelope-only (passive env + conv L)':36s} {eo[0]:6.1f} {eo[1]:7.1f} {eo[2]:9.0f}")
    print(f"{'Lighting-only (conv env + LED)':36s} {lo[0]:6.1f} {lo[1]:7.1f} {lo[2]:9.0f}")
    print(f"{'Proposed (passive env + LED)':36s} {prop['PV']:6.1f} {prop['battery']:7.1f} {prop['cost']:9.0f}")


def cost_sensitivity(starts):
    print("\n== Technology-cost sensitivity, +/-25% CAPEX, grid cases (Fig. B.1) ==")
    for s in ["S1", "S4"]:
        for lab, pv, bt in [("base", 1.0, 1.0), ("PV-25%", .75, 1.0), ("PV+25%", 1.25, 1.0),
                            ("Batt-25%", 1.0, .75), ("Batt+25%", 1.0, 1.25)]:
            r = solve(s, starts, pv_mult=pv, batt_mult=bt)
            print(f"{s} {lab:9s}  PV {r['PV']:6.1f}  batt {r['battery']:7.1f}  cost {r['cost']:.0f}")


def offgrid_bounds(starts):
    """Hydrogen-tank bounds for the off-grid scenarios (Table 9, Fig. 13)."""
    print("\n== Off-grid hydrogen store across temporal bases (Table 9) ==")
    print(f"{'Scn':12s} {'seasonal':>9s} {'max-week':>9s} {'fortnight':>10s}")
    for s in ["S2", "S5"]:
        seas = solve(s, starts)["tank"]
        wk = solve_window(s, range(MAXWK, MAXWK + LEN + 1))
        fn = solve_window(s, FORTNIGHT)
        print(f"{s:12s} {seas:9.1f} {wk:9.1f} {fn:10.1f}")


if __name__ == "__main__":
    print(f"Repository root: {ROOT}\nSolver: {SOLVER}")
    starts = select_seasonal_weeks()
    print(f"Four seasonal medoid weeks start at hours: {starts}  (w = 8760/480 = {8760/480:.1f})")
    reproduce(starts)
    attribution(starts)
    zero_export(starts)
    cost_sensitivity(starts)
    offgrid_bounds(starts)
    print("\nSee analysis/README.md for the mapping to paper tables and figures.")
