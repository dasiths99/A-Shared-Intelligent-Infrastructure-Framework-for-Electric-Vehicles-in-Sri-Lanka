import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

const EMPTY = { model_id: "", nickname: "", home_charger_kw: 7.4, tariff_type: "TOU", usual_plugin: "19:00",
  usual_departure: "07:30", min_soc_pct: 15, battery_health_pct: 100, let_app_schedule: true };

export default function MyEV({ vehicles, reload }) {
  const [models, setModels] = useState([]);
  const [make, setMake] = useState("Nissan");
  const [f, setF] = useState(EMPTY);
  const [show, setShow] = useState(!vehicles.length);
  const [newModel, setNewModel] = useState(null);
  const [err, setErr] = useState("");
  const loadModels = () => api("/vehicle-models").then(setModels);
  useEffect(() => { loadModels(); }, []);
  const makes = useMemo(() => [...new Set(models.map((m) => m.make))], [models]);
  const ofMake = models.filter((m) => m.make === make);
  const sel = models.find((m) => m.id === Number(f.model_id));
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const save = async () => {
    setErr("");
    try {
      await api("/vehicles", { method: "POST", body: { ...f, model_id: Number(f.model_id),
        home_charger_kw: Number(f.home_charger_kw), min_soc_pct: Number(f.min_soc_pct), battery_health_pct: Number(f.battery_health_pct) } });
      setF(EMPTY); setShow(false); reload();
    } catch (x) { setErr(x.message); }
  };
  const saveModel = async () => {
    setErr("");
    try {
      const m = await api("/vehicle-models", { method: "POST", body: { ...newModel, usable_kwh: Number(newModel.usable_kwh),
        max_ac_kw: Number(newModel.max_ac_kw) || null, max_dc_kw: Number(newModel.max_dc_kw) || null, year: Number(newModel.year) || null } });
      await loadModels(); setMake(m.make); setF({ ...f, model_id: m.id }); setNewModel(null);
    } catch (x) { setErr(x.message); }
  };

  return (
    <>
      {vehicles.map((v) => (
        <div className="card ev" key={v.id}>
          <div className="ev-icon">🚙</div>
          <div>
            <h3>{v.nickname || `${v.model.make} ${v.model.model}`}</h3>
            <div className="specs">{v.model.usable_kwh} kWh · AC {v.model.max_ac_kw ?? "?"} kW · {v.model.connector || "connector ?"}</div>
            <div className="specs">Home charger {v.home_charger_kw} kW · {v.tariff_type} · leaves {v.usual_departure} · min {v.min_soc_pct}%</div>
            <div className="rid">Random ID {v.random_id.slice(0, 8)}… (no plate / VIN stored)</div>
          </div>
        </div>
      ))}
      {!show ? <button className="primary wide" onClick={() => setShow(true)}>+ Add another EV</button> : (
        <div className="card">
          <h2>Add your EV</h2>
          <label>Make<select value={make} onChange={(e) => { setMake(e.target.value); setF({ ...f, model_id: "" }); }}>
            {makes.map((m) => <option key={m}>{m}</option>)}</select></label>
          <label>Model<select value={f.model_id} onChange={set("model_id")}>
            <option value="">Choose…</option>
            {ofMake.map((m) => <option key={m.id} value={m.id}>{m.model} {m.variant || ""} {m.year || ""} · {m.usable_kwh} kWh</option>)}
          </select></label>
          {sel && <div className="autofill">Auto-filled: {sel.usable_kwh} kWh usable · AC {sel.max_ac_kw ?? "?"} kW · DC {sel.max_dc_kw ?? "?"} kW · {sel.connector || "?"} <i>({sel.source})</i></div>}
          <button className="link" onClick={() => setNewModel({ make: "BYD", model: "", usable_kwh: "", max_ac_kw: "", max_dc_kw: "", connector: "type2;ccs", year: "", source: "" })}>My model is not in the list (e.g. BYD) →</button>
          {newModel && (
            <div className="subcard">
              <p className="hint">Enter values from the official brochure – they are shared with all users.</p>
              <div className="row2"><label>Make<input value={newModel.make} onChange={(e) => setNewModel({ ...newModel, make: e.target.value })} /></label>
                <label>Model<input value={newModel.model} onChange={(e) => setNewModel({ ...newModel, model: e.target.value })} /></label></div>
              <div className="row2"><label>Usable kWh<input type="number" value={newModel.usable_kwh} onChange={(e) => setNewModel({ ...newModel, usable_kwh: e.target.value })} /></label>
                <label>Year<input type="number" value={newModel.year} onChange={(e) => setNewModel({ ...newModel, year: e.target.value })} /></label></div>
              <div className="row2"><label>Max AC kW<input type="number" value={newModel.max_ac_kw} onChange={(e) => setNewModel({ ...newModel, max_ac_kw: e.target.value })} /></label>
                <label>Max DC kW<input type="number" value={newModel.max_dc_kw} onChange={(e) => setNewModel({ ...newModel, max_dc_kw: e.target.value })} /></label></div>
              <label>Source (brochure / website)<input value={newModel.source} onChange={(e) => setNewModel({ ...newModel, source: e.target.value })} /></label>
              <button className="secondary" onClick={saveModel}>Save model</button>
            </div>
          )}
          <label>Nickname<input value={f.nickname} onChange={set("nickname")} placeholder="optional" /></label>
          <div className="row2">
            <label>Home charger kW<input type="number" step="0.1" value={f.home_charger_kw} onChange={set("home_charger_kw")} /></label>
            <label>Tariff<select value={f.tariff_type} onChange={set("tariff_type")}><option>TOU</option><option>normal</option></select></label>
          </div>
          <div className="row2">
            <label>Usually plug in<input type="time" value={f.usual_plugin} onChange={set("usual_plugin")} /></label>
            <label>Usually leave<input type="time" value={f.usual_departure} onChange={set("usual_departure")} /></label>
          </div>
          <div className="row2">
            <label>Minimum SoC %<input type="number" value={f.min_soc_pct} onChange={set("min_soc_pct")} /></label>
            <label>Battery health %<input type="number" value={f.battery_health_pct} onChange={set("battery_health_pct")} /></label>
          </div>
          <label className="check"><input type="checkbox" checked={f.let_app_schedule} onChange={set("let_app_schedule")} />Let the app schedule my charging</label>
          {err && <div className="error">{err}</div>}
          <button className="primary" disabled={!f.model_id} onClick={save}>Save EV</button>
        </div>
      )}
    </>
  );
}
