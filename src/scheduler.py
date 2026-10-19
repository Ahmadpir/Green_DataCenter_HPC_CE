"""Greedy online carbon- and PUE-aware scheduler for deferrable CE cloud workloads.

Each hour, every workload class releases an aggregate job (IT energy e, duration d, window W).
The scheduler ranks (region, start) options by *forecast* emissions
    sum_h  CI_hat[h, r] * PUE[r] * (e/d) * (1 + eps * [r != home])
and fills them in that order subject to a per-region hourly headroom for flexible load,
splitting a job across options when needed. Emissions are evaluated with the *actual* intensity.
"""
import numpy as np

STRATEGIES = ["baseline", "temporal", "spatial", "spatiotemporal", "pue_blind", "lowest_pue"]


def arrivals(cfg, index, profile_override=None):
    """Hourly IT energy (MWh) released by each workload class."""
    avg_mw = cfg["study"]["fleet_avg_it_mw"]
    local_hour = index.tz_convert("Europe/Berlin").hour.values
    out = {}
    for k, w in cfg["workloads"].items():
        name = w["profile"] if profile_override in (None, "as_configured") else profile_override
        p = np.array(cfg["profiles"][name], dtype=float)
        p = p / p.mean()
        out[k] = w["share"] * avg_mw * p[local_hour]
    return out


def persistence_forecast(c, t, horizon):
    """Forecast of c[t:t+horizon] made at hour t: the current hour is observed, later hours take the
    value of the same clock hour on the most recent observed day (day-ahead persistence)."""
    k = np.arange(horizon)
    src = t + k - 24 * np.ceil(k / 24).astype(int)
    src = np.clip(src, 0, len(c) - 1)
    return c[src]


_OFF = {}


def _offsets(horizon):
    if horizon not in _OFF:
        k = np.arange(horizon)
        _OFF[horizon] = k - 24 * np.ceil(k / 24).astype(int)
    return _OFF[horizon].copy()


