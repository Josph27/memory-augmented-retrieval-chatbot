import { useState, useEffect } from "react";
import { fetchStats } from "../api";

function Row({ label, value }) {
	return (
		<div className="flex justify-between px-lg py-sm border-b border-outline-variant/10 font-body-md text-body-md items-start">
			<span className="text-on-surface-variant shrink-0 pt-[3px]">{label}</span>
			<span className="text-on-surface font-mono text-sm min-w-0 ml-md text-right break-all">
				{value}
			</span>
		</div>
	);
}

export default function Diagnostics() {
	const [stats, setStats] = useState(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		fetchStats()
			.then((data) => {
				setStats(data);
				setLoading(false);
			})
			.catch((err) => {
				console.error(err);
				setLoading(false);
			});
	}, []);

	return (
		<div className="pt-xl pb-xl px-margin max-w-4xl mx-auto">
			<h1 className="font-headline-lg text-headline-lg text-primary mb-lg">
				Diagnostics
			</h1>

			<section className="mb-xl">
				<h2 className="font-label-md text-label-md text-secondary mb-sm uppercase tracking-wider">
					System
				</h2>
				<div className="bg-surface-container-low border border-outline-variant/20 rounded overflow-hidden">
					{loading ? (
						<Row label="Status" value="Loading stats..." />
					) : (
						<>
							<Row label="Daemon" value="Running" />
							<Row label="Version" value={stats?.version ?? "v2.4.1"} />
							<Row label="Active Chats" value={stats?.active_chats ?? "0"} />
							<Row
								label="Total Memories"
								value={stats?.total_memories ?? "0"}
							/>
							<Row
								label="Ready Documents"
								value={stats?.ready_documents ?? "0"}
							/>
						</>
					)}
				</div>
			</section>

			<section className="mb-xl">
				<h2 className="font-label-md text-label-md text-secondary mb-sm uppercase tracking-wider">
					Build
				</h2>
				<div className="bg-surface-container-low border border-outline-variant/20 rounded overflow-hidden">
					<Row
						label="Frontend"
						value="Vite v8.1.3 + React 18.3.1 + Tailwind CSS v4"
					/>
					<Row label="Backend" value="Chainlit + FastAPI" />
					<Row label="Database" value="SQLite (chatbot.db) + Chroma" />
					<Row label="Design" value="Stitch — Braemon Design System" />
				</div>
			</section>

			<section className="mb-xl">
				<h2 className="font-label-md text-label-md text-secondary mb-sm uppercase tracking-wider">
					Environment
				</h2>
				<div className="bg-surface-container-low border border-outline-variant/20 rounded overflow-hidden">
					<Row
						label="User Agent"
						value={
							typeof navigator !== "undefined" ? navigator.userAgent : "N/A"
						}
					/>
					<Row
						label="Online"
						value={
							typeof navigator !== "undefined"
								? navigator.onLine
									? "Yes"
									: "No"
								: "N/A"
						}
					/>
					<Row
						label="Screen"
						value={
							typeof window !== "undefined"
								? `${window.innerWidth}×${window.innerHeight}`
								: "N/A"
						}
					/>
				</div>
			</section>
		</div>
	);
}
