#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Off-grid full-year reliability metrics introduced in the second revision (MC1, Section 4.7).

Extends full_year_operation.py: fixes each off-grid scenario's 2040 design and
simulates its hourly dispatch month by month over the full 8,760-hour TMY
(cyclic storage per month, no inter-month hydrogen carry-over -- the conservative
reading of the representative-week sizing). Reports, per scenario:
    annual demand, energy not served (MWh and % of demand),
    number of loss-of-load events, and the longest consecutive outage.

Run from the repository root:
    python analysis/reliability_metrics.py            # S2 and S5 (the off-grid designs)
    python analysis/reliability_metrics.py S2
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import full_year_operation as F
import urbs, pyomo.environ as pyo
from pyomo.opt.base import SolverFactory

def hourly_unmet(scen):
    caps = F.design_caps(scen); data = F._prepare(scen, caps)
    stf, sit = float(F.YEAR), "Site1"; dem = []; unmet = []
    for mi in range(12):
        a, b = F.BND[mi], F.BND[mi+1]
        prob = urbs.create_model(data, 1, range(a, b+1), "cost")
        SolverFactory(F.SOLVER).solve(prob, tee=False)
        for t in range(a+1, b+1):
            dem.append(float(data["demand"].loc[(stf, t), (sit, "Electricity")]))
            key = (t, stf, sit, "ElecSlack", "Electricity")
            unmet.append(float(pyo.value(prob.e_pro_out[key])) if key in prob.e_pro_out else 0.0)
    return dem, unmet

def metrics(scen, tol=1e-3):
    dem, unmet = hourly_unmet(scen)
    D = sum(dem); U = sum(unmet)
    runs = []; c = 0
    for u in unmet:
        if u > tol: c += 1
        elif c > 0: runs.append(c); c = 0
    if c > 0: runs.append(c)
    print(f"=== {scen} ===")
    print(f"  annual demand          = {D/1000:.2f} MWh")
    print(f"  energy not served      = {U/1000:.3f} MWh  ({100*U/D:.2f}% of demand; self-sufficiency {100-100*U/D:.1f}%)")
    print(f"  loss-of-load events    = {len(runs)}")
    print(f"  longest outage (hours) = {max(runs) if runs else 0}")

if __name__ == "__main__":
    scens = sys.argv[1:] or ["S2", "S5"]
    for s in scens:
        metrics(s)
