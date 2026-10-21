import React, { useEffect, useState } from "react";
import { api, auth } from "./api.js";
import Auth from "./screens/Auth.jsx";
import Plan from "./screens/Plan.jsx";
import MyEV from "./screens/MyEV.jsx";
import History from "./screens/History.jsx";
import Grid from "./screens/Grid.jsx";

const TABS = [
  { id: "plan", label: "Plan", icon: "⚡" },
  { id: "ev", label: "My EV", icon: "🚗" },
  { id: "history", label: "History", icon: "🕘" },
  { id: "grid", label: "Grid", icon: "📈" },
];

export default function App() {
  const [token, setToken] = useState(auth.get());
  const [tab, setTab] = useState("plan");
  const [vehicles, setVehicles] = useState([]);

  const loadVehicles = () => api("/vehicles").then(setVehicles).catch(() => { auth.set(null); setToken(null); });
  useEffect(() => { if (token) loadVehicles(); }, [token]);

  if (!token) return <Shell><Auth onLogin={(t) => { auth.set(t); setToken(t); }} /></Shell>;

  return (
    <Shell>
      <header className="hero">
        <div>
          <div className="brand">Smart Charge <span>LK</span></div>
          <div className="tagline">Charge when the grid is quiet · save on TOU</div>
        </div>
        <button className="ghost" onClick={() => { auth.set(null); setToken(null); }}>Log out</button>
      </header>
      <main className="content">
        {tab === "plan" && <Plan vehicles={vehicles} goToEV={() => setTab("ev")} />}
        {tab === "ev" && <MyEV vehicles={vehicles} reload={loadVehicles} />}
        {tab === "history" && <History />}
        {tab === "grid" && <Grid />}
      </main>
      <nav className="tabbar">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            <span className="ico">{t.icon}</span>{t.label}
          </button>
        ))}
      </nav>
    </Shell>
  );
}

function Shell({ children }) {
  return <div className="phone">{children}</div>;
}
