import React, { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { Area, AreaChart, CartesianGrid, Line, ReferenceLine, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from "recharts";

async function api(path, opts = {}) {
  const res = await fetch(`/api/c3${path}`, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`);
  return data;
}
const pin = (cls, txt) => L.divIcon({ className: `pin ${cls}`, html: `<span>${txt}</span>`, iconSize: [30, 30], iconAnchor: [15, 15] });
const QUICK = [["Colombo", "Kandy"], ["Colombo", "Nuwara Eliya"], ["Colombo", "Galle"], ["Colombo", "Jaffna"]];

function ClickSetter({ onPick }) { useMapEvents({ click: (e) => onPick(e.latlng) }); return null; }
function Fit({ route }) {
  const map = useMap();
  useEffect(() => { if (route) map.fitBounds(route.geometry, { padding: [60, 60] }); }, [route]);
  return null;
}

export default function App() {
  const [places, setPlaces] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [chargers, setChargers] = useState(null);
  const [from, setFrom] = useState({ name: "Colombo" });
  const [to, setTo] = useState({ name: "Nuwara Eliya" });
  const [vid, setVid] = useState(0);
  const [soc, setSoc] = useState(90);
  const [reserve, setReserve] = useState(15);
  const [res, setRes] = useState(null);
  const [sel, setSel] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pickMode, setPickMode] = useState(null);

  useEffect(() => {
    api("/places").then(setPlaces); api("/vehicles").then((v) => { setVehicles(v); setVid(v[0]?.id ?? 0); }); api("/chargers").then(setChargers);
  }, []);
  const byName = useMemo(() => Object.fromEntries(places.map((p) => [p.name.toLowerCase(), p])), [places]);
  const resolve = (pt) => pt.lat ? pt : byName[(pt.name || "").toLowerCase()];

  const go = async (a = from, b = to) => {
    const o = resolve(a), d = resolve(b);
    if (!o || !d) { setErr("Pick a town from the list or click on the map"); return; }
    setBusy(true); setErr("");
    try {
      const r = await api("/plan", { method: "POST", body: JSON.stringify({ origin: { lat: o.lat, lon: o.lon, name: o.name }, destination: { lat: d.lat, lon: d.lon, name: d.name }, vehicle_id: Number(vid), start_soc_pct: soc, reserve_pct: reserve }) });
      setRes(r); setSel(0);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const route = res?.routes[sel];
  const veh = vehicles.find((v) => v.id === Number(vid));

  return (
    <div className="app">
      <MapContainer center={[7.6, 80.7]} zoom={8} className="map" zoomControl={false} preferCanvas>
        <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png" attribution='&copy; OpenStreetMap &copy; CARTO' />
        <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png" />
        {pickMode && <ClickSetter onPick={(ll) => { const p = { name: `${ll.lat.toFixed(3)}, ${ll.lng.toFixed(3)}`, lat: ll.lat, lon: ll.lng }; pickMode === "from" ? setFrom(p) : setTo(p); setPickMode(null); }} />}
        {chargers?.features.map((f, i) => <CircleMarker key={i} center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]} radius={3} pathOptions={{ color: "#22d3ee", weight: 1, fillOpacity: 0.7 }}>
          <Tooltip>{f.properties.name || f.properties.operator || "Charger"} {f.properties.max_kw ? `· ${f.properties.max_kw} kW` : ""}</Tooltip></CircleMarker>)}
        {res?.routes.map((r, i) => i !== sel && <Polyline key={i} positions={r.geometry} pathOptions={{ color: "#6d5bd0", weight: 4, opacity: 0.55 }} eventHandlers={{ click: () => setSel(i) }} />)}
        {route && <><Polyline positions={route.geometry} pathOptions={{ color: "#ff7a1a", weight: 11, opacity: 0.25 }} />
          <Polyline positions={route.geometry} pathOptions={{ color: "#ffb347", weight: 4 }} /><Fit route={route} />
          <Marker position={route.geometry[0]} icon={pin("start", "A")} /><Marker position={route.geometry.at(-1)} icon={pin("end", "B")} />
          {route.stop?.stops?.map((s, k) => <Marker key={k} position={[s.lat, s.lon]} icon={pin("bolt", `⚡${route.stop.stops.length > 1 ? k + 1 : ""}`)}>
            <Popup><b>{s.name || s.operator || "Charging station"}</b><br />km {Math.round(s.route_km)} · {s.kw} kW ({s.compatible === "yes" ? "connector OK" : "connector unknown"})<br />
              Arrive {s.soc_at_arrival}% → charge to {s.charge_to_pct}% ({s.charge_min} min)</Popup></Marker>)}</>}
      </MapContainer>

      <div className="glass search">
        <div className="title"><span className="logo">◢◤</span> TerrainRoute <small>C3 · hills · battery · stops</small></div>
        <Field label="From" value={from.name} onChange={(v) => setFrom({ name: v })} places={places} onPick={() => setPickMode("from")} active={pickMode === "from"} />
        <Field label="To" value={to.name} onChange={(v) => setTo({ name: v })} places={places} onPick={() => setPickMode("to")} active={pickMode === "to"} />
        <div className="quick">{QUICK.map(([a, b]) => <button key={b} onClick={() => { setFrom({ name: a }); setTo({ name: b }); go({ name: a }, { name: b }); }}>{b}</button>)}</div>
        <label className="lbl">Vehicle<select value={vid} onChange={(e) => setVid(e.target.value)}>{vehicles.map((v) => <option key={v.id} value={v.id}>{v.name} · {v.usable_kwh} kWh</option>)}</select></label>
        {veh && <div className="vmeta">{veh.connector} · {veh.params_source}</div>}
        <div className="sl"><span>Battery now</span><b>{soc}%</b></div>
        <input type="range" min="20" max="100" value={soc} onChange={(e) => setSoc(+e.target.value)} />
        <div className="sl"><span>Keep in reserve</span><b>{reserve}%</b></div>
        <input type="range" min="5" max="30" value={reserve} onChange={(e) => setReserve(+e.target.value)} />
        <button className="go" onClick={() => go()} disabled={busy}>{busy ? "Calculating routes…" : "Find routes"}</button>
        {err && <div className="err">{err}</div>}
        {pickMode && <div className="hint">Click on the map to set {pickMode === "from" ? "the start" : "the destination"}</div>}
      </div>

      {res && (
        <div className="sheet">
          <div className="cards">
            {res.routes.map((r, i) => (
              <button key={i} className={`card ${i === sel ? "on" : ""}`} onClick={() => setSel(i)}>
                <div className="tags">{r.recommended && <span className="tag best">Recommended</span>}{r.labels.map((l) => <span key={l} className="tag">{l}</span>)}</div>
                <div className="big">{Math.floor(r.total_min / 60)}h {r.total_min % 60}m <small>{r.distance_km} km</small></div>
                <div className="row"><span>⚡ {(r.energy_kwh.hybrid ?? r.energy_kwh.physics).toFixed(1)} kWh</span><span>▲ {r.climb_m} m</span><span>🔋 {r.arrival_soc_pct}%</span></div>
                <div className={`stopline ${!r.feasible ? "bad" : r.n_stops ? "warn" : "ok"}`}>
                  {!r.feasible ? `Not reachable with known chargers${r.n_stops ? ` (after ${r.n_stops} stop${r.n_stops > 1 ? "s" : ""})` : ""}`
                    : r.n_stops ? `${r.n_stops} stop${r.n_stops > 1 ? "s" : ""} · ${r.charge_min} min charging` : "No charging stop needed"}</div>
              </button>))}
          </div>
          {route && (
            <div className="detail">
              <div className="chart">
                <div className="ct">Elevation & battery along the route <span>(ambient {res.ambient_c}°C · {res.energy_model} model)</span></div>
                <ResponsiveContainer width="100%" height={170}>
                  <AreaChart data={route.profile} margin={{ left: -10, right: 8, top: 6 }}>
                    <defs><linearGradient id="el" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7c5cff" stopOpacity={0.7} /><stop offset="100%" stopColor="#7c5cff" stopOpacity={0.05} /></linearGradient></defs>
                    <CartesianGrid stroke="#25213f" vertical={false} />
                    <XAxis dataKey="km" tick={{ fill: "#8f88b8", fontSize: 10 }} unit=" km" type="number" domain={[0, "dataMax"]} />
                    <YAxis yAxisId="z" tick={{ fill: "#8f88b8", fontSize: 10 }} unit=" m" />
                    <YAxis yAxisId="s" orientation="right" domain={[-20, 100]} tick={{ fill: "#ffb347", fontSize: 10 }} unit="%" />
                    <RTooltip contentStyle={{ background: "#16132e", border: "1px solid #332d5c", color: "#fff" }} />
                    <Area yAxisId="z" dataKey="elev" name="elevation (m)" stroke="#9b85ff" fill="url(#el)" />
                    <Line yAxisId="s" dataKey="soc" name="battery % (hybrid)" stroke="#ffb347" dot={false} strokeWidth={2.5} />
                    <Line yAxisId="s" dataKey="soc_constant" name="battery % (constant kWh/km)" stroke="#8f88b8" dot={false} strokeDasharray="4 3" />
                    <ReferenceLine yAxisId="s" y={reserve} stroke="#ff4d6d" strokeDasharray="5 4" label={{ value: "reserve", fill: "#ff4d6d", fontSize: 10 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="side">
                <div className="ct">Energy estimate</div>
                {Object.entries(route.energy_kwh).map(([k, v]) => <div className="erow" key={k}><span>{k === "hybrid" ? "Hybrid (proposed)" : k === "physics" ? "Physics only" : "Constant kWh/km"}</span><b>{v.toFixed(1)} kWh</b></div>)}
                {route.stop?.stops?.length > 0 && <>
                  <div className="ct">Charging stops</div>
                  {route.stop.stops.map((s, k) => <div className="erow" key={k}><span>⚡{k + 1} km {Math.round(s.route_km)} · {s.soc_at_arrival}%→{s.charge_to_pct}%</span><b>{s.charge_min} min</b></div>)}
                  {route.stop.nearest_first && <div className="erow"><span>Nearest charger (baseline)</span><b>km {Math.round(route.stop.nearest_first.route_km)}</b></div>}</>}
                {!route.feasible && <div className="warnbox">The battery would fall below the {reserve}% reserve and no known charger lies within 3 km of the route.
                  The OSM charger list is incomplete – operator data (Volt Charge, ChargeNET) is needed.</div>}
                <div className="notes">{res.notes.map((n) => <p key={n}>{n}</p>)}</div>
              </div>
            </div>)}
        </div>)}
    </div>
  );
}

function Field({ label, value, onChange, places, onPick, active }) {
  return (
    <div className="field"><span>{label}</span>
      <input list="places" value={value} onChange={(e) => onChange(e.target.value)} placeholder="Town…" />
      <datalist id="places">{places.map((p) => <option key={p.name} value={p.name} />)}</datalist>
      <button className={`pick ${active ? "on" : ""}`} onClick={onPick} title="Pick on map">⌖</button>
    </div>
  );
}
