import React, { useEffect, useMemo, useState } from "react";
import { CircleMarker, GeoJSON, MapContainer, Marker, Popup, TileLayer, Tooltip } from "react-leaflet";
import L from "leaflet";
import { api } from "./api.js";

const MODE_LABEL = { temporal: "All week (time-weighted)", static: "Static – population only", weekday_peak: "Weekday peak 18:30–22:30",
  weekday_offpeak: "Weekday off-peak", weekend_peak: "Weekend peak", weekend_offpeak: "Weekend off-peak" };
const CRIT_LABEL = { demand: "Demand", grid: "Grid capacity", road: "Road access", land: "Land", competition: "Distance to chargers" };
const amber = (v) => `hsl(${42 - v * 42}, 95%, ${62 - v * 22}%)`;
const triangle = L.divIcon({ className: "gss-icon", html: "▲", iconSize: [16, 16], iconAnchor: [8, 8] });
const siteIcon = (n) => L.divIcon({ className: "site-icon", html: `<span>${n}</span>`, iconSize: [26, 26], iconAnchor: [13, 13] });
const fmt = (v, d = 1) => (v === null || v === undefined ? "–" : Number(v).toFixed(d));

export default function App() {
  const [meta, setMeta] = useState(null);
  const [mode, setMode] = useState("temporal");
  const [hex, setHex] = useState(null);
  const [gss, setGss] = useState(null);
  const [chg, setChg] = useState(null);
  const [p, setP] = useState(null);
  const [judg, setJudg] = useState(null);
  const [ahp, setAhp] = useState(null);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [runs, setRuns] = useState([]);
  const [layers, setLayers] = useState({ hex: true, gss: true, chg: true });

  useEffect(() => {
    api("/meta").then((m) => { setMeta(m); setP({ ...m.defaults, label: "My scenario" }); setJudg(m.default_judgements); });
    api("/substations").then(setGss); api("/chargers").then(setChg); api("/runs").then(setRuns);
  }, []);
  useEffect(() => { setHex(null); api("/hexagons", { query: { mode } }).then(setHex); }, [mode]);
  useEffect(() => { if (judg) api("/ahp", { method: "POST", body: { judgements: judg } }).then(setAhp).catch((e) => setErr(e.message)); }, [judg]);

  const run = async () => {
    setBusy(true); setErr("");
    try { const r = await api("/optimize", { method: "POST", body: { ...p, demand_mode: mode, judgements: judg } }); setRes(r); api("/runs").then(setRuns); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const hexStyle = useMemo(() => (f) => ({ fillColor: amber(f.properties.demand), fillOpacity: 0.15 + 0.6 * f.properties.demand, weight: 0.3, color: "#111827" }), []);
  if (!meta || !p) return <div className="loading">Loading planner…</div>;
  const set = (k, num = true) => (e) => setP({ ...p, [k]: e.target.type === "checkbox" ? e.target.checked : num ? Number(e.target.value) : e.target.value });

  return (
    <div className="layout">
      <aside className="side">
        <div className="logo"><b>GRIDSITE</b> PLANNER<small>C2 · Colombo District · {meta.counts.candidates} candidate sites</small></div>

        <section><h4>Demand period</h4>
          <select value={mode} onChange={(e) => setMode(e.target.value)}>{meta.modes.map((m) => <option key={m} value={m}>{MODE_LABEL[m]}</option>)}</select>
        </section>

        <section><h4>Network</h4>
          <Range label="New stations" v={p.n_sites} min={3} max={40} step={1} on={set("n_sites")} unit="" />
          <Range label="Service radius" v={p.radius_m} min={1000} max={6000} step={500} on={set("radius_m")} unit=" m" />
          <Range label="Power per station" v={p.station_mw} min={0.25} max={6} step={0.25} on={set("station_mw")} unit=" MW" />
          <Range label="EV share of spare grid" v={p.ev_share} min={0.05} max={1} step={0.05} on={set("ev_share")} unit="" pct />
          <label className="toggle"><input type="checkbox" checked={p.grid_constraint} onChange={set("grid_constraint")} /><span />Substation capacity limit</label>
        </section>

        <section><h4>AHP criteria weights <span className={`cr ${ahp?.consistent ? "ok" : "bad"}`}>CR {fmt(ahp?.CR, 3)}</span></h4>
          {ahp && meta.criteria.map((c) => (
            <div className="wbar" key={c}><span>{CRIT_LABEL[c]}</span><div><i style={{ width: `${ahp.weights[c] * 100}%` }} /></div><b>{fmt(ahp.weights[c] * 100, 0)}%</b></div>
          ))}
          <details><summary>Pairwise judgements (expert input)</summary>
            {Object.entries(judg).map(([k, v]) => { const [a, b] = k.split("|"); return (
              <div className="pair" key={k}><span>{CRIT_LABEL[a]} vs {CRIT_LABEL[b]}</span>
                <select value={v} onChange={(e) => setJudg({ ...judg, [k]: Number(e.target.value) })}>
                  {[1 / 5, 1 / 4, 1 / 3, 1 / 2, 1, 2, 3, 4, 5, 6, 7].map((x) => <option key={x} value={x}>{x < 1 ? `1/${Math.round(1 / x)}` : x}</option>)}
                </select></div>); })}
            <p className="note">⚠ Placeholder values until the expert interviews. CR must stay below 0.10.</p>
          </details>
        </section>

        <input className="label" value={p.label} onChange={set("label", false)} />
        <button className="run" onClick={run} disabled={busy || !ahp?.consistent}>{busy ? "Optimising (MILP)…" : "Run optimisation ▸"}</button>
        {err && <div className="err">{err}</div>}

        {runs.length > 0 && <section><h4>Saved runs</h4>
          <table className="runs"><tbody>{runs.slice(0, 8).map((r) => <tr key={r.id}><td>#{r.id}</td><td>{r.label}</td><td>{r.coverage_pct}%</td>
            <td><a href={`/api/c2/runs/${r.id}/export?fmt=csv`}>csv</a> <a href={`/api/c2/runs/${r.id}/export?fmt=geojson`}>geo</a></td></tr>)}</tbody></table>
        </section>}
        <p className="foot">Substation capacity: CEB LTTDP 2013–2022 (2025 forecast). OSM chargers incomplete. Expressway corridor pending.</p>
      </aside>

      <main className="main">
        <div className="mapwrap">
          <MapContainer center={[6.87, 79.98]} zoom={11} className="map" preferCanvas>
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>' />
            <GeoJSON data={meta.district} style={{ color: "#38bdf8", weight: 2, fill: false, dashArray: "6 4" }} />
            {layers.hex && hex && <GeoJSON key={mode} data={hex} style={hexStyle}
              onEachFeature={(f, l) => l.bindTooltip(`demand ${(f.properties.demand * 100).toFixed(0)}% · pop ${f.properties.population}`)} />}
            {layers.chg && chg?.features.map((f, i) => (
              <CircleMarker key={i} center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]} radius={4} pathOptions={{ color: "#60a5fa", fillOpacity: 0.9 }}>
                <Tooltip>Existing charger: {f.properties.name || f.properties.operator || "unnamed"}</Tooltip></CircleMarker>))}
            {layers.gss && gss?.features.filter((f) => f.properties.serves_study_area).map((f, i) => (
              <Marker key={i} position={[f.geometry.coordinates[1], f.geometry.coordinates[0]]} icon={triangle}>
                <Popup><b>{f.properties.ceb_name}</b><br />Capacity 2025: {f.properties.capacity_2025_mva} MVA<br />Peak: {f.properties.peak_2025_mva} MVA<br />
                  Spare: {f.properties.spare_2025_mva} MVA<br />EV allowance: {fmt(res?.allowance_mw?.[f.properties.ceb_name], 2)} MW<br /><i>{f.properties.location_source}</i></Popup></Marker>))}
            {res?.sites.map((s) => (
              <Marker key={s.id} position={[s.lat, s.lon]} icon={siteIcon(s.rank)}>
                <Popup><b>#{s.rank} {s.name || s.category}</b><br />{s.category} · score {fmt(s.score, 3)}<br />Substation: {s.gss}<br />
                  Major road {fmt(s.dist_major_road_m, 0)} m · nearest charger {fmt(s.dist_charger_m, 0)} m</Popup></Marker>))}
          </MapContainer>
          <div className="layers">
            {[["hex", "Demand"], ["gss", "Substations"], ["chg", "Chargers"]].map(([k, l]) => (
              <label key={k}><input type="checkbox" checked={layers[k]} onChange={(e) => setLayers({ ...layers, [k]: e.target.checked })} />{l}</label>))}
            <div className="scale"><span>low</span><i /><span>high demand</span></div>
          </div>
        </div>

        <div className="panel">
          {!res ? <div className="placeholder">Set the parameters and press <b>Run optimisation</b>. The MCLP picks real buildable sites
            (fuel stations, malls, supermarkets, car parks, hotels) that cover the most EV demand within the radius – without overloading any substation.</div> : (
            <>
              <div className="kpis">
                <Kpi label="Demand covered" value={`${fmt(res.metrics.coverage_temporal_pct)}%`} accent />
                <Kpi label="Weekday peak covered" value={`${fmt(res.metrics.coverage_weekday_peak_pct)}%`} />
                <Kpi label="Overloaded substations" value={res.metrics.grid_violations} bad={res.metrics.grid_violations > 0} />
                <Kpi label="Sites placed" value={`${res.metrics.sites_placed}/${p.n_sites}`} />
                <Kpi label="Solver time" value={`${fmt(res.metrics.runtime_s)} s`} />
              </div>
              <div className="twocol">
                <table className="cmp"><thead><tr><th>Method</th><th>Coverage</th><th>Overloads</th><th>Overload MW</th></tr></thead><tbody>
                  <tr className="hl"><td>MCLP + grid (proposed)</td><td>{fmt(res.metrics.coverage_temporal_pct)}%</td><td>{res.metrics.grid_violations}</td><td>{fmt(res.metrics.grid_overload_mw, 2)}</td></tr>
                  {Object.entries(res.baselines).map(([k, b]) => <tr key={k}><td>{k}</td><td>{fmt(b.coverage_temporal_pct)}%</td><td className={b.grid_violations ? "red" : ""}>{b.grid_violations}</td><td>{fmt(b.grid_overload_mw, 2)}</td></tr>)}
                </tbody></table>
                <div className="sites"><table className="cmp"><thead><tr><th>#</th><th>Site</th><th>Type</th><th>Substation</th><th>Score</th></tr></thead><tbody>
                  {res.sites.map((s) => <tr key={s.id}><td>{s.rank}</td><td>{s.name || "–"}</td><td>{s.category}</td><td>{s.gss}</td><td>{fmt(s.score, 3)}</td></tr>)}
                </tbody></table></div>
              </div>
              <div className="exports">Run #{res.run_id}: <a href={`/api/c2/runs/${res.run_id}/export?fmt=csv`}>Download CSV</a> · <a href={`/api/c2/runs/${res.run_id}/export?fmt=geojson`}>Download GeoJSON</a></div>
            </>)}
        </div>
      </main>
    </div>
  );
}

function Range({ label, v, min, max, step, on, unit, pct }) {
  return <label className="range"><span>{label}</span><b>{pct ? `${Math.round(v * 100)}%` : `${v}${unit}`}</b>
    <input type="range" min={min} max={max} step={step} value={v} onChange={on} /></label>;
}
function Kpi({ label, value, accent, bad }) {
  return <div className={`kpi ${accent ? "accent" : ""} ${bad ? "bad" : ""}`}><span>{label}</span><b>{value}</b></div>;
}
