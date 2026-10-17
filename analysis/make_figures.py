#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regenerate the main data-driven figures of the paper from a fresh four-season
solve of the six scenarios:

  * DER capacities by scenario          (paper Fig. 6)
  * System-cost composition by scenario (paper Fig. 7)
  * Season-shaded electricity dispatch  (paper Fig. 8)
  * Energy-system technology mix (2040)  (paper Fig. 9)
  * Inter-period evolution of S6        (paper Fig. 10)

Run from anywhere:
    python analysis/make_figures.py
Outputs are written to analysis/figures/.

Requirements: see analysis/requirements.txt (adds matplotlib).
Solver: open-source HiGHS via Pyomo's appsi_highs.

This script reuses the four-season medoid-week selection and the model setup from
reproduce_analyses.py (same temporal basis as the paper's main results), so it is
fully self-contained against the bundled urbs source.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reproduce_analyses as R          # four-season setup, urbs import, HiGHS, _load, _reindex, select_seasonal_weeks
import pyomo.environ as pyo
from pyomo.opt.base import SolverFactory

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

plt.rcParams.update({
    "figure.facecolor": "white", "savefig.facecolor": "white", "axes.facecolor": "white",
    "font.size": 9.5, "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.labelsize": 9.5,
    "axes.edgecolor": "#333333", "axes.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "axes.axisbelow": True, "legend.frameon": False, "figure.dpi": 300})
C = dict(PV="#E1A730", Batt="#3B6FB0", FC="#C0473F", Buy="#7E4A9B", CHP="#9467bd",
         Feed="#4E9A6B", Elyz="#8C6BB1", Dem="#1a1a1a", Boiler="#7B4A2E", Solar="#3FA46A",
         HP="#D3703A", Invest="#3B6FB0", Fixed="#9CC0E0", Carbon="#7f7f7f", Premium="#8C6BB1")
ORDER = ["S1", "S2", "S3", "S4", "S5", "S6"]
LAB = ["S1\nRef·Grid", "S2\nRef·Off", "S3\nRef·CO$_2$",
       "S4\nProp·Grid", "S5\nProp·Off", "S6\nProp·CO$_2$"]
OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)


# --------------------------------------------------------------------------- #
def solve_full(scen, starts):
    """Solve a scenario on the four seasons; return caps (per year), costs, annual flows, 480-h dispatch."""
    data = R._load(scen)
    data, ts = R._reindex(data, starts)
    N = len(list(ts)) - 1
    prob = R.urbs.create_model(data, 1, ts, "cost")
    SolverFactory(R.SOLVER).solve(prob, tee=False)
    v = lambda x: float(pyo.value(x)); y = 2040.0; S = "Site1"; W = 8760.0 / N
    years = sorted(set(k[0] for k in prob.cap_pro))
    caps = {int(yy): {k[2]: round(v(prob.cap_pro[k]), 3) for k in prob.cap_pro if k[0] == yy and v(prob.cap_pro[k]) > 1e-3} for yy in years}
    stoc = {int(yy): {k[2]: round(v(prob.cap_sto_c[k]), 3) for k in prob.cap_sto_c if k[0] == yy and v(prob.cap_sto_c[k]) > 1e-3} for yy in years}
    costs = {ct: round(v(prob.costs[ct]), 0) for ct in prob.cost_type}
    po = lambda p, c="Electricity": round(W * sum(v(prob.e_pro_out[i]) for i in prob.e_pro_out if i[1] == y and i[3] == p and i[4] == c) / 1000, 2)
    heat = {p: po(p, "Heat") for p in ["Boiler GN", "Boiler Elec", "Heatpump", "Solarthermal", "CHP"]}
    elec = {p: po(p) for p in ["Photovoltaics", "Hydrogen FC", "Purchase", "CHP"]}
    T = list(range(1, N + 1))
    ser = lambda comp, p, c="Electricity": np.array([v(comp[(t, y, S, p, c)]) if (t, y, S, p, c) in comp else 0.0 for t in T])
    disp = dict(pv=ser(prob.e_pro_out, "Photovoltaics"), fc=ser(prob.e_pro_out, "Hydrogen FC"),
                buy=ser(prob.e_pro_out, "Purchase"), chp=ser(prob.e_pro_out, "CHP"),
                bdis=ser(prob.e_sto_out, "Battery"), bchg=ser(prob.e_sto_in, "Battery"),
                sell=ser(prob.e_pro_in, "Feed-in"), elyz=ser(prob.e_pro_in, "Electrolizer"),
                dem=np.array([float(data["demand"].loc[(y, t), (S, "Electricity")]) for t in T]))
    return dict(caps=caps, stoc=stoc, costs=costs, heat=heat, elec=elec, disp=disp, N=N)


# --------------------------------------------------------------------------- #
def fig_capacity(D):
    xs = np.arange(6)
    PV = [D[s]["caps"][2040].get("Photovoltaics", 0) for s in ORDER]
    BAT = [D[s]["stoc"][2040].get("Battery", 0) for s in ORDER]
    TK = [D[s]["stoc"][2040].get("Tank", 0) for s in ORDER]
    HP = [D[s]["caps"][2040].get("Heatpump", 0) for s in ORDER]
    fig, ax = plt.subplots(figsize=(8.6, 4.6)); w = 0.2
    ax.bar(xs - 1.5 * w, PV, w, label="PV (kW$_p$)", color=C["PV"])
    ax.bar(xs - 0.5 * w, BAT, w, label="Battery (kWh)", color=C["Batt"])
    ax.bar(xs + 0.5 * w, TK, w, label="H$_2$ tank (kWh)", color=C["Feed"])
    ax.bar(xs + 1.5 * w, np.array(HP) * 10, w, label="Heat pump (kW $\\times$10)", color=C["FC"])
    ax.set_xticks(xs); ax.set_xticklabels(LAB); ax.set_ylabel("Installed capacity"); ax.set_ylim(0, 230)
    ax.axvline(2.5, color="#b0b0b0", ls="--", lw=1); ax.grid(axis="y", color="#d5d5d5", lw=0.6)
    ax.legend(ncol=4, fontsize=8.6, loc="upper center", bbox_to_anchor=(0.5, 1.14))
    fig.tight_layout(); fig.savefig(f"{OUT}/comp_capacity_scenarios.png", bbox_inches="tight", dpi=300); plt.close()


def fig_cost(D):
    xs = np.arange(6); g = lambda s, k: D[s]["costs"].get(k, 0)
    rows = [("Invest", C["Invest"], "Investment"), ("Fixed", C["Fixed"], "Fixed O&M"),
            ("Fuel", C["PV"], "Fuel"), ("Environmental", C["Carbon"], "Carbon"), ("Purchase", C["FC"], "Grid purchase")]
    Prem = [0, 0, 0, 50000, 50000, 50000]; Net = [sum(D[s]["costs"].values()) + p for s, p in zip(ORDER, Prem)]
    fig, ax = plt.subplots(figsize=(8.6, 5.0)); bot = np.zeros(6)
    for k, col, lab in rows:
        vv = np.array([g(s, k) for s in ORDER]); ax.bar(xs, vv, 0.6, bottom=bot, color=col, label=lab, edgecolor="white", lw=0.4); bot = bot + vv
    ax.bar(xs, Prem, 0.6, bottom=bot, color=C["Premium"], label="Envelope premium (est.)", edgecolor="white", lw=0.4)
    ax.bar(xs, [g(s, "Revenue") for s in ORDER], 0.6, color=C["Feed"], label="Grid revenue", edgecolor="white", lw=0.4)
    top = 235000; ax.set_ylim(-28000, top * 1.1)
    for xi, vv in zip(xs, Net):
        ax.hlines(vv, xi - 0.33, xi + 0.33, color="black", lw=2.4)
        ax.text(xi, vv + top * 0.02, f"{vv/1000:.0f}k", ha="center", va="bottom", fontsize=8.6, fontweight="bold")
    ax.set_xticks(xs); ax.set_xticklabels(LAB); ax.set_ylabel("System cost over horizon (USD)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1000:.0f}k")); ax.axvline(2.5, color="#b0b0b0", ls="--", lw=1)
    ax.grid(axis="y", color="#d5d5d5", lw=0.6); ax.plot([], [], color="black", lw=2.4, label="Net total")
    ax.legend(ncol=4, fontsize=8.3, loc="lower center", bbox_to_anchor=(0.5, -0.22))
    fig.tight_layout(); fig.savefig(f"{OUT}/comp_cost_scenarios.png", bbox_inches="tight", dpi=300); plt.close()


def fig_dispatch(D):
    titles = {"S1": "(a) S1 Reference, grid", "S2": "(b) S2 Reference, off-grid", "S3": "(c) S3 Reference, carbon",
              "S4": "(d) S4 Proposed, grid", "S5": "(e) S5 Proposed, off-grid", "S6": "(f) S6 Proposed, carbon"}
    SH = ["#EEF3FA", "#EFF6EF", "#FCF8ED", "#FAEFEE"]            # light winter/spring/summer/autumn tints
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 6.0), sharex=True); axes = axes.ravel()
    for ax, s in zip(axes, ORDER):
        d = D[s]["disp"]; x = np.arange(len(d["dem"]))
        for k in range(4):
            ax.axvspan(k * 120, (k + 1) * 120, color=SH[k], zorder=0, lw=0)
        base = np.zeros(len(x))
        for arr, col in [(d["pv"], C["PV"]), (d["bdis"], C["Batt"]), (d["fc"], C["FC"]), (d["chp"], C["CHP"]), (d["buy"], C["Buy"])]:
            ax.fill_between(x, base, base + arr, color=col, lw=0, zorder=2); base = base + arr
        nb = np.zeros(len(x))
        for arr, col in [(d["bchg"], C["Batt"]), (d["sell"], C["Feed"]), (d["elyz"], C["Elyz"])]:
            ax.fill_between(x, nb, nb - arr, color=col, alpha=0.5, lw=0, zorder=2); nb = nb - arr
        ax.plot(x, d["dem"], color=C["Dem"], lw=0.9, zorder=4); ax.axhline(0, color="#333", lw=0.5)
        for b in (120, 240, 360):
            ax.axvline(b, color="#c8c8c8", ls="--", lw=0.7)
        ax.set_title(titles[s], loc="left", fontsize=9); ax.set_xlim(0, 480); ax.set_ylim(-35, 70)
        ax.grid(axis="y", color="#ededed", lw=0.5); ax.set_xticks([60, 180, 300, 420]); ax.set_xticklabels(["W", "Sp", "Su", "A"], fontsize=8)
    for i in (0, 3):
        axes[i].set_ylabel("Power (kW)")
    for ax in axes[3:]:
        ax.set_xlabel("Season (W, Sp, Su, A)")
    leg = [Patch(fc=C["PV"], label="PV"), Patch(fc=C["Batt"], label="Battery (± charge)"), Patch(fc=C["FC"], label="Fuel cell"),
           Patch(fc=C["CHP"], label="CHP"), Patch(fc=C["Buy"], label="Grid import"), Patch(fc=C["Feed"], alpha=0.5, label="Grid export"),
           Patch(fc=C["Elyz"], alpha=0.5, label="Electrolyser"), Line2D([], [], color=C["Dem"], lw=1, label="Demand")]
    seas = [Patch(fc=SH[0], ec="#c9d6e8", label="Winter"), Patch(fc=SH[1], ec="#cfe0cf", label="Spring"),
            Patch(fc=SH[2], ec="#ead9b0", label="Summer"), Patch(fc=SH[3], ec="#e6cbc8", label="Autumn")]
    fig.legend(handles=leg, ncol=8, loc="lower center", bbox_to_anchor=(0.5, -0.03), fontsize=8, handlelength=1.1, columnspacing=1.0)
    fig.legend(handles=seas, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.075), fontsize=8,
               title="Representative weeks (non-contiguous seasons)", title_fontsize=8)
    fig.tight_layout(rect=(0, 0.08, 1, 1)); fig.savefig(f"{OUT}/disp_grid_all.png", bbox_inches="tight", dpi=300); plt.close()


