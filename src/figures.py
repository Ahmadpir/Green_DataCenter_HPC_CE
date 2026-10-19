"""Figures (300 dpi PNG + vector PDF) for the article. Okabe-Ito colour-blind-safe palette."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd

from common import FIG, OUT, load_cfg

OI = {"black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
      "yellow": "#F0E442", "blue": "#0072B2", "verm": "#D55E00", "purple": "#CC79A7", "grey": "#999999"}
plt.rcParams.update({"font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5, "legend.fontsize": 6.5,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "font.family": "DejaVu Sans",
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
W1 = 3.45  # single magazine column, inches


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=350, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def _box(ax, x, y, w, h, text, fc, ec="#333333", fs=6.6, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=0.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", wrap=True)


def _arrow(ax, p, q, color="#333333", ls="-", lw=1.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=7, color=color, lw=lw, ls=ls))


def fig_architecture():
    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    light = {"dev": "#DCEFFA", "ctl": "#FCE8C3", "dc": "#D4F0E6", "data": "#EFE3EE", "rep": "#EEEEEE"}
    fs = 6.0
    ax.text(0.09, 0.965, "Consumer devices", ha="center", fontsize=7, fontweight="bold")
    devs = ["Smartphones\n(photo/video backup)", "Smart speakers\n(voice assistant)",
            "Wearables, TVs, IoT\n(OTA firmware)", "On-device AI models\n(retraining data)"]
    for i, t in enumerate(devs):
        _box(ax, 0.015, 0.75 - i * 0.2, 0.15, 0.15, t, light["dev"], fs=fs)
    _box(ax, 0.21, 0.56, 0.15, 0.28, "Ingest API in\nhome region\n(upload, request,\nconsent, residency)",
         light["ctl"], fs=fs)
    for i in range(4):
        _arrow(ax, (0.168, 0.825 - i * 0.2), (0.208, 0.70))
    _box(ax, 0.21, 0.13, 0.15, 0.32, "Workload tagging:\nwindow W,\nduration d,\nallowed regions,\npriority (Table 1)",
         light["ctl"], fs=fs)
    _arrow(ax, (0.285, 0.555), (0.285, 0.455))
    _box(ax, 0.415, 0.31, 0.21, 0.40, "Carbon- and PUE-aware\nscheduler\n\nrank (region, start) by\n"
         "forecast CI × PUE × energy;\nfill under headroom;\nfall back at deadline", "#F9D9A8", fs=fs)
    _arrow(ax, (0.362, 0.29), (0.413, 0.45))
    _arrow(ax, (0.362, 0.80), (0.70, 0.80), color=OI["verm"])
    ax.text(0.53, 0.815, "non-deferrable (voice):\nserve now in home region (DE)", color=OI["verm"], fontsize=5.8,
            ha="center", va="bottom")
    _box(ax, 0.415, 0.04, 0.21, 0.18, "Signals: grid carbon intensity\n(Energy-Charts, NESO),\n"
         "PUE table, spare capacity", light["data"], fs=5.8)
    _arrow(ax, (0.52, 0.225), (0.52, 0.305))
    ax.text(0.845, 0.965, "Data-center region pool", ha="center", fontsize=7, fontweight="bold")
    regs = [("DE (home)", "1.54*"), ("IE", "1.08"), ("NL", "1.07"), ("BE", "1.08"), ("DK", "1.07"),
            ("FI", "1.10"), ("UK", "1.54*"), ("FR", "1.54*"), ("PL", "1.54*")]
    for i, (c, p) in enumerate(regs):
        col, row = i % 3, i // 3
        _box(ax, 0.705 + col * 0.1, 0.73 - row * 0.19, 0.075, 0.15, f"{c}\nPUE {p}", light["dc"], fs=fs)
    _arrow(ax, (0.628, 0.51), (0.70, 0.51))
    ax.text(0.70, 0.27, "* industry-average PUE assumed", fontsize=5.6, ha="left", style="italic")
    _box(ax, 0.705, 0.03, 0.272, 0.15, "Carbon accounting and reporting\n(per-service gCO$_2$e, delay,\n"
         "share of work moved)", light["rep"], fs=fs)
    _arrow(ax, (0.945, 0.345), (0.945, 0.185), ls="--")
    save(fig, "fig1_architecture")


def fig_regions(ci, R, cfg):
    codes = [r["code"] for r in cfg["regions"]]
    stats = {r["code"]: r for r in R["regions"]}
    order = sorted(codes, key=lambda c: stats[c]["mean"])
    fig, axes = plt.subplots(1, 2, figsize=(W1 * 2.03, 2.25), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    data = [ci[c].values for c in order]
    bp = ax.boxplot(data, whis=(10, 90), showfliers=False, patch_artist=True, widths=0.55,
                    medianprops={"color": "black", "lw": 0.9})
    for patch, c in zip(bp["boxes"], order):
        patch.set_facecolor(OI["green"] if stats[c]["pue"] < 1.2 else OI["sky"])
        patch.set_alpha(0.8)
    ax.scatter(range(1, len(order) + 1), [stats[c]["effective"] for c in order], marker="D", s=12,
               color=OI["verm"], zorder=5, label="mean CI × PUE")
    ax.set_xticks(range(1, len(order) + 1)); ax.set_xticklabels(order)
    ax.set_ylabel("gCO$_2$e per kWh"); ax.set_title("(a) Hourly grid carbon intensity, 2025", loc="left")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(fc=OI["green"], alpha=0.8, label="published campus PUE"),
                       Patch(fc=OI["sky"], alpha=0.8, label="industry-average PUE"),
                       plt.Line2D([], [], marker="D", ls="", color=OI["verm"], ms=3.5, label="mean CI × PUE")],
              loc="upper left", frameon=False)
    ax = axes[1]
    loc = ci.index.tz_convert("Europe/Berlin")
    pick = ["PL", "DE", "UK", "NL", "FR"]
    cols = [OI["black"], OI["verm"], OI["purple"], OI["blue"], OI["green"]]
    styles = ["-", "--", "-.", ":", "-"]
    for c, col, ls in zip(pick, cols, styles):
        prof = ci[c].groupby(loc.hour).mean()
        ax.plot(prof.index, prof.values, color=col, ls=ls, lw=1.2, label=c)
    ax.set_xlabel("Hour of day (CET/CEST)"); ax.set_ylabel("Mean gCO$_2$e per kWh")
    ax.set_xticks([0, 6, 12, 18, 23]); ax.set_title("(b) Average daily profile", loc="left")
    ax.legend(ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.0), columnspacing=0.8,
              handlelength=1.6)
    ax.set_ylim(0, max(ci[pick].groupby(loc.hour).mean().max()) * 1.25)
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig2_regions")


def fig_savings(R, cfg):
    m = R["main"]["persistence"]
    o = R["main"]["oracle"]
    strategies = [("lowest_pue", "Lowest-PUE site\n(NL/DK tie split)"), ("temporal", "Temporal\n(home only)"),
                  ("spatial", "Spatial\n(run now)"), ("pue_blind", "Spatio-temp.\nPUE-blind"),
                  ("spatiotemporal", "Spatio-temp.\nCI × PUE")]
    classes = [("photo", "Photo/video indexing", OI["blue"]), ("ota", "OTA packaging", OI["orange"]),
               ("train", "Model retraining", OI["green"]), ("total", "Whole fleet (incl. voice)", OI["black"])]
    fig, ax = plt.subplots(figsize=(W1 * 2.03, 2.2))
    x = np.arange(len(strategies)); w = 0.2
    for i, (k, lab, col) in enumerate(classes):
        vals = [m[s][k] for s, _ in strategies]
        ax.bar(x + (i - 1.5) * w, vals, w, color=col, label=lab, alpha=0.9 if k != "total" else 1)
        ov = [o[s][k] for s, _ in strategies]
        ax.scatter(x + (i - 1.5) * w, ov, marker="_", s=40, color=OI["verm"], zorder=5, lw=1.4,
                   label="perfect-forecast bound" if i == 0 else None)
    tie = R["lowest_pue_tie"]["persistence"]
    for i, (k, _, _) in enumerate(classes):          # PUE tie range: all to NL ... all to DK
        lo, hi = sorted([tie["NL"][k], tie["DK"][k]])
        ax.plot([x[0] + (i - 1.5) * w] * 2, [lo, hi], color=OI["grey"], lw=1.0, zorder=6,
                label="tie range (all NL to all DK)" if i == 0 else None)
    for xi, (s, _) in zip(x, strategies):
        top = max(m[s]["total"], o[s]["total"])
        if s == "lowest_pue":
            top = max(top, tie["NL"]["total"], tie["DK"]["total"])
        ax.text(xi + 1.5 * w, top + 2.5, f"{m[s]['total']:.0f}%", ha="center", fontsize=6.2)
    ax.set_xticks(x); ax.set_xticklabels([l for _, l in strategies])
    ax.set_ylabel("CO$_2$e reduction vs.\nrun-now-at-home (%)")
    ax.axhline(0, color="black", lw=0.6)
    ax.legend(ncol=3, frameon=False, loc="upper left", fontsize=6.3)
    ax.set_ylim(min(0, min(m[s][k] for s, _ in strategies for k, _, _ in classes)) - 3, 122)
    fig.tight_layout()
    save(fig, "fig3_savings")


def fig_sensitivity(R, cfg):
    fig, axes = plt.subplots(1, 2, figsize=(W1 * 2.03, 2.25), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axes[0]
    win = R["window_sensitivity_flex"]
    sty = {"temporal": (OI["orange"], "--", "Temporal (home only)"),
           "spatial": (OI["blue"], ":", "Spatial (run now)"),
           "spatiotemporal": (OI["green"], "-", "Spatio-temporal")}
    for st, (col, ls, lab) in sty.items():
        xs = [float(k) for k in win[st]]
        ax.plot(xs, list(win[st].values()), color=col, ls=ls, marker="o", ms=3, lw=1.2, label=lab)
    ax.set_xlabel("Deferral window scale (1 = Table 1)")
    ax.set_ylabel("Deferrable-load CO$_2$e reduction (%)")
    ax.set_title("(a) Value of waiting", loc="left")
    ax.legend(frameon=False, loc="center right", bbox_to_anchor=(1.0, 0.45)); ax.set_ylim(0, 100)
    ax = axes[1]
    oat = R["oat_total"]; ref = oat["reference"]
    labels = {"headroom_factor": "Region headroom (0.25-100x)",
              "migration_overhead": "Migration overhead (0-20%)",
              "emission_factor_set": "Emission factors (IPCC min-max)",
              "pue_scenario": "PUE (published / all 1.09 / all 1.54)",
              "arrival_profile": "Arrival profile (diurnal / flat)",
              "voice_share": "Non-deferrable share (20-70%)",
              "photo_residency": "Photo data kept in home country",
              "exclude_best": "Cleanest region(s) unavailable"}
    rows = []
    for k, lab in labels.items():
        v = list(oat[k].values()) + [ref]; rows.append((lab, min(v), max(v)))
    rows.sort(key=lambda r: r[2] - r[1])
    for i, (lab, lo, hi) in enumerate(rows):
        ax.barh(i, hi - lo, left=lo, color=OI["sky"], ec=OI["blue"], lw=0.6, height=0.6)
        ax.text(lo - 0.8, i, f"{lo:.0f}", va="center", ha="right", fontsize=6)
        ax.text(hi + 0.8, i, f"{hi:.0f}", va="center", ha="left", fontsize=6)
    ax.axvline(ref, color=OI["verm"], lw=1, ls="--")
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=6.3)
    ax.set_xlabel("Whole-fleet CO$_2$e reduction (%)")
    ax.set_title(f"(b) One-at-a-time sensitivity (base {ref:.0f}%)", loc="left")
    lo_all = min(r[1] for r in rows); hi_all = max(r[2] for r in rows)
    ax.set_xlim(max(0, lo_all - 8), hi_all + 8)
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig4_sensitivity")


def main():
    cfg = load_cfg()
    R = json.load(open(OUT / "results.json", encoding="utf8"))
    ci = pd.read_csv(OUT / "hourly_carbon_intensity_gco2e_per_kwh.csv.gz", index_col=0)
    ci.index = pd.to_datetime(ci.index, utc=True)
    fig_architecture()
    fig_regions(ci, R, cfg)
    fig_savings(R, cfg)
    fig_sensitivity(R, cfg)


if __name__ == "__main__":
    main()
