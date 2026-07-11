import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RecoilRoot } from "recoil";
import { ChainlitContext, ChainlitAPI } from "@chainlit/react-client";
import "./index.css";
import App from "./App.jsx";

const CHAINLIT_URL = "http://localhost:8000";
const apiClient = new ChainlitAPI(CHAINLIT_URL, "webapp");

createRoot(document.getElementById("root")).render(
	<StrictMode>
		<RecoilRoot>
			<ChainlitContext.Provider value={apiClient}>
				<App />
			</ChainlitContext.Provider>
		</RecoilRoot>
	</StrictMode>,
);
