import React, { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";

const COLORS = { "B1 uncontrolled": "#ef6c57", "B2 fixed TOU 22:30": "#ffa726", "B3 TOU + random delay": "#ab47bc",
  "B4 coordinated, defaults": "#90a4ae", "Coordinated (personal)": "#0f9d8a" };

export default function Grid() {
  const [dates, setDates] = useState([]);
  const [date, setDate] = useState("");
  const [fc, setFc] = useState(null);
  const [nEv, setNEv] = useState(200);
  const [sc, setSc] = useState(null);
  useEffect(() => {
    api("/grid/forecast-dates").then((d) => { setDates(d); setDate(d[Math.floor(d.length / 2)]); });
  }, []);
  useEffect(() => { if (date) api("/grid/forecast", { query: { date } }).then(setFc); }, [date]);
  useEffect(() => { setSc(null); const id = setTimeout(() => api("/grid/scenario", { query: { n_ev: nEv } }).then(setSc), 300); return () => clearTimeout(id); }, [nEv]);

  const scData = sc ? sc.time_local.map((t, i) => ({ t, base: sc.base_kw[i], ...Object.fromEntries(Object.entries(sc.curves).map(([k, v]) => [k, v[i]])) })) : [];

  return (
    <>
      <div className="card">
        <h2>Household load forecast</h2>
        <p className="hint">How much electricity an average Sri Lankan home uses through the day – forecast vs. what really happened.</p>
        <select value={date} onChange={(e) => setDate(e.target.value)}>{dates.map((d) => <option key={d}>{d}</option>)}</select>
        {fc && (<>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={fc.points} margin={{ left: -14, right: 4, top: 8 }}>
              <CartesianGrid stroke="#eef3f2" vertical={false} />
              <XAxis dataKey="time_local" interval={11} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} />
              <Tooltip />
              <Line dataKey="actual_kw" name="actual" stroke="#263238" dot={false} strokeWidth={2} />
              <Line dataKey="forecast_kw" name="forecast" stroke="#0f9d8a" dot={false} strokeWidth={2} />
              <Line dataKey="last_week_kw" name="last week" stroke="#b0bec5" dot={false} strokeDasharray="4 3" />
            </LineChart>
          </ResponsiveContainer>
        </>)}
      </div>

      <div className="card">
        <h2>What if everyone charges?</h2>
        <p className="hint">Example street of 1,000 homes: what happens to the evening peak when many EVs plug in.</p>
        <div className="slider"><span>EVs on the feeder</span><b>{nEv}</b></div>
        <input type="range" min="50" max="500" step="50" value={nEv} onChange={(e) => setNEv(+e.target.value)} />
        {!sc ? <div className="hint">Solving…</div> : (<>
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={scData} margin={{ left: -6, right: 4, top: 8 }}>
              <CartesianGrid stroke="#eef3f2" vertical={false} />
              <XAxis dataKey="t" interval={15} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Line dataKey="base" name="homes only" stroke="#cfd8dc" dot={false} strokeWidth={3} />
              {Object.keys(sc.curves).map((k) => <Line key={k} dataKey={k} stroke={COLORS[k]} dot={false} strokeWidth={k.startsWith("Coord") ? 3 : 1.5} />)}
            </LineChart>
          </ResponsiveContainer>
          <table className="mini"><thead><tr><th>Strategy</th><th>Peak kW</th><th>vs B1</th><th>Ready</th></tr></thead><tbody>
            {Object.entries(sc.metrics).map(([k, m]) => <tr key={k} className={k.startsWith("Coord") ? "hl" : ""}><td>{k}</td><td>{m.peak_kw}</td><td>{m.peak_reduction_vs_B1_pct}%</td><td>{m.car_ready_pct}%</td></tr>)}
          </tbody></table>
        </>)}
      </div>
    </>
  );
}
