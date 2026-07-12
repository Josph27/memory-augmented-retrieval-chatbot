import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { RecoilRoot } from "recoil";
import { ChainlitContext, ChainlitAPI, useAuth } from "@chainlit/react-client";
import "./index.css";
import App from "./App.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";

const CHAINLIT_URL = "http://localhost:8000";
const apiClient = new ChainlitAPI(CHAINLIT_URL, "webapp");

function AuthWrapper({ children }) {
	const { isAuthenticated, isReady } = useAuth();

	useEffect(() => {
		if (isReady && !isAuthenticated) {
			// Auto-login for local prototype
			fetch("/login", {
				method: "POST",
				headers: { "Content-Type": "application/x-www-form-urlencoded" },
				body: new URLSearchParams({ username: "local", password: "local" }),
			})
				.then((res) => {
					if (res.ok) {
						console.log("Auto-login successful. Reloading to apply auth.");
						window.location.reload();
					} else {
						console.error("Auto-login failed:", res.status);
					}
				})
				.catch(console.error);
		}
	}, [isReady, isAuthenticated]);

	// Wait for auth to complete to ensure Socket.IO sends the cookie
	if (!isReady || !isAuthenticated) {
		return (
			<div className="flex h-screen items-center justify-center bg-background text-on-surface-variant font-code">
				Authenticating...
			</div>
		);
	}

	return children;
}

createRoot(document.getElementById("root")).render(
	<StrictMode>
		<RecoilRoot>
			<ChainlitContext.Provider value={apiClient}>
				<ErrorBoundary>
					<AuthWrapper>
						<App />
					</AuthWrapper>
				</ErrorBoundary>
			</ChainlitContext.Provider>
		</RecoilRoot>
	</StrictMode>,
);
