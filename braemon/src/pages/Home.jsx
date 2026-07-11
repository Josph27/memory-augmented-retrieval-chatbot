import { Link } from "react-router-dom";

const chats = [
	{ label: "System Architecture Review v2", active: true },
	{ label: "Debug Stream: Auth Module Error", active: true },
	{ label: "Query Log Optimization", active: false },
	{ label: "Database Migration Plan Assessment", inactive: true },
	{ label: "API Rate Limiting Logic Review", inactive: true },
	{ label: "Frontend Performance Audit 2024", inactive: true },
	{ label: "React Router V6 Integration Strategy", inactive: true },
	{ label: "Tailwind Custom Config Setup", inactive: true },
	{ label: "Redis Cache Implementation Details", inactive: true },
	{ label: "Kubernetes Deployment Scripts Issue", inactive: true },
	{ label: "User Authentication Flow Analysis", inactive: true },
	{ label: "Payment Gateway Webhooks Debugging", inactive: true },
	{ label: "Serverless Functions Config Updates", inactive: true },
	{ label: "GraphQL Schema Definition Check", inactive: true },
	{ label: "End-to-End Testing Setup Guide", inactive: true },
	{ label: "CI/CD Pipeline Configuration Steps", inactive: true },
	{ label: "Websocket Connection Dropping Issue", inactive: true },
	{ label: "Image Optimization Pipeline Review", inactive: true },
];

function Home() {
	return (
		<div className="px-margin py-lg max-w-7xl mx-auto flex flex-col gap-lg lg:h-[calc(100vh-3rem)] lg:overflow-hidden">
			{/* Hero */}
			<div className="flex flex-col items-center justify-center gap-md text-center max-w-3xl mx-auto py-sm shrink-0">
				<header className="space-y-sm">
					<h1 className="font-display text-display text-on-surface">
						Technical Retrieval Workspace
					</h1>
				</header>
				<div className="mt-md">
					<Link
						to="/chat"
						className="group relative overflow-hidden rounded-lg bg-almond-silk text-primary-container font-headline-md text-headline-md px-xl py-lg flex items-center justify-center gap-md hover:bg-[#d2c2cf] transition-all duration-300 mx-auto min-w-[200px]"
					>
						<span className="material-symbols-outlined">add_circle</span>
						<span>New Chat</span>
						<div className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg pointer-events-none" />
					</Link>
				</div>
			</div>

			{/* Bottom Section: Two Columns */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-lg flex-1 min-h-0">
				{/* Left: Continue Chat */}
				<div className="lg:col-span-8 flex flex-col gap-md min-h-0">
					<div className="glass-panel p-lg rounded-lg flex flex-col gap-md flex-1 min-h-0">
						<div className="flex items-center justify-between border-b border-outline-variant/20 pb-sm shrink-0">
							<h3 className="font-label-md text-label-md text-on-surface uppercase tracking-wider flex items-center gap-2">
								<span className="material-symbols-outlined text-on-surface-variant text-sm">
									history
								</span>
								Continue Chat
							</h3>
							<span className="font-label-sm text-on-surface-variant">
								Last 30 Days
							</span>
						</div>
						<ul className="space-y-sm font-body-sm text-body-sm text-on-surface-variant overflow-y-auto custom-scrollbar pr-2 flex-1 min-h-0">
							{chats.map((chat, i) => {
								const activeStyle = chat.active
									? "border-l-2 border-almond-silk"
									: chat.inactive
										? "border-l-2 border-outline-variant"
										: "border-l-2 border-lilac-ash";
								return (
									<Link
										key={i}
										to="/chat"
										className={`flex items-center gap-sm ${activeStyle} pl-sm py-xs hover:bg-surface-container transition-colors rounded-r no-underline text-on-surface-variant`}
									>
										<span className="truncate">{chat.label}</span>
									</Link>
								);
							})}
						</ul>
					</div>
				</div>

				{/* Right: Quick Actions */}
				<div className="lg:col-span-4 flex flex-col sm:flex-row lg:flex-col gap-md">
					<Link
						to="/chats"
						className="glass-panel flex-1 rounded-lg hover:bg-[#4a4e69]/30 transition-all duration-300 flex flex-col items-center justify-center p-xl gap-sm text-center group cursor-pointer border border-outline-variant/30 hover:border-[#c9ada7]/50"
					>
						<span className="material-symbols-outlined text-4xl text-almond-silk group-hover:scale-110 transition-transform">
							forum
						</span>
						<h3 className="font-headline-md text-headline-md text-on-surface">
							Chats
						</h3>
						<p className="font-body-sm text-body-sm text-on-surface-variant max-w-[200px]">
							Browse and manage all active workspace conversations.
						</p>
					</Link>
					<Link
						to="/documents"
						className="glass-panel flex-1 rounded-lg hover:bg-[#4a4e69]/30 transition-all duration-300 flex flex-col items-center justify-center p-xl gap-sm text-center group cursor-pointer border border-outline-variant/30 hover:border-lilac-ash/50"
					>
						<span className="material-symbols-outlined text-4xl text-lilac-ash group-hover:scale-110 transition-transform">
							description
						</span>
						<h3 className="font-headline-md text-headline-md text-on-surface">
							Documents
						</h3>
						<p className="font-body-sm text-body-sm text-on-surface-variant max-w-[200px]">
							Access indexed files, code snippets, and structured data.
						</p>
					</Link>
					<Link
						to="/memories"
						className="glass-panel flex-1 rounded-lg hover:bg-[#4a4e69]/30 transition-all duration-300 flex flex-col items-center justify-center p-xl gap-sm text-center group cursor-pointer border border-outline-variant/30 hover:border-primary/50"
					>
						<span className="material-symbols-outlined text-4xl text-primary group-hover:scale-110 transition-transform">
							psychology
						</span>
						<h3 className="font-headline-md text-headline-md text-on-surface">
							Memories
						</h3>
						<p className="font-body-sm text-body-sm text-on-surface-variant max-w-[200px]">
							Explore contextual vectors and persistent system states.
						</p>
					</Link>
				</div>
			</div>
		</div>
	);
}

export default Home;
