import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import consoleForwardPlugin from "./console-forward-plugin.mjs";

export default defineConfig({
	plugins: [react(), tailwindcss(), consoleForwardPlugin()],
	server: {
		proxy: {
			"/api": { target: "http://localhost:8000" },
			"/ws": { target: "http://localhost:8000", ws: true },
			"/auth": { target: "http://localhost:8000" },
			"/project": { target: "http://localhost:8000" },
			"/login": { target: "http://localhost:8000" },
			"/logout": { target: "http://localhost:8000" },
			"/user": { target: "http://localhost:8000" },
			"/mcp": { target: "http://localhost:8000" },
		},
	},
});
