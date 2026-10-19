"""LaTeX tables and a macro file (latex/numbers.tex) so that every number quoted in the text
comes straight from code/outputs/results.json."""
import json

from common import OUT, PAPER, TAB, load_cfg

EXAMPLES = {"voice": "Wake-word follow-up, speech recognition, answer generation",
            "photo": "Cloud photo library: face/object tagging, search index",
            "ota": "Firmware build, signing, delta packages for TVs, wearables",
            "train": "Periodic re-training or fine-tuning of on-device models"}


def nz(x, f="{:.0f}"):
    """Format a number, printing a rounded negative zero as 0."""
    out = f.format(x)
    return "0" if out in ("-0", "-0.0") else out


def t1(cfg):
    L = [r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{1.95cm}>{\raggedright\arraybackslash}p{2.75cm}cccc@{}}",
         r"\hline",
         r"Workload class & Example CE service & $W$ (h) & $d$ (h) & Move? & Share \\", r"\hline"]
    for k, w in cfg["workloads"].items():
        L.append(f"{w['label']} & {EXAMPLES[k]} & {w['window_h']} & {w['duration_h']} & "
                 f"{'yes' if w['spatial'] else 'no'} & {100 * w['share']:.0f}\\% \\\\")
    L += [r"\hline", r"\end{tabular}"]
    (TAB / "tab1_workloads.tex").write_text("\n".join(L) + "\n", encoding="utf8")


def t2(cfg, R):
    sw = R["home_sweep"]
    L = [r"\begin{tabular}{@{}lcccccc@{}}", r"\hline",
         r" & & \multicolumn{3}{c}{Grid CI (gCO$_2$e/kWh)} & CI$\times$PUE & Saving as home \\",
         r"Region & PUE & Mean & P10--P90 & Swing & Mean & T / ST (\%) \\", r"\hline"]
    for r in sorted(R["regions"], key=lambda x: x["mean"]):
        s = sw[r["code"]]
        star = "" if r["pue"] < 1.2 else "$^{*}$"
        L.append(f"{r['code']} & {r['pue']:.2f}{star} & {r['mean']:.0f} & {r['p10']:.0f}--{r['p90']:.0f} & "
                 f"{r['daily_swing']:.0f} & {r['effective']:.0f} & {nz(s['temporal'])} / {nz(s['spatiotemporal'])} \\\\")
    L += [r"\hline", r"\end{tabular}"]
    (TAB / "tab2_regions.tex").write_text("\n".join(L) + "\n", encoding="utf8")


def t3(R):
    p, o = R["main"]["persistence"], R["main"]["oracle"]
    names = [("lowest_pue", "Lowest-PUE site (NL/DK split)"), ("temporal", "Temporal, home region"),
             ("spatial", "Spatial, run now"), ("pue_blind", "Spatio-temporal, PUE-blind"),
             ("spatiotemporal", r"Spatio-temporal, CI$\times$PUE")]
    L = [r"\begin{tabular}{@{}lccccc@{}}", r"\hline",
         r" & \multicolumn{2}{c}{Fleet saving (\%)} & Deferrable & Moved & Mean \\",
         r"Strategy & Persist. & Oracle & saving (\%) & out (\%) & delay (h) \\", r"\hline"]
    for k, lab in names:
        L.append(f"{lab} & {p[k]['total']:.1f} & {o[k]['total']:.1f} & {p[k]['flexible']:.1f} & "
                 f"{p[k]['moved_share_flex']:.0f} & {p[k]['mean_delay_flex_h']:.1f} \\\\")
    L += [r"\hline", r"\end{tabular}"]
    (TAB / "tab3_results.tex").write_text("\n".join(L) + "\n", encoding="utf8")


