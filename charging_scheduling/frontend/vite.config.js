import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// C1 frontend on :5181, API calls to /api/* go to the C1 backend on :8001
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5181,
    strictPort: true,
    proxy: { "/api": { target: "http://localhost:8001", rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