def simulate(ci, pue, home, cfg, strategy="spatiotemporal", forecast="persistence",
             eps=None, headroom=None, window_scale=1.0, profile_override=None, exclude=(), tie="split"):
    """Return dict class -> metrics (emissions in tCO2e, energy in MWh, shares, delay)."""
    eps = cfg["study"]["migration_overhead"] if eps is None else eps
    headroom = cfg["study"]["headroom_factor"] if headroom is None else headroom
    ci_arr = ci.values.astype(float)                       # T x R, gCO2e/kWh
    T, R = ci_arr.shape
    pue = np.asarray(pue, dtype=float)
    regions = list(ci.columns)
    h_idx = regions.index(home)
    true_cost = ci_arr * pue                                # gCO2e per kWh of IT energy
    if strategy == "pue_blind":
        plan_cost = ci_arr.copy()                           # planner ignores PUE
    elif strategy == "lowest_pue":
        plan_cost = np.tile(pue, (T, 1))                    # planner ignores carbon, sees PUE only
    else:
        plan_cost = true_cost.copy()
    for code in exclude:                                    # regions unavailable for shifted work
        if code != home:
            plan_cost[:, regions.index(code)] = np.inf
    lp_sites = []
    if strategy == "lowest_pue":
        avail = [i for i, c in enumerate(regions) if c not in exclude or c == home]
        pmin = min(pue[i] for i in avail)
        tied = [i for i in avail if abs(pue[i] - pmin) < 1e-9]
        lp_sites = tied if tie == "split" else [regions.index(tie)]
        if tie != "split" and lp_sites[0] not in tied:
            raise ValueError(f"{tie} is not among the lowest-PUE sites")
    arr = arrivals(cfg, ci.index, profile_override=profile_override)
    wl = cfg["workloads"]
    flex_avg = sum(arr[k].mean() for k in wl if wl[k]["window_h"] > 0 or wl[k]["spatial"])
    cap = headroom * flex_avg                               # MW of flexible load per region-hour
    used = np.zeros((T, R))
    order = sorted(wl, key=lambda k: wl[k]["window_h"])     # tightest deadline first
    acc = {k: dict(em=0.0, en=0.0, moved=0.0, delay=0.0, overflow=0.0, reg=np.zeros(R)) for k in order}
    use_t = strategy in ("temporal", "spatiotemporal", "pue_blind")
    use_s = strategy in ("spatial", "spatiotemporal", "pue_blind", "lowest_pue")
    for t in range(T):
        for k in order:
            w = wl[k]
            e = arr[k][t]
            d = int(w["duration_h"])
            W = int(round(w["window_h"] * window_scale)) if w["window_h"] > 0 else 0
            flex_t = use_t and W >= d and W > 0
            flex_s = use_s and w["spatial"]
            if strategy == "baseline" or not (flex_t or flex_s):
                acc[k]["em"] += (e / d) * true_cost[t:min(t + d, T), h_idx].sum()  # MWh x g/kWh = kg
                acc[k]["en"] += e
                continue
            if strategy == "lowest_pue":
                # Static PUE-only site choice, run now. Ties in PUE are broken explicitly:
                # tie="split" shares the job equally among all tied sites; tie="<code>" picks that site.
                for r in lp_sites:
                    part = e / len(lp_sites)
                    m = 1.0 if r == h_idx else 1.0 + eps
                    acc[k]["em"] += (part / d) * m * true_cost[t:min(t + d, T), r].sum()
                    acc[k]["en"] += part * m
                    if r != h_idx:
                        acc[k]["moved"] += part
                continue
            n_start = (W - d + 1) if flex_t else 1
            n_start = max(1, min(n_start, T - d - t + 1))
            horizon = n_start + d - 1
            cols = slice(None) if flex_s else slice(h_idx, h_idx + 1)
            if forecast == "oracle" or strategy == "lowest_pue":
                f = plan_cost[t:t + horizon, cols]
            else:
                src = t + _offsets(horizon)
                np.clip(src, 0, T - 1, out=src)
                f = plan_cost[src, cols]
            if f.shape[0] < horizon:                          # end of the year
                f = np.vstack([f, np.repeat(f[-1:], horizon - f.shape[0], 0)])
            cs = np.cumsum(f, axis=0)
            win = cs[d - 1:d - 1 + n_start].copy()
            win[1:] -= cs[0:n_start - 1]                      # n_start x R' (sum over duration)
            reg_ids = np.arange(R) if flex_s else np.array([h_idx])
            mult = np.where(reg_ids == h_idx, 1.0, 1.0 + eps)
            score = win * mult
            remaining = e
            Rp = len(reg_ids)
            for fi in np.argsort(score, axis=None, kind="stable"):  # ties: earliest start, then config order
                if not np.isfinite(score.flat[fi]):
                    break
                s_off, j = divmod(int(fi), Rp)
                r = reg_ids[j]
                s = t + s_off
                s_end = min(s + d, T)
                free = cap - used[s:s_end, r].max()
                if free <= 1e-12:
                    continue
                part = min(remaining, free * d)
                used[s:s_end, r] += part / d
                acc[k]["em"] += (part / d) * mult[j] * true_cost[s:s_end, r].sum()
                acc[k]["en"] += part * mult[j]
                acc[k]["delay"] += part * s_off
                acc[k]["reg"][r] += part
                if r != h_idx:
                    acc[k]["moved"] += part
                remaining -= part
                if remaining <= 1e-12:
                    break
            if remaining > 1e-12:                             # no headroom anywhere: run at home now
                acc[k]["em"] += (remaining / d) * true_cost[t:min(t + d, T), h_idx].sum()
                acc[k]["en"] += remaining
                acc[k]["overflow"] += remaining
    res = {}
    for k, a in acc.items():
        it = arr[k].sum()
        res[k] = dict(emissions_t=a["em"] / 1000.0, energy_mwh=a["en"], it_mwh=it,
                      moved_share=a["moved"] / it, mean_delay_h=a["delay"] / it,
                      overflow_share=a["overflow"] / it,
                      region_share={c: float(a["reg"][i] / it) for i, c in enumerate(regions)})
    return res


def savings(base, other, classes=None):
    classes = classes or list(base)
    b = sum(base[k]["emissions_t"] for k in classes)
    o = sum(other[k]["emissions_t"] for k in classes)
    return 100.0 * (b - o) / b