def fig_techmix(D):
    xs = np.arange(6); el = lambda s, k: D[s]["elec"].get(k, 0); he = lambda s, k: D[s]["heat"].get(k, 0)
    fig, axs = plt.subplots(1, 3, figsize=(12.5, 4.4))
    ax = axs[0]; bot = np.zeros(6)
    for k, c, lab in [("Photovoltaics", C["PV"], "PV"), ("Hydrogen FC", C["FC"], "H$_2$ fuel cell"), ("CHP", C["CHP"], "CHP"), ("Purchase", C["Buy"], "Grid purchase")]:
        vv = np.array([el(s, k) for s in ORDER]); ax.bar(xs, vv, 0.62, bottom=bot, color=c, label=lab, edgecolor="white", lw=0.3); bot = bot + vv
    ax.set_title("(a) Electricity generation", loc="left"); ax.set_ylabel("Energy (MWh yr$^{-1}$)")
    ax = axs[2]; bot = np.zeros(6)
    for k, c, lab in [("Boiler GN", C["Boiler"], "Gas boiler"), ("Boiler Elec", "#999", "Electric boiler"), ("CHP", C["CHP"], "CHP"), ("Solarthermal", C["Solar"], "Solar thermal"), ("Heatpump", C["HP"], "Heat pump")]:
        vv = np.array([he(s, k) for s in ORDER]); ax.bar(xs, vv, 0.62, bottom=bot, color=c, label=lab, edgecolor="white", lw=0.3); bot = bot + vv
    ax.set_title("(c) Hot-water & cooking heat", loc="left"); ax.set_ylabel("Heat (MWh yr$^{-1}$)"); ax.set_ylim(0, 33)
    axs[1].set_title("(b) see paper for electricity-use split", loc="left", fontsize=8)
    for ax in (axs[0], axs[2]):
        ax.set_xticks(xs); ax.set_xticklabels(ORDER, fontsize=8.6); ax.axvline(2.5, color="#b0b0b0", ls="--", lw=0.9)
        ax.grid(axis="y", color="#d5d5d5", lw=0.6); ax.legend(fontsize=7.6, loc="upper right")
    fig.tight_layout(); fig.savefig(f"{OUT}/tech_mix.png", bbox_inches="tight", dpi=300); plt.close()


