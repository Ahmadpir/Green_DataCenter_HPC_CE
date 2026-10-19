"""Hourly grid carbon intensity from public generation data (production-based, life-cycle factors)."""
import warnings

import numpy as np
import pandas as pd

from common import DATA


def load_generation(cc, year):
    f = DATA / f"energycharts_public_power_{cc}_{year}_hourly.csv.gz"
    df = pd.read_csv(f, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def intensity(gen, cfg, which="med"):
    """Generation-weighted life-cycle intensity in gCO2eq/kWh for each hour."""
    ef = cfg["emission_factors"]
    skip = set(cfg["non_generation"])
    num = pd.Series(0.0, index=gen.index)
    den = pd.Series(0.0, index=gen.index)
    unknown = []
    for col in gen.columns:
        if col in skip or col in cfg["storage_types"]:
            continue  # non-generation series and storage discharge are excluded (see config)
        if col not in ef:
            unknown.append(col)
            factor = ef["Others"][which]
        else:
            factor = ef[col][which]
        g = gen[col].clip(lower=0).fillna(0.0)
        num += g * factor
        den += g
    if unknown:
        warnings.warn(f"production types without factor, used 'Others': {unknown}")
    ci = num / den.replace(0, np.nan)
    return ci, unknown


def ci_matrix(cfg, which="med"):
    """DataFrame (hours x region code) of intensity, gaps filled by time interpolation."""
    year = cfg["study"]["year"]
    idx = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq="1h", inclusive="left", tz="UTC")
    cols, info = {}, {}
    for r in cfg["regions"]:
        if r.get("ci_source") == "neso":
            neso = pd.read_csv(DATA / f"neso_gb_carbon_intensity_{year}_hourly.csv", index_col=0)
            neso.index = pd.to_datetime(neso.index, utc=True)
            ci, unknown = neso["actual"].reindex(idx), []
        else:
            gen = load_generation(r["energy_charts_country"], year).reindex(idx)
            ci, unknown = intensity(gen, cfg, which)
        n_missing = int(ci.isna().sum())
        ci = ci.interpolate(limit_direction="both")
        cols[r["code"]] = ci
        info[r["code"]] = {"missing_hours_filled": n_missing, "unknown_types": unknown}
    return pd.DataFrame(cols, index=idx), info
