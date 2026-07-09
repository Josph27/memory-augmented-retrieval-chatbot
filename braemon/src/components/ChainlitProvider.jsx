import { useState, useEffect } from "react";
import { ChainlitAPI, ChainlitContext } from "@chainlit/react-client";

const CHAINLIT_URL = "http://localhost:8000";

// eslint-disable-next-line react/prop-types
export default function ChainlitProvider({ children }) {
	const [client, setClient] = useState(null);
	const [error, setError] = useState(null);

	useEffect(() => {
		let cancelled = false;
		const api = new ChainlitAPI(CHAINLIT_URL, "webapp");

		const formData = new FormData();
		formData.set("username", "local");
		formData.set("password", "local");

		api
			.passwordAuth(formData)
			.then(() => {
				if (!cancelled) setClient(api);
			})
			.catch((err) => {
				if (!cancelled) setError(`Auth failed: ${err.message}`);
			});

		return () => {
			cancelled = true;
		};
	}, []);

	if (error) {
		return (
			<div className="h-screen flex items-center justify-center bg-background">
				<div className="glass-panel p-xl rounded-lg text-center">
					<span className="material-symbols-outlined text-4xl text-error mb-md block">
						error
					</span>
					<p className="font-body-lg text-error">{error}</p>
					<p className="font-body-sm text-on-surface-variant mt-sm">
						Is Chainlit running on port 8000?
					</p>
				</div>
			</div>
		);
	}

	if (!client) {
		return (
			<div className="h-screen flex items-center justify-center bg-background">
				<div className="flex flex-col items-center gap-md">
					<div className="w-8 h-8 border-2 border-almond-silk border-t-transparent rounded-full animate-spin" />
					<p className="font-label-md text-on-surface-variant">
						Authenticating Braemon...
					</p>
				</div>
			</div>
		);
	}

	return (
		<ChainlitContext.Provider value={client}>
			{children}
		</ChainlitContext.Provider>
	);
}
