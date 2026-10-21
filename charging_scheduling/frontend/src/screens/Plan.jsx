import React, { useEffect, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";

const priceColor = (p) => (p >= 60 ? "#ff8a80" : p >= 30 ? "#ffd180" : "#a5d6a7");

export default function Plan({ vehicles, goToEV }) {
  const [vid, setVid] = useState("");
  const [soc, setSoc] = useState(30);
  const [target, setTarget] = useState(80);
  const [plug, setPlug] = useState("");
  const [dep, setDep] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (vehicles.length && !vid) setVid(String(vehicles[0].id)); }, [vehicles]);

  if (!vehicles.length) return (
    <div className="card empty"><h2>Add your EV first</h2><p>Pick your model and the app fills in battery size and charger power.</p>
      <button className="primary" onClick={goToEV}>Add my EV</button></div>
  );

  const run = async () => {
    setErr(""); setBusy(true);
    try {
      setRes(await api("/plan", { method: "POST", body: {
        vehicle_id: Number(vid), soc_now_pct: soc, soc_target_pct: target,
        plug_in_local: plug || null, departure_local: dep || null } }));
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  return (
    <>
      <div className="card">
        <h2>Tonight's charge</h2>
        <label>Vehicle<select value={vid} onChange={(e) => setVid(e.target.value)}>
          {vehicles.map((v) => <option key={v.id} value={v.id}>{v.nickname || `${v.model.make} ${v.model.model}`} · {v.model.usable_kwh} kWh</option>)}
        </select></label>
        <div className="slider"><span>Battery now</span><b>{soc}%</b></div>
        <input type="range" min="0" max="95" value={soc} onChange={(e) => setSoc(+e.target.value)} />
        <div className="slider"><span>Charge to</span><b>{target}%</b></div>
        <input type="range" min="20" max="100" step="5" value={target} onChange={(e) => setTarget(+e.target.value)} />
        <div className="row2">
          <label>Plug in<input type="time" value={plug} onChange={(e) => setPlug(e.target.value)} placeholder="now" /></label>
          <label>Leave at<input type="time" value={dep} onChange={(e) => setDep(e.target.value)} /></label>
        </div>
        <p className="hint">Leave times empty: plug-in = now, departure = learned from your routine.</p>
        {err && <div className="error">{err}</div>}
        <button className="primary" onClick={run} disabled={busy}>{busy ? "Planning…" : "Plan my charge"}</button>
      </div>

      {res && (
        <>
          <div className={`card result ${res.ready ? "ok" : "warn"}`}>
            <div className="big">{res.windows.map((w) => `${w.start}–${w.end}`).join(", ") || "No charging needed"}</div>
            <div className="sub">{res.ready ? `${res.soc_at_departure_pct}% ready by ${res.departure}` : `Only ${res.soc_at_departure_pct}% by ${res.departure} – leave later or charge less`}</div>
            <div className="pills">
              <span className="pill save">Save LKR {res.saving_lkr}</span>
              <span className="pill">Cost LKR {res.cost_lkr}</span>
              <span className="pill">{res.kwh_from_grid} kWh @ {res.charger_kw} kW</span>
            </div>
            <div className="src">Departure: {res.departure_source}</div>
          </div>
          <div className="card">
            <h3>Your plan vs. plugging in now</h3>
            <ResponsiveContainer width="100%" height={210}>
              <ComposedChart data={res.timeline} margin={{ left: -18, right: 4, top: 8 }}>
                <CartesianGrid stroke="#eef3f2" vertical={false} />
                <XAxis dataKey="time" interval={7} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} unit=" kW" />
                <Tooltip formatter={(v, n) => [`${v}`, n]} />
                <Bar dataKey="plan_kw" name="Smart plan (kW)" fill="#0f9d8a" radius={[3, 3, 0, 0]} />
                <Line dataKey="uncontrolled_kw" name="Plug in now (kW)" stroke="#ef6c57" dot={false} strokeWidth={2} />
              </ComposedChart>
            </ResponsiveContainer>
            <div className="tariff">
              {res.timeline.map((t, i) => <span key={i} style={{ background: priceColor(t.price) }} title={`${t.time} · LKR ${t.price}/kWh`} />)}
            </div>
            <div className="legend"><span className="lg off" />Off-peak 21 <span className="lg day" />Day 35 <span className="lg peak" />Peak 67 LKR/kWh</div>
            <p className="hint">{res.note}</p>
          </div>
        </>
      )}
    </>
  );
}