def fig_interperiod(D):
    yrs = [2025, 2030, 2035, 2040]; c = D["S6"]
    pv = [c["caps"][y].get("Photovoltaics", 0) for y in yrs]; hp = [c["caps"][y].get("Heatpump", 0) for y in yrs]
    bo = [c["caps"][y].get("Boiler GN", 0) for y in yrs]; bt = [c["stoc"][y].get("Battery", 0) for y in yrs]
    fig, ax = plt.subplots(figsize=(7.4, 4.4)); ax2 = ax.twinx()
    ax.plot(yrs, pv, "-o", color=C["PV"], lw=2, label="PV (kW$_p$)")
    ax.plot(yrs, bt, "-s", color=C["Batt"], lw=2, label="Battery (kWh)")
    ax.plot(yrs, [h * 10 for h in hp], "-^", color=C["HP"], lw=2, label="Heat pump (kW $\\times$10)")
    ax.plot(yrs, bo, "-D", color=C["Boiler"], lw=2, label="Gas boiler (kW)")
    ax2.plot(yrs, [25, 60, 90, 120], "--", color="#7f7f7f", lw=1.6, label="CO$_2$ price")
    ax.set_xlabel("Planning year"); ax.set_ylabel("Installed capacity"); ax2.set_ylabel("CO$_2$ price (USD tCO$_2^{-1}$)", color="#7f7f7f")
    ax2.tick_params(axis="y", colors="#7f7f7f"); ax.set_xticks(yrs); ax.grid(axis="y", color="#d5d5d5", lw=0.6)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, ncol=2, fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig(f"{OUT}/interperiod_s6.png", bbox_inches="tight", dpi=300); plt.close()


if __name__ == "__main__":
    print("Selecting four seasonal medoid weeks ...")
    starts = R.select_seasonal_weeks()
    print(f"  week starts: {starts}")
    D = {}
    for s in ORDER:
        print(f"Solving {s} ...")
        D[s] = solve_full(s, starts)
    print("Rendering figures ...")
    fig_capacity(D); fig_cost(D); fig_dispatch(D); fig_techmix(D); fig_interperiod(D)
    print(f"Done. Figures written to {OUT}/")
