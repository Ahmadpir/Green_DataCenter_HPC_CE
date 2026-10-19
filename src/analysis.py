"""All numerical experiments (run in parallel on CPU). Results go to code/outputs/results.json."""
import copy
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from carbon import ci_matrix
from common import DATA, OUT, load_cfg
from scheduler import simulate, savings

FLEX = ["photo", "ota", "train"]
_CI = {}


def _ci(cfg, which):
    if which not in _CI:
        _CI[which] = ci_matrix(cfg, which)[0]
    return _CI[which]


def _variant(cfg, mod):
    c = copy.deepcopy(cfg)
    if "voice_share" in mod:
        vs = mod["voice_share"]
        rest = 1 - cfg["workloads"]["voice"]["share"]
        for k in FLEX:
            c["workloads"][k]["share"] = cfg["workloads"][k]["share"] * (1 - vs) / rest
        c["workloads"]["voice"]["share"] = vs
    if mod.get("photo_residency"):
        c["workloads"]["photo"]["spatial"] = False
    return c


def _task(args):
    """Worker: one simulation. args = (key, ef_set, cfg_mod, pue_override, home, kwargs)."""
    key, which, mod, pue_o, home, kw = args
    import warnings
    warnings.filterwarnings("ignore")
    cfg = load_cfg()
    c = _variant(cfg, mod)
    ci = _ci(cfg, which)
    pue = pue_o or [r["pue"] for r in cfg["regions"]]
    return key, simulate(ci, pue, home, c, **kw)


def regional_stats(ci, cfg):
    rows = []
    for r in cfg["regions"]:
        s = ci[r["code"]]
        daily = s.groupby(s.index.tz_convert("Europe/Berlin").date)
        rows.append(dict(code=r["code"], name=r["name"], pue=r["pue"], pue_source=r["pue_source"],
                         mean=s.mean(), p10=s.quantile(0.10), p90=s.quantile(0.90),
                         daily_swing=(daily.max() - daily.min()).mean(), effective=s.mean() * r["pue"]))
    return rows


def validate_dk(ci, cfg):
    """Cross-check our generation-based DK series against Energinet's published CO2Emis
    (consumption-based, includes imports; simple mean of DK1 and DK2)."""
    year = cfg["study"]["year"]
    en = pd.read_csv(DATA / f"energinet_dk_co2emis_{year}_hourly.csv", index_col=0)
    en.index = pd.to_datetime(en.index, utc=True)
    j = pd.concat([ci["DK"], en[["DK1", "DK2"]].mean(axis=1)], axis=1, keys=["ours", "energinet"]).dropna()
    dj = j.groupby(j.index.date).mean()
    return dict(n_hours=len(j), pearson_hourly=float(j.corr().iloc[0, 1]),
                pearson_daily=float(dj.corr().iloc[0, 1]),
                mean_ours=float(j["ours"].mean()), mean_energinet=float(j["energinet"].mean()))


def summarise(base, res):
    out = dict(total=savings(base, res), flexible=savings(base, res, FLEX))
    for k in base:
        out[k] = savings(base, res, [k])
    it_flex = sum(res[k]["it_mwh"] for k in FLEX)
    out["moved_share_flex"] = 100 * sum(res[k]["moved_share"] * res[k]["it_mwh"] for k in FLEX) / it_flex
    out["mean_delay_flex_h"] = sum(res[k]["mean_delay_h"] * res[k]["it_mwh"] for k in FLEX) / it_flex
    out["overflow_flex"] = 100 * sum(res[k]["overflow_share"] * res[k]["it_mwh"] for k in FLEX) / it_flex
    out["region_share_flex"] = {c: 100 * sum(res[k]["region_share"][c] * res[k]["it_mwh"] for k in FLEX) / it_flex
                                for c in res[FLEX[0]]["region_share"]}
    out["emissions_t"] = sum(v["emissions_t"] for v in res.values())
    out["energy_mwh"] = sum(v["energy_mwh"] for v in res.values())
    return out


