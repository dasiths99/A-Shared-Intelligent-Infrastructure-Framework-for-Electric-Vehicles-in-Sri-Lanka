import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Auth({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [districts, setDistricts] = useState([]);
  const [f, setF] = useState({ email: "", password: "", district: "Colombo", consent: false });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/meta").then((m) => setDistricts(m.districts)).catch(() => {}); }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const r = mode === "login"
        ? await api("/auth/login", { method: "POST", body: { email: f.email, password: f.password } })
        : await api("/auth/register", { method: "POST", body: f });
      onLogin(r.token);
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  return (
    <div className="auth">
      <div className="auth-hero">
        <div className="bolt">⚡</div>
        <h1>Smart Charge <span>LK</span></h1>
        <p>Your personal EV charging planner for Sri Lanka's TOU tariff.</p>
      </div>
      <form className="card" onSubmit={submit}>
        <div className="seg">
          <button type="button" className={mode === "login" ? "on" : ""} onClick={() => setMode("login")}>Log in</button>
          <button type="button" className={mode === "register" ? "on" : ""} onClick={() => setMode("register")}>Register</button>
        </div>
        <label>Email<input type="email" required value={f.email} onChange={set("email")} /></label>
        <label>Password<input type="password" required minLength={6} value={f.password} onChange={set("password")} /></label>
        {mode === "register" && (
          <>
            <label>District<select value={f.district} onChange={set("district")}>{districts.map((d) => <option key={d}>{d}</option>)}</select></label>
            <label className="check"><input type="checkbox" checked={f.consent} onChange={set("consent")} />
              I agree that my charging data is stored with a random ID and district only (no name, plate or GPS). I can delete it any time.</label>
          </>
        )}
        {err && <div className="error">{err}</div>}
        <button className="primary" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}</button>
      </form>
      <p className="fine">J26-IT-430 · SLIIT research prototype · Component 1</p>
    </div>
  );
}
