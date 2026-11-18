#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Additional sensitivity / robustness analyses introduced in the second revision.

Run from the repository root (same requirements as reproduce_analyses.py):
    python analysis/extra_sensitivities.py            # runs all four analyses
    python analysis/extra_sensitivities.py battery    # one of: battery land demand variants carbon

These reuse the four-season representative-period harness of reproduce_analyses.py
(open-source HiGHS solver, pandas>=2 shim), so no commercial solver is needed.

Mapping to the paper (Section 4.6 unless noted):
  * battery  -> MC4: battery energy+power sizing and a 150 USD/kW power-conversion
               (inverter/PCS) cost. Reproduces the Table 7 caption figures.
  * land     -> MC8: land-availability sensitivity (installation area 400/200/150/100 m^2).
  * demand   -> MC6: aggregate +/-15% scaling of the building electricity demand.
  * variants -> MC6: six physics-based IES VE building-model variants per building
               (HVAC COP +/-15%, internal gains +/-20%, infiltration +/-30%),
               read from analysis/iesve_demand_variants.csv.
  * carbon   -> MC9: continuous carbon-price sweep on the grid-connected reference,
               locating the boiler->heat-pump transition (Fig. 12).
"""
import os, sys, csv, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reproduce_analyses as R          # harness: _load, _reindex, select_seasonal_weeks, solve, SOLVER, urbs
import pyomo.environ as pyo
from pyomo.opt.base import SolverFactory

urbs = R.urbs
V = lambda x: float(pyo.value(x))
Y = 2040.0
def _cap(prob, nm):  return round(sum(V(prob.cap_pro[k])   for k in prob.cap_pro   if k[0]==Y and k[2]==nm), 2)
def _stoc(prob, nm): return round(sum(V(prob.cap_sto_c[k]) for k in prob.cap_sto_c if k[0]==Y and k[2]==nm), 2)
def _stop(prob, nm): return round(sum(V(prob.cap_sto_p[k]) for k in prob.cap_sto_p if k[0]==Y and k[2]==nm), 2)
def _cost(prob):     return round(sum(V(prob.costs[c]) for c in prob.cost_type), 0)
def _build(data, starts):
    data, ts = R._reindex(data, starts)
    prob = urbs.create_model(data, 1, ts, "cost")
    SolverFactory(R.SOLVER).solve(prob, tee=False)
    return prob


# ----------------------------------------------------------------- MC4
def battery_power(starts):
    print("\n== MC4: battery energy/power and a 150 USD/kW power-conversion cost (Table 7 caption) ==")
    for scen in ["S1", "S4"]:
        for pcap in [0, 150]:
            data = R._load(scen)
            for i in data["storage"].index:
                if i[2] == "Battery":
                    data["storage"].loc[i, "inv-cost-p"] = pcap     # USD/kW (inverter/PCS)
            prob = _build(data, starts)
            be, bp = _stoc(prob, "Battery"), _stop(prob, "Battery")
            print(f"  {scen}  PCS={pcap:3d} USD/kW:  battery {be:6.1f} kWh / {bp:5.2f} kW "
                  f"(C-rate {bp/be:.2f})  PV {_cap(prob,'Photovoltaics'):5.1f}  cost {_cost(prob):.0f}")


# ----------------------------------------------------------------- MC8
def land_area(starts):
    print("\n== MC8: land-availability sensitivity (installation area) ==")
    for scen in ["S1", "S3"]:
        print(f"  {scen}:")
        for area in [400, 200, 150, 100]:
            data = R._load(scen)
            for i in data["site"].index:
                data["site"].loc[i, "area"] = area
            res = SolverFactory(R.SOLVER)
            data2, ts = R._reindex(data, starts)
            prob = urbs.create_model(data2, 1, ts, "cost")
            out = res.solve(prob, tee=False)
            if str(out.solver.termination_condition) != "optimal":
                print(f"    {area:3d} m^2: infeasible"); continue
            pv = _cap(prob, "Photovoltaics")
            print(f"    {area:3d} m^2: PV {pv:5.1f} kWp ({round(pv*5.15)} m^2)  "
                  f"battery {_stoc(prob,'Battery'):6.1f}  cost {_cost(prob):.0f}")


# ----------------------------------------------------------------- MC6 (aggregate)
def demand_scaling(starts):
    print("\n== MC6: aggregate +/-15% building-demand scaling ==")
    for scale in [0.85, 1.0, 1.15]:
        r = {}
        for scen in ["S1", "S4"]:
            data = R._load(scen); col = ("Site1", "Electricity")
            for idx in data["demand"].index:
                data["demand"].loc[idx, col] *= scale
            prob = _build(data, starts)
            r[scen] = (_cap(prob, "Photovoltaics"), _stoc(prob, "Battery"), _cost(prob))
        adv = 100*(1 - r["S4"][2]/r["S1"][2])
        print(f"  x{scale:.2f}:  S1 PV {r['S1'][0]:.1f} batt {r['S1'][1]:.1f} cost {r['S1'][2]:.0f} | "
              f"S4 PV {r['S4'][0]:.1f} batt {r['S4'][1]:.1f} cost {r['S4'][2]:.0f} | passive advantage {adv:.1f}%")


# ----------------------------------------------------------------- MC6 (IES VE variants)
def demand_variants(starts):
    print("\n== MC6: six IES VE building-model variants per building (re-optimised) ==")
    path = os.path.join(HERE, "iesve_demand_variants.csv")
    rows = list(csv.DictReader(open(path)))[:8760]
    variants = ["base", "COP+15", "COP-15", "IG+20", "IG-20", "Infil+30", "Infil-30"]
    def run(colname):
        elec = [float(r[colname]) for r in rows]
        data = R._load("S1"); col = ("Site1", "Electricity")
        for stf in sorted(set(data["demand"].index.get_level_values(0))):
            for t in range(1, 8761):
                data["demand"].loc[(stf, t), col] = elec[t-1]
        prob = _build(data, starts)
        return _cap(prob, "Photovoltaics"), _stoc(prob, "Battery"), _cost(prob)
    print(f"  {'variant':12s} {'Ref cost':>9s} {'Prop cost':>10s} {'advantage':>10s}")
    for v in variants:
        b = run(f"BAU_{v}"); p = run(f"Prop_{v}")
        print(f"  {v:12s} {b[2]/1000:8.1f}k {p[2]/1000:9.1f}k {100*(1-p[2]/b[2]):9.1f}%")


# ----------------------------------------------------------------- MC9
def carbon_sweep(starts, prices=(0, 50, 90, 110, 120, 130, 140, 160, 200)):
    print("\n== MC9: continuous carbon-price sweep on the grid-connected reference (Fig. 12) ==")
    N = len(starts) * R.LEN; W = 8760.0/N
    print(f"  {'CO2 (USD/tCO2)':>15s} {'boiler heat':>12s} {'heat-pump heat':>14s}  (MWh/yr)")
    for co2 in prices:
        data = R._load("S1")
        for i in data["commodity"].index:
            if i[2] == "CO2" and i[3] == "Env":
                data["commodity"].loc[i, "price"] = co2
        prob = _build(data, starts)
        bo = W*sum(V(prob.e_pro_out[i]) for i in prob.e_pro_out if i[1]==Y and i[3]=="Boiler GN"  and i[4]=="Heat")/1000
        hp = W*sum(V(prob.e_pro_out[i]) for i in prob.e_pro_out if i[1]==Y and i[3]=="Heatpump"   and i[4]=="Heat")/1000
        print(f"  {co2:15d} {bo:12.2f} {hp:14.2f}")


if __name__ == "__main__":
    starts = R.select_seasonal_weeks()
    print(f"Four seasonal medoid weeks start at hours: {starts}")
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    funcs = {"battery": battery_power, "land": land_area, "demand": demand_scaling,
             "variants": demand_variants, "carbon": carbon_sweep}
    if which == "all":
        for f in [battery_power, land_area, demand_scaling, demand_variants, carbon_sweep]:
            f(starts)
    else:
        funcs[which](starts)
