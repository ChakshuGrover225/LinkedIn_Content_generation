import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Dev only: forwards /api to FastAPI so the browser sees a single origin (no CORS needed locally).
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
