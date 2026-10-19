"""Download and cache the public data used in the study (run once; later runs use the cache).

Sources (no account or API key needed):
  * Energy-Charts API (Fraunhofer ISE), /public_power, CC BY 4.0: net public electricity
    generation by production type, 15-min or hourly, per country.
  * NESO (formerly National Grid ESO) Carbon Intensity API, /intensity: GB national
    half-hourly carbon intensity (used only to validate our generation-based method).

Raw responses are reduced to hourly CSV files (UTC) to keep the cache small.
"""
import gzip
import io
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from common import DATA, load_cfg

UA = {"User-Agent": "research-reproducibility-script (P06 carbon-aware CE cloud study)"}


def _get(url, tries=6):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", "40")) + 2
                print(f"  rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError:
            time.sleep(10)
    raise RuntimeError(f"failed to fetch {url}")


def fetch_energy_charts(cc, year):
    out = DATA / f"energycharts_public_power_{cc}_{year}_hourly.csv.gz"
    if out.exists():
        return out
    url = (f"https://api.energy-charts.info/public_power?country={cc}"
           f"&start={year}-01-01T00:00Z&end={year}-12-31T23:59Z")
    print("GET", url)
    d = json.loads(_get(url))
    idx = pd.to_datetime(d["unix_seconds"], unit="s", utc=True)
    df = pd.DataFrame({p["name"]: p["data"] for p in d["production_types"]}, index=idx)
    df = df.apply(pd.to_numeric, errors="coerce")
    hourly = df.resample("1h").mean()
    hourly.index.name = "utc"
    hourly.to_csv(out, compression="gzip", float_format="%.1f")
    time.sleep(35)  # Energy-Charts public limit: 2 requests/min per endpoint
    return out


def fetch_neso(year):
    out = DATA / f"neso_gb_carbon_intensity_{year}_hourly.csv"
    if out.exists():
        return out
    rows = []
    t = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    while t < end:
        t2 = min(t + timedelta(days=13), end)
        url = ("https://api.carbonintensity.org.uk/intensity/"
               f"{t:%Y-%m-%dT%H:%MZ}/{t2:%Y-%m-%dT%H:%MZ}")
        print("GET", url)
        for r in json.loads(_get(url))["data"]:
            rows.append((r["from"], r["intensity"].get("actual"), r["intensity"].get("forecast")))
        t = t2
        time.sleep(1)
    df = pd.DataFrame(rows, columns=["from", "actual", "forecast"]).drop_duplicates("from")
    df["utc"] = pd.to_datetime(df["from"], utc=True)
    df = df.set_index("utc")[["actual", "forecast"]].apply(pd.to_numeric, errors="coerce")
    df = df[(df.index >= f"{year}-01-01") & (df.index < f"{year + 1}-01-01")]
    df.resample("1h").mean().to_csv(out, float_format="%.1f")
    return out


def fetch_energinet(year):
    """Energinet Energi Data Service, dataset CO2Emis (5-min CO2 per kWh consumed, DK1 and DK2).
    Used only to cross-check our generation-based intensity for Denmark."""
    out = DATA / f"energinet_dk_co2emis_{year}_hourly.csv"
    if out.exists():
        return out
    url = ("https://api.energidataservice.dk/dataset/CO2Emis?"
           f"start={year}-01-01T00:00&end={year + 1}-01-01T00:00&timezone=UTC"
           "&columns=Minutes5UTC,PriceArea,CO2Emission&limit=0")
    print("GET", url)
    recs = json.loads(_get(url))["records"]
    df = pd.DataFrame(recs)
    df["utc"] = pd.to_datetime(df["Minutes5UTC"], utc=True)
    piv = df.pivot_table(index="utc", columns="PriceArea", values="CO2Emission").resample("1h").mean()
    piv.index.name = "utc"
    piv.to_csv(out, float_format="%.1f")
    return out


def main():
    cfg = load_cfg()
    year = cfg["study"]["year"]
    DATA.mkdir(parents=True, exist_ok=True)
    for r in cfg["regions"]:
        fetch_energy_charts(r["energy_charts_country"], year)
    fetch_neso(year)
    fetch_energinet(year)
    stamp = DATA / "ACCESS_LOG.txt"
    with open(stamp, "a", encoding="utf8") as f:
        f.write(f"fetch_data.py run completed {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")


if __name__ == "__main__":
    main()
