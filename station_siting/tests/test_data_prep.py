"""Tests for C2 data preparation (pure functions, no raw files needed)."""

import geopandas as gpd
import pytest
import shapely

from station_siting.data_prep import osm_layers, other_layers, power


def test_ceb_line_existing_capacity_only():
    r = power.parse_ceb_line("Kelanitissa 120 17.8 10.4 22.1 13.7 23.6 14.6 48.9 30.3 69.5 43.1 27.2 16.9 28.6 17.7 "
                             "29.6 18.4 46.1 28.6 46.8 29.0 47.5 29.5 49.2 30.6 51.6 32.0 54.0 33.5")
    assert r["name"] == "Kelanitissa" and r["existing_mva"] == "120" and r["expansion_mva"] is None
    assert r["load"][2012] == (17.8, 10.4) and r["load"][2025] == (54.0, 33.5)


def test_ceb_line_new_substation_and_name_with_digit():
    r = power.parse_ceb_line("Port City 1 90 2017 25.0 8.2 25.0 8.2 37.5 12.3 50.0 16.4 62.5 20.5 75.0 24.7 "
                             "75.0 24.7 75.0 24.7 75.0 24.7")
    assert r["name"] == "Port City 1" and r["existing_mva"] is None and r["expansion_mva"] == "90"
    assert min(r["load"]) == 2017 and power.capacity_in(r, 2016) is None and power.capacity_in(r, 2025) == 90


def test_ceb_line_region_prefix_and_staged_expansion():
    r = power.parse_ceb_line("WPS II Kelaniya 31.5 63/94.5 2015/2023 " + "1.0 0.5 " * 14)
    assert r["name"] == "Kelaniya"
    assert power.capacity_in(r, 2014) == 31.5 and power.capacity_in(r, 2016) == 63 and power.capacity_in(r, 2025) == 94.5


def test_ceb_non_data_lines_ignored():
    assert power.parse_ceb_line("Total Demand - Night Peak 2162.2 901.5") is None
    assert power.parse_ceb_line("Region Prov. Grid Substation") is None


def test_canonical_names_match_spelling_variants():
    c = power.canonical
    assert c("Kollonnawa (Outdoor)") == c("Kolonnawa")
    assert c("Sub A (Havelock Town)") == c("Havelock Town")
    assert c("Athurugiriya") == c("Aturugiriya Grid Substation")
    assert c("Sri Jayawardanapura") != ""


def test_spelling_variant_with_final_vowel():
    assert power.canonical("Sub K (Wellawatta)") == power.canonical("Wellawatte")


def test_ambiguous_place_name_not_guessed():
    import pandas as pd
    ceb = pd.DataFrame({"ceb_name": ["Madampe", "Kesbewa"]})
    places = gpd.GeoDataFrame({"name": ["Madampe", "Madampe", "Kesbewa"]},
                              geometry=[shapely.Point(79.84, 7.50), shapely.Point(80.59, 6.53), shapely.Point(79.94, 6.80)],
                              crs="EPSG:4326")
    colombo = shapely.Point(79.86, 6.93).buffer(0.1)
    out = power.match_names(ceb, places, fuzzy_cutoff=None, prefer_near=colombo, near_km=30).set_index("ceb_name")
    assert out.loc["Madampe", "match"] == "ambiguous" and out.loc["Madampe", "geometry"] is None
    assert out.loc["Kesbewa", "match"] == "exact"


def test_maxspeed_parsing():
    assert osm_layers.parse_maxspeed("60") == 60
    assert osm_layers.parse_maxspeed("40 mph") == pytest.approx(64.4)
    assert osm_layers.parse_maxspeed("signals") is None and osm_layers.parse_maxspeed(None) is None


def test_poi_classification():
    assert osm_layers.classify_poi({"amenity": "fuel"}) == ("fuel_station", "candidate")
    assert osm_layers.classify_poi({"office": "government"}) == ("office", "attractor")
    assert osm_layers.classify_poi({"amenity": "bench"}) is None


def test_dedupe_points_same_category_within_30m():
    pts = [shapely.Point(79.8600, 6.9000), shapely.Point(79.86015, 6.9000),  # ~17 m apart
           shapely.Point(79.8700, 6.9000)]
    g = gpd.GeoDataFrame({"category": ["fuel_station"] * 3}, geometry=pts, crs="EPSG:4326")
    out, n = osm_layers.dedupe_points(g, "category")
    assert n == 1 and len(out) == 2


def test_kw_parsing():
    assert other_layers.parse_kw("22 kW") == 22
    assert other_layers.parse_kw("7.4kW;50 kW") == 50
    assert other_layers.parse_kw(None) is None
