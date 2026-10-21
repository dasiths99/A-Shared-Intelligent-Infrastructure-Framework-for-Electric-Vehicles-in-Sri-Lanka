// Tiny API client for the C1 backend (proxied at /api by Vite).
const KEY = "c1_token";

export const auth = {
  get() { try { return localStorage.getItem(KEY); } catch { return null; } },
  set(t) { try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch { /* storage blocked */ } },
};

export async function api(path, { method = "GET", body, query } = {}) {
  const qs = query ? "?" + new URLSearchParams(query).toString() : "";
  const headers = { "Content-Type": "application/json" };
  const t = auth.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`/api/c1${path}${qs}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}
