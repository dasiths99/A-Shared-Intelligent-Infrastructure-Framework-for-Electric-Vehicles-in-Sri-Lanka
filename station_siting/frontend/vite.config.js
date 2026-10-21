import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// C2 frontend on :5182, API calls to /api/* go to the C2 backend on :8002
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5182,
    strictPort: true,
    proxy: { "/api": { target: "http://localhost:8002", rewrite: (p) => p.replace(/^\/api/, ""), timeout: 180000 } },
  },
});
