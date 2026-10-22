import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development, requests to /api are forwarded to the FastAPI backend.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.js"] },
  server: {
    port: 5173,
    // API_TARGET lets you point the dev server at another backend, e.g.  API_TARGET=http://127.0.0.1:8001 npm run dev
    proxy: { "/api": process.env.API_TARGET || "http://127.0.0.1:8000" },
  },
});
