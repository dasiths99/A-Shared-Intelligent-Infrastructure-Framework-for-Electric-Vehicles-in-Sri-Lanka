import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// C3 frontend on :5183, API calls to /api/* go to the C3 backend on :8003
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5183,
    strictPort: true,
    proxy: { "/api": { target: "http://localhost:8003", rewrite: (p) => p.replace(/^\/api/, ""), timeout: 120000 } },
  },
});
