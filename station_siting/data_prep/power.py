"""Grid substations: OSM locations + CEB capacity / forecast load (LTTDP 2013-2022, Tables 3.1/3.2).

CEB numbers are a 2013 PLANNING forecast (to 2025), not today's measured loading -> every value
derived from them is labelled `source = "CEB LTTDP 2013-2022"` and must be called an assumption
in results. Current capacity data has been requested via the supervisor.
"""

from __future__ import annotations

import difflib
import json
import math
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pdfplumber
import shapely

CRS_STORE = "EPSG:4326"
YEARS = list(range(2012, 2026))  # table columns: 2012 actual, 2013 ... 2025 forecast
REGION_TOKENS = {"CC", "NCP", "WPN", "WPS", "SBP", "UP", "SP", "NWP", "CP", "EP", "NP", "SAB", "UVA",
                 "I", "II", "III", "IV", "1", "2", "3", "4", "5", "6"}
NUM = re.compile(r"^\*?\d+(\.\d+)?(/\d+(\.\d+)?)*$")
YEAR = re.compile(r"^20[1-3]\d(/20[1-3]\d)*$")


def parse_ceb_line(line: str) -> dict | None:
    """Parse one substation row of CEB Table 3.1/3.2. Returns None for non-data lines."""
    toks = line.split()
    while toks and toks[0] in REGION_TOKENS:
        toks = toks[1:]
    i = next((k for k, t in enumerate(toks) if NUM.match(t)), None)
    if not i:
        return None
    name, vals = " ".join(toks[:i]), toks[i:]
    if re.match(r"(?i)^(total|region|capacity|existing|long term|table)", name):
        return None
    ypos = next((k for k in range(min(3, len(vals))) if YEAR.match(vals[k])), None)
    if ypos == 2 and re.fullmatch(r"\d", vals[0]):  # 'Port City 1 90 2017 ...' -> digit belongs to name
        name, vals, ypos = f"{name} {vals[0]}", vals[1:], 1
    if ypos is None:
        existing, expansion, exp_year, rest = vals[0], None, None, vals[1:]
    elif ypos == 1:
        existing, expansion, exp_year, rest = None, vals[0], vals[1], vals[2:]
    elif ypos == 2:
        existing, expansion, exp_year, rest = vals[0], vals[1], vals[2], vals[3:]
    else:
        return None
    try:
        nums = [float(t.strip("*")) for t in rest]
    except ValueError:
        return None
    if not nums or len(nums) % 2 or len(nums) // 2 > len(YEARS):
        return None
    pairs = list(zip(nums[0::2], nums[1::2]))
    years = YEARS[-len(pairs):]
    return {"name": name, "existing_mva": existing, "expansion_mva": expansion, "expansion_year": exp_year,
            "load": {y: p for y, p in zip(years, pairs)}}


def capacity_in(row: dict, year: int) -> float | None:
    """Installed MVA in `year`: last expansion step done by that year, else existing."""
    cap = float(row["existing_mva"].split("/")[-1]) if row["existing_mva"] else None
    if row["expansion_mva"] and row["expansion_year"]:
        for mva, yr in zip(row["expansion_mva"].split("/"), row["expansion_year"].split("/")):
            if int(yr) <= year:
                cap = float(mva)
    return cap


def read_ceb_tables(pdf_path: Path) -> pd.DataFrame:
    """Night-peak (Table 3.1) and day-peak (Table 3.2) grid substation forecasts, one row per GSS."""
    rows = {"night": {}, "day": {}}
    table = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[20:45]:
            for line in (page.extract_text() or "").splitlines():
                if "Table 3.1" in line:
                    table = "night"
                elif "Table 3.2" in line:
                    table = "day"
                elif line.startswith("Total Demand"):
                    table = None if table == "day" else table
                    continue
                if table:
                    r = parse_ceb_line(line)
                    if r:
                        rows[table].setdefault(r["name"], r)
    out = []
    for name, n in rows["night"].items():
        d = rows["day"].get(name)
        rec = {"ceb_name": name, "existing_mva": n["existing_mva"], "expansion_mva": n["expansion_mva"],
               "expansion_year": n["expansion_year"], "capacity_2025_mva": capacity_in(n, 2025)}
        for tag, r in (("night", n), ("day", d)):
            for y in (2012, 2020, 2025):
                p = r["load"].get(y) if r else None
                rec[f"{tag}_{y}_mw"] = p[0] if p else None
                rec[f"{tag}_{y}_mva"] = round(math.hypot(*p), 1) if p else None
        peak = max(v for v in (rec["night_2025_mva"], rec["day_2025_mva"]) if v is not None) if (
            rec["night_2025_mva"] or rec["day_2025_mva"]) else None
        rec["peak_2025_mva"] = peak
        cap = rec["capacity_2025_mva"]
        rec["spare_2025_mva"] = round(cap - peak, 1) if cap and peak else None
        rec["utilisation_2025"] = round(peak / cap, 3) if cap and peak else None
        out.append(rec)
    df = pd.DataFrame(out)
    df["source"] = "CEB LTTDP 2013-2022 (forecast)"
    return df


