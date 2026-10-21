import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const t = (iso) => new Date(iso).toLocaleString("en-GB", { timeZone: "Asia/Colombo", weekday: "short", hour: "2-digit", minute: "2-digit" });

export default function History() {
  const [rows, setRows] = useState(null);
  useEffect(() => { api("/sessions").then(setRows).catch(() => setRows([])); }, []);
  if (!rows) return <div className="card">Loading…</div>;
  const saved = rows.reduce((s, r) => s + (r.uncontrolled_cost_lkr - r.cost_lkr), 0);
  return (
    <>
      <div className="card stat">
        <div><b>{rows.length}</b><span>sessions</span></div>
        <div><b>LKR {Math.round(saved)}</b><span>saved vs plug-in-now</span></div>
        <div><b>{Math.min(rows.length, 10)}/10</b><span>to personal routine</span></div>
      </div>
      {rows.length === 0 && <div className="card empty"><p>No sessions yet. Plan your first charge!</p></div>}
      {rows.map((r) => (
        <div className="card hist" key={r.id}>
          <div><b>{r.planned_start_utc ? `${t(r.planned_start_utc)} → ${t(r.planned_end_utc)}` : "no charging"}</b>
            <div className="specs">{r.soc_start_pct}% → {r.soc_target_pct}% · {r.kwh_needed.toFixed(1)} kWh · leave {t(r.departure_utc)}</div></div>
          <div className="right"><span className="pill save">−LKR {Math.round(r.uncontrolled_cost_lkr - r.cost_lkr)}</span></div>
        </div>
      ))}
    </>
  );
}