def build_tasks(cfg):
    home = cfg["study"]["home_region"]
    S = cfg["sensitivity"]
    T = []
    add = lambda key, which="med", mod=None, pue=None, h=home, **kw: T.append((key, which, mod or {}, pue, h, kw))
    add("base", strategy="baseline")
    for fc in ["persistence", "oracle"]:
        for st in ["temporal", "spatial", "spatiotemporal", "pue_blind", "lowest_pue"]:
            add(f"main|{fc}|{st}", strategy=st, forecast=fc)
    for fc in ["persistence", "oracle"]:          # explicit PUE tie-breaks (NL and DK both 1.07)
        for tie in ["NL", "DK"]:
            add(f"lptie|{fc}|{tie}", strategy="lowest_pue", forecast=fc, tie=tie)
    for st in ["temporal", "spatiotemporal"]:     # France as home with a perfect forecast
        add(f"sweepo|FR|{st}", h="FR", strategy=st, forecast="oracle")
    for r in cfg["regions"]:
        c = r["code"]
        add(f"sweep|{c}|baseline", h=c, strategy="baseline")
        add(f"sweep|{c}|temporal", h=c, strategy="temporal")
        add(f"sweep|{c}|spatiotemporal", h=c, strategy="spatiotemporal")
    for st in ["temporal", "spatial", "spatiotemporal"]:
        for s in S["window_scale"]:
            add(f"win|{st}|{s}", strategy=st, window_scale=s)
    for h in S["headroom_factor"]:
        add(f"oat|headroom_factor|{h}", headroom=h)
    for e in S["migration_overhead"]:
        add(f"oat|migration_overhead|{e}", eps=e)
    n = len(cfg["regions"])
    for w in S["emission_factor_set"]:
        add(f"oatb|emission_factor_set|{w}", which=w, strategy="baseline")
        add(f"oat|emission_factor_set|{w}", which=w)
    for p in S["pue_scenario"]:
        pv = None if p == "published" else [float(p.split("_")[1])] * n
        add(f"oatb|pue_scenario|{p}", pue=pv, strategy="baseline")
        add(f"oat|pue_scenario|{p}", pue=pv)
    for p in S["arrival_profile"]:
        po = "flat" if p == "all_flat" else None
        add(f"oatb|arrival_profile|{p}", strategy="baseline", profile_override=po)
        add(f"oat|arrival_profile|{p}", profile_override=po)
    for vs in [0.2, 0.35, 0.5, 0.7]:
        add(f"oatb|voice_share|{vs}", mod={"voice_share": vs}, strategy="baseline")
        add(f"oat|voice_share|{vs}", mod={"voice_share": vs})
    # practical constraints: photo data must stay in the home country; best region unavailable
    add("oatb|photo_residency|yes", mod={"photo_residency": True}, strategy="baseline")
    add("oat|photo_residency|yes", mod={"photo_residency": True})
    add("oat|exclude_best|FR", exclude=("FR",))
    add("oat|exclude_best|FR+FI", exclude=("FR", "FI"))
    return T


def main():
    t0 = time.time()
    cfg = load_cfg()
    ci, info = ci_matrix(cfg, "med")
    OUT.mkdir(exist_ok=True)
    ci.round(2).to_csv(OUT / "hourly_carbon_intensity_gco2e_per_kwh.csv.gz", compression="gzip")
    R = {"data_info": info, "regions": regional_stats(ci, cfg), "validation_dk": validate_dk(ci, cfg)}
    tasks = build_tasks(cfg)
    workers = max(1, min(8, (os.cpu_count() or 2) - 1))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        out = dict(ex.map(_task, tasks))
    print(f"{len(tasks)} simulations on {workers} workers: {time.time() - t0:.0f}s")
    base = out["base"]
    R["baseline"] = base
    R["baseline_total_t"] = sum(v["emissions_t"] for v in base.values())
    R["baseline_energy_mwh"] = sum(v["energy_mwh"] for v in base.values())
    R["main"] = {fc: {st: summarise(base, out[f"main|{fc}|{st}"])
                      for st in ["temporal", "spatial", "spatiotemporal", "pue_blind", "lowest_pue"]}
                 for fc in ["persistence", "oracle"]}
    R["home_sweep"] = {}
    for r in cfg["regions"]:
        c = r["code"]
        b = out[f"sweep|{c}|baseline"]
        R["home_sweep"][c] = dict(temporal=savings(b, out[f"sweep|{c}|temporal"]),
                                  spatiotemporal=savings(b, out[f"sweep|{c}|spatiotemporal"]),
                                  temporal_flex=savings(b, out[f"sweep|{c}|temporal"], FLEX),
                                  baseline_t=sum(v["emissions_t"] for v in b.values()))
    R["lowest_pue_tie"] = {fc: {tie: summarise(base, out[f"lptie|{fc}|{tie}"]) for tie in ["NL", "DK"]}
                           for fc in ["persistence", "oracle"]}
    bfr = out["sweep|FR|baseline"]
    R["home_FR_oracle"] = {st: savings(bfr, out[f"sweepo|FR|{st}"]) for st in ["temporal", "spatiotemporal"]}
    R["window_sensitivity_flex"] = {st: {str(s): savings(base, out[f"win|{st}|{s}"], FLEX)
                                         for s in cfg["sensitivity"]["window_scale"]}
                                    for st in ["temporal", "spatial", "spatiotemporal"]}
    oat = {"reference": summarise(base, out["main|persistence|spatiotemporal"])["total"]}
    for key, res in out.items():
        if not key.startswith("oat|"):
            continue
        _, par, val = key.split("|")
        b = out.get(f"oatb|{par}|{val}", base)
        oat.setdefault(par, {})[val] = summarise(b, res)["total"]
    R["headroom_detail"] = {str(h): summarise(base, out[f"oat|headroom_factor|{h}"])
                            for h in cfg["sensitivity"]["headroom_factor"]}
    pr = summarise(out["oatb|photo_residency|yes"], out["oat|photo_residency|yes"])
    R["photo_residency"] = pr
    R["oat_total"] = oat
    R["runtime_s"] = time.time() - t0

    def conv(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        raise TypeError(type(o))
    with open(OUT / "results.json", "w", encoding="utf8") as f:
        json.dump(R, f, indent=1, default=conv)
    print(f"analysis finished in {R['runtime_s']:.0f}s")
    return R


if __name__ == "__main__":
    main()