def macros(cfg, R):
    p, o = R["main"]["persistence"], R["main"]["oracle"]
    reg = {r["code"]: r for r in R["regions"]}
    means = sorted(R["regions"], key=lambda r: r["mean"])
    oat = R["oat_total"]
    sw = R["home_sweep"]
    v = R["validation_dk"]
    M = {
        "SavST": p["spatiotemporal"]["total"], "SavSTo": o["spatiotemporal"]["total"],
        "SavSTflex": p["spatiotemporal"]["flexible"], "SavSTflexo": o["spatiotemporal"]["flexible"],
        "SavT": p["temporal"]["total"], "SavTflex": p["temporal"]["flexible"],
        "SavTo": o["temporal"]["total"],
        "SavS": p["spatial"]["total"], "SavSflex": p["spatial"]["flexible"],
        "SavPB": p["pue_blind"]["total"], "SavLP": p["lowest_pue"]["total"],
        "SavPhoto": p["spatiotemporal"]["photo"], "SavOta": p["spatiotemporal"]["ota"],
        "SavTrain": p["spatiotemporal"]["train"],
        "SavTPhoto": p["temporal"]["photo"], "SavTOta": abs(p["temporal"]["ota"]), "SavTTrain": p["temporal"]["train"],
        "MovedST": p["spatiotemporal"]["moved_share_flex"], "DelayST": p["spatiotemporal"]["mean_delay_flex_h"],
        "DelayT": p["temporal"]["mean_delay_flex_h"],
        "OverflowST": p["spatiotemporal"]["overflow_flex"],
        "BaseT": R["baseline_total_t"], "BaseMWh": R["baseline_energy_mwh"],
        "STT": p["spatiotemporal"]["emissions_t"],
        "CIminCode": means[0]["code"], "CIminMean": means[0]["mean"],
        "CImaxCode": means[-1]["code"], "CImaxMean": means[-1]["mean"],
        "CIratio": means[-1]["mean"] / means[0]["mean"],
        "CIde": reg["DE"]["mean"], "CIdeSwing": reg["DE"]["daily_swing"], "CIdeEff": reg["DE"]["effective"],
        "CIdeP": reg["DE"]["p10"], "CIdePn": reg["DE"]["p90"],
        "CIplSwing": reg["PL"]["daily_swing"], "CIfrSwing": reg["FR"]["daily_swing"],
        "OatHeadLo": min(oat["headroom_factor"].values()), "OatHeadHi": max(oat["headroom_factor"].values()),
        "OatHeadLow": oat["headroom_factor"]["1.1"],
        "OatMigHi": oat["migration_overhead"]["0.2"], "OatMigZero": oat["migration_overhead"]["0.0"],
        "OatEFmin": oat["emission_factor_set"]["min"], "OatEFmax": oat["emission_factor_set"]["max"],
        "OatPUEa": oat["pue_scenario"]["all_1.09"], "OatPUEb": oat["pue_scenario"]["all_1.54"],
        "OatFlat": oat["arrival_profile"]["all_flat"],
        "OatVoiceLo": oat["voice_share"]["0.7"], "OatVoiceHi": oat["voice_share"]["0.2"],
        "WinHalfST": R["window_sensitivity_flex"]["spatiotemporal"]["0.5"],
        "WinZeroST": R["window_sensitivity_flex"]["spatiotemporal"]["0.0"],
        "WinThreeST": R["window_sensitivity_flex"]["spatiotemporal"]["3.0"],
        "WinThreeT": R["window_sensitivity_flex"]["temporal"]["3.0"],
        "WinQuarterT": R["window_sensitivity_flex"]["temporal"]["0.25"],
        "SweepTmin": min(s["temporal"] for s in sw.values()), "SweepTmax": max(s["temporal"] for s in sw.values()),
        "SweepSTmin": min(s["spatiotemporal"] for s in sw.values()),
        "SweepSTmax": max(s["spatiotemporal"] for s in sw.values()),
        "ValR": v["pearson_hourly"], "ValRd": v["pearson_daily"], "ValOurs": v["mean_ours"],
        "ValEn": v["mean_energinet"], "Runtime": R["runtime_s"] / 60,
        "SweepSTfr": sw["FR"]["spatiotemporal"], "SweepSTfi": sw["FI"]["spatiotemporal"],
        "SweepSTpl": sw["PL"]["spatiotemporal"],
        "SweepTde": sw["DE"]["temporal"], "SweepTflexmax": max(s["temporal_flex"] for s in sw.values()),
        "SavToflex": o["temporal"]["flexible"], "SavSo": o["spatial"]["total"],
        "SavPBo": o["pue_blind"]["total"], "SavLPflex": p["lowest_pue"]["flexible"],
        "SavTOtao": abs(o["temporal"]["ota"]), "OverflowT": p["temporal"]["overflow_flex"],
        "OatRes": oat["photo_residency"]["yes"], "OatResPhoto": R["photo_residency"]["photo"],
        "OatExFR": oat["exclude_best"]["FR"], "OatExFRFI": oat["exclude_best"]["FR+FI"],
        "OatHeadInf": oat["headroom_factor"]["100.0"],
        "SavLPnl": R["lowest_pue_tie"]["persistence"]["NL"]["total"],
        "SavLPdk": R["lowest_pue_tie"]["persistence"]["DK"]["total"],
        "FRoT": R["home_FR_oracle"]["temporal"], "FRoST": R["home_FR_oracle"]["spatiotemporal"],
        "FRpT": sw["FR"]["temporal"], "FRpST": sw["FR"]["spatiotemporal"],
        "OatHeadQ": oat["headroom_factor"]["0.25"], "OatHeadH": oat["headroom_factor"]["0.5"],
        "FRshareST": p["spatiotemporal"]["region_share_flex"]["FR"],
        "FRshareQ": R["headroom_detail"]["0.25"]["region_share_flex"]["FR"],
        "STTo": o["spatiotemporal"]["emissions_t"], "SpatT": p["spatial"]["emissions_t"],
        "SavedT": R["baseline_total_t"] - p["spatiotemporal"]["emissions_t"],
        "ITMWh": sum(v["it_mwh"] for v in R["baseline"].values()),
        "EnergyST": p["spatiotemporal"]["energy_mwh"],
        "WinHalfT": R["window_sensitivity_flex"]["temporal"]["0.5"],
        "CIfi": reg["FI"]["mean"], "CIfiEff": reg["FI"]["effective"], "CIfrEff": reg["FR"]["effective"],
        "CIplEff": reg["PL"]["effective"], "CInlEff": reg["NL"]["effective"],
        "ResDrop": p["spatiotemporal"]["total"] - oat["photo_residency"]["yes"],
        "SpaceTimeRatio": p["spatial"]["total"] / p["temporal"]["total"],
    }
    fmt = {"CIratio": "{:.0f}", "ValR": "{:.2f}", "ValRd": "{:.2f}", "DelayST": "{:.1f}", "DelayT": "{:.1f}",
           "Runtime": "{:.0f}", "OverflowST": "{:.1f}", "BaseMWh": "{:,.0f}", "BaseT": "{:,.0f}", "STT": "{:,.0f}",
           "STTo": "{:,.0f}", "SpatT": "{:,.0f}", "SavedT": "{:,.0f}", "ITMWh": "{:,.0f}", "EnergyST": "{:,.0f}",
           "SavST": "{:.1f}", "SavS": "{:.1f}", "SavPB": "{:.1f}", "SavSTo": "{:.1f}", "SavT": "{:.1f}",
           "SavTo": "{:.1f}", "SavLP": "{:.1f}", "SavLPnl": "{:.1f}", "SavLPdk": "{:.1f}", "FRoT": "{:.1f}", "FRoST": "{:.1f}", "FRpT": "{:.1f}", "FRpST": "{:.1f}", "OverflowT": "{:.1f}", "SavSo": "{:.1f}", "SavPBo": "{:.1f}"}
    lines = ["% AUTO-GENERATED by code/src/tables.py from code/outputs/results.json. Do not edit."]
    for k, val in M.items():
        if isinstance(val, str):
            s = val
        else:
            s = nz(val, fmt.get(k, "{:.0f}"))
        lines.append(f"\\newcommand{{\\{k}}}{{{s}}}")
    (PAPER / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf8")


def main():
    cfg = load_cfg()
    R = json.load(open(OUT / "results.json", encoding="utf8"))
    TAB.mkdir(parents=True, exist_ok=True)
    t1(cfg); t2(cfg, R); t3(R); macros(cfg, R)


if __name__ == "__main__":
    main()
