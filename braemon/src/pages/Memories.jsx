import { useState } from "react";

const memories = [
	{
		title: "Project Phoenix Specs",
		text: "Initial architecture definitions for the new routing module. The system will use a dual-path approach: native Chainlit routing for simple queries with known intent patterns, and an experimental LangGraph orchestration path for complex multi-hop retrieval. Both paths share the same typed-memory infrastructure — Chroma for document vectors, SQLite for structured memories via LangMem, and a gisting pipeline for conversation compression.",
		time: "2 hours ago",
		color: "bg-primary",
	},
	{
		title: "Client Meeting Notes - Acme",
		text: "Key takeaways regarding the Q3 delivery schedule and expected SLAs. Acme requires 99.9% uptime for the production deployment with a maximum latency of 200ms p95 on retrieval queries. They also requested audit logging for all memory write operations and a rollback mechanism for accidental memory deletions. The initial deployment target is August 2026 with a beta preview in late July.",
		time: "Yesterday",
		color: "bg-secondary",
	},
	{
		title: "User Persona V2",
		text: "Updated demographics focusing on technical power users in the enterprise sector. Primary persona 'DevOps Diana' — senior infrastructure engineer, 8+ years experience, prefers CLI and keyboard shortcuts over mouse interaction, values response latency over explanation verbosity. Secondary persona 'Architect Alex' — system architect, needs deep trace explanations for retrieval decisions, wants to inspect source candidates and reranking scores.",
		time: "Oct 12",
		color: "bg-tertiary",
	},
	{
		title: "API Key Configurations",
		text: "Draft settings for staging environment authentication flows. All API keys must be rotated every 90 days. The staging environment uses a separate keyring from production with reduced rate limits (100 req/min vs 1000 req/min). Third-party integrations (Stitch, GitHub, Slack) use OAuth2 with refresh token rotation enabled. Service-to-service auth uses mTLS with certificate pinning.",
		time: "Oct 10",
		color: "bg-primary-fixed-dim",
	},
];

export default function Memories() {
	const [expanded, setExpanded] = useState(null);

	return (
		<div className="pt-xl pb-xl px-margin max-w-[1200px] mx-auto w-full">
			<div className="mb-lg flex flex-col md:flex-row justify-between items-start md:items-end gap-md">
				<div>
					<h1 className="font-display text-display text-primary">
						Memory Vault
					</h1>
				</div>
				<div className="relative w-full md:w-96">
					<span className="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-outline">
						search
					</span>
					<input
						className="w-full bg-surface-container-high border border-outline-variant rounded text-on-surface pl-8 pr-sm py-sm font-body-md text-body-md focus:outline-none focus:border-primary focus:ring-0 transition-colors placeholder:text-on-surface-variant/50"
						placeholder="Search memories..."
						type="text"
					/>
				</div>
			</div>

			<div className="mb-xl bg-secondary-container rounded py-sm px-md flex items-center">
				<span className="font-label-md text-label-md text-secondary uppercase tracking-wider mr-sm">
					Quick Stats:
				</span>
				<span className="font-body-md text-body-md text-on-secondary-container">
					Total Memories: {memories.length}
				</span>
			</div>

			<div className="flex flex-col">
				{memories.map((mem, i) => {
					const isExpanded = expanded === i;
					return (
						<div key={i}>
							{/* Summary row — always visible */}
							<div
								onClick={() => setExpanded(isExpanded ? null : i)}
								className={`group flex items-center justify-between px-sm hover:bg-surface-container-high transition-colors border-b border-outline-variant/10 cursor-pointer ${isExpanded ? "h-10" : "h-10"}`}
							>
								<div className="flex items-center gap-md flex-1 min-w-0">
									<div className={`w-[2px] h-4 shrink-0 ${mem.color}`} />
									<span
										className={`font-label-md text-label-md text-primary w-48 ${isExpanded ? "" : "truncate"}`}
									>
										{mem.title}
									</span>
									<span
										className={`font-body-sm text-body-sm text-on-surface-variant ${isExpanded ? "hidden" : "truncate"}`}
									>
										{mem.text.slice(0, 80)}...
									</span>
								</div>
								<div className="flex items-center gap-md opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
									<span className="font-label-sm text-label-sm text-on-surface-variant">
										{mem.time}
									</span>
									<span
										className={`material-symbols-outlined text-[18px] text-on-surface-variant transition-transform ${isExpanded ? "rotate-180" : ""}`}
									>
										expand_more
									</span>
									<button
										className="text-on-surface-variant hover:text-error transition-colors p-1"
										onClick={(e) => e.stopPropagation()}
									>
										<span className="material-symbols-outlined text-[18px]">
											delete
										</span>
									</button>
								</div>
							</div>

							{/* Expanded detail — only shown when clicked */}
							{isExpanded && (
								<div className="px-8 py-md border-b border-outline-variant/10 bg-surface-container-low/30">
									<p className="font-body-md text-body-md text-on-surface leading-relaxed whitespace-pre-wrap">
										{mem.text}
									</p>
								</div>
							)}
						</div>
					);
				})}
			</div>
		</div>
	);
}
