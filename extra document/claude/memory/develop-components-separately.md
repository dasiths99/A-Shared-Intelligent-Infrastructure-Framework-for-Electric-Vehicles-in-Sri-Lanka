---
name: develop-components-separately
description: "Build C1, C2, C3 as fully separate folders/models; no integration until the user explicitly says to merge"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c82d2d2f-1b2e-48d7-a347-0674f73a2809
  modified: 2026-10-19T08:13:39.077Z
---

Develop each component (C1 charging_scheduling/, C2 station_siting/, C3 route_recommendation/) completely separately. Do NOT integrate them (no shared API wiring, no C1→C2/C3 data flows, no cross-component imports beyond `shared/config.py`) until the user explicitly says to merge.

**Why:** User instruction on 2026-10-19 ("develop each part separately, not integrate this time, until I tell you to merge").

**How to apply:** Keep code, cleaned data and results inside the component's own folder. Where a component would normally consume another's output (e.g. C3 needs C1 busyness forecast, C2 needs C1 growth factors), use a local placeholder/fallback inside that component and note it for later merge. Also: never modify `data/raw/` — cleaned outputs go to `data/interim/` or `data/processed/`.