def canonical(name: str | None) -> str:
    """Normalise substation / place names for matching ('Sub A (Havelock Town)' -> 'havelocktown')."""
    if not name:
        return ""
    s = name.lower()
    par = re.search(r"\(([^)]*)\)", s)
    if par and not re.search(r"indoor|outdoor", par.group(1)):
        s = par.group(1)
    s = re.sub(r"\((indoor|outdoor)\)", "", s)
    s = re.sub(r"\b(grid|sub ?station|substation|gss|switch ?yard|primary|power|station|sub|\d+/?\d*\s*kv)\b", " ", s)
    s = re.sub(r"[^a-z]", "", s)
    for a, b in (("th", "t"), ("ll", "l"), ("nn", "n"), ("aa", "a"), ("ee", "i"), ("oo", "u")):
        s = s.replace(a, b)
    return re.sub(r"[aeiou]+$", "", s)  # Wellawatta / Wellawatte -> same key


def match_names(ceb: pd.DataFrame, candidates: gpd.GeoDataFrame, fuzzy_cutoff: float | None = 0.85,
                prefer_near=None, near_km: float = 30) -> pd.DataFrame:
    """Give each CEB substation a location by name.

    1. exact canonical-name match; 2. (optional) close fuzzy match.
    If several candidates share the name (e.g. two villages called Madampe) the one within `near_km`
    of `prefer_near` is used; otherwise the name is 'ambiguous' and left without location (no guessing).
    """
    cand = candidates.assign(key=candidates["name"].map(canonical))
    cand = cand[cand["key"] != ""]
    groups = cand.groupby("key").groups
    near_m = None
    if prefer_near is not None:
        near_m = gpd.GeoSeries([prefer_near], crs=CRS_STORE).to_crs(5235).iloc[0]
    res = []
    for _, r in ceb.iterrows():
        k = canonical(r["ceb_name"])
        how = "exact" if k in groups else None
        if how is None and fuzzy_cutoff:
            close = difflib.get_close_matches(k, list(groups), n=1, cutoff=fuzzy_cutoff)
            if close:
                k, how = close[0], "fuzzy"
        rec = {"ceb_name": r["ceb_name"], "matched_name": None, "match": None, "geometry": None}
        if how:
            hits = cand.loc[groups[k]]
            if len(hits) > 1 and near_m is not None:
                d = hits.to_crs(5235).distance(near_m) / 1000
                hits = hits[d <= near_km]
            hm = hits.geometry.to_crs(5235)
            if len(hits) == 1 or (len(hits) > 1 and hm.distance(hm.iloc[0]).max() < 2000):  # same spot mapped twice
                h = hits.iloc[0]
                rec.update(matched_name=h["name"], match=how, geometry=h.geometry)
            else:
                rec.update(match="ambiguous")
        res.append(rec)
    return pd.DataFrame(res)


def osm_substations(json_path: Path) -> gpd.GeoDataFrame:
    """OSM power=substation (Overpass extract): clean voltage, type, name."""
    el = json.loads(json_path.read_text(encoding="utf-8"))["elements"]
    rows = []
    for e in el:
        t = e.get("tags", {})
        if t.get("power") != "substation":
            continue
        lon, lat = (e["lon"], e["lat"]) if "lon" in e else (e["center"]["lon"], e["center"]["lat"])
        volts = [float(v) / 1000 for v in re.findall(r"\d+", t.get("voltage", "")) if float(v) >= 1000]
        rows.append({"osm_id": f"{e['type'][0]}{e['id']}", "name": t.get("name"), "operator": t.get("operator"),
                     "substation_type": t.get("substation"), "voltage_kv_max": max(volts) if volts else None,
                     "voltage_raw": t.get("voltage"), "geometry": shapely.Point(lon, lat)})
    g = gpd.GeoDataFrame(rows, crs=CRS_STORE)
    g["is_grid_substation"] = (g["voltage_kv_max"] >= 132) | g["name"].fillna("").str.contains("(?i)grid")
    return g
