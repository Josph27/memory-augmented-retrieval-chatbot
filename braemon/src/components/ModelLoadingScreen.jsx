import { useState, useEffect } from "react";

/**
 * Fullscreen loading overlay — same spinner used for "Consolidating memory…".
 * Polls /api/models/status until the backend signals models are ready.
 */
export default function ModelLoadingScreen({ children }) {
	const [ready, setReady] = useState(false);
	const [error, setError] = useState(null);

	useEffect(() => {
		let cancelled = false;

		async function poll() {
			while (!cancelled) {
				try {
					const res = await fetch("/api/models/status");
					if (!res.ok) throw new Error(`HTTP ${res.status}`);
					const data = await res.json();
					if (data.ready) {
						if (!cancelled) setReady(true);
						return;
					}
				} catch (_err) {
					// Backend still starting — keep polling.
				}
				await new Promise((r) => setTimeout(r, 500));
			}
		}

		const safety = setTimeout(() => {
			if (!cancelled && !ready) {
				setError(
					"Models took too long to load. The inference server may be unreachable.",
				);
			}
		}, 120_000);

		poll();

		return () => {
			cancelled = true;
			clearTimeout(safety);
		};
	}, [ready]);

	if (error) {
		return (
			<div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm">
				<div className="text-center max-w-md px-6">
					<span className="material-symbols-outlined text-[48px] text-error mb-4 block">
						cloud_off
					</span>
					<h2 className="text-headline-md font-bold text-on-surface mb-2">
						Backend Unavailable
					</h2>
					<p className="text-body-md text-on-surface-variant">{error}</p>
					<button
						onClick={() => {
							setError(null);
							setReady(false);
						}}
						className="mt-6 px-6 py-2 bg-primary text-on-primary rounded-full font-medium hover:opacity-90 transition-opacity"
					>
						Retry
					</button>
				</div>
			</div>
		);
	}

	if (!ready) {
		return (
			<div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/70 backdrop-blur-sm gap-6">
				<div
					className="w-16 h-16 rounded-full animate-spin"
					style={{
						background:
							"conic-gradient(from 0deg, #6b5b95, #c5c3e4, #c9ada7, #9a8c98, #6b5b95)",
						mask: "radial-gradient(farthest-side, transparent calc(100% - 5px), #000 calc(100% - 4px))",
						WebkitMask:
							"radial-gradient(farthest-side, transparent calc(100% - 5px), #000 calc(100% - 4px))",
					}}
				/>
				<p className="text-headline-sm font-bold text-on-surface">
					Loading models…
				</p>
			</div>
		);
	}

	return children;
}
