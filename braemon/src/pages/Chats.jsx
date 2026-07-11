import { Link } from "react-router-dom";

const activeThreads = [
	{ id: "1", title: "System Architecture Planning", time: "10:42 AM" },
	{ id: "2", title: "Data Pipeline Optimization", time: "09:15 AM" },
	{ id: "3", title: "UI Tokens Refactor", time: "Yesterday" },
];

const inactiveThreads = [
	{ id: "4", title: "Q3 Resource Allocation Review", time: "Oct 12" },
	{ id: "5", title: "Legacy API Deprecation Notice", time: "Oct 05" },
	{ id: "6", title: "Initial Onboarding Setup", time: "Sep 28" },
];

export default function Chats() {
	return (
		<div className="pt-xl pb-xl px-margin max-w-4xl mx-auto">
			<header className="mb-xl flex justify-between items-end border-b border-outline-variant/20 pb-sm">
				<div>
					<h1 className="font-headline-lg text-headline-lg text-primary">
						Chat Threads
					</h1>
					<p className="font-label-md text-label-md text-on-surface-variant mt-xs">
						Contextual data streams and dialogue histories.
					</p>
				</div>
				<button
					className="bg-almond-silk text-primary-container px-lg py-sm rounded font-label-md text-label-md hover:bg-surface-tint transition-colors flex items-center gap-sm opacity-50 cursor-not-allowed"
					disabled
				>
					<span className="material-symbols-outlined text-[16px]">add</span>New
					Session
				</button>
			</header>

			<section className="mb-xl">
				<h2 className="font-label-md text-label-md text-secondary mb-sm uppercase tracking-wider">
					Active Threads
				</h2>
				<div className="bg-surface-container-low border border-outline-variant/20 rounded overflow-hidden">
					{activeThreads.map((t) => (
						<Link
							key={t.id}
							to="/chat"
							className="group flex items-center justify-between px-lg py-sm border-b border-lilac-ash/10 hover:bg-dusty-grape/20 transition-colors cursor-pointer h-10 no-underline"
						>
							<div className="flex items-center gap-md">
								<span className="material-symbols-outlined text-[16px] text-primary">
									chat_bubble
								</span>
								<span className="font-body-md text-body-md text-on-surface truncate max-w-[300px]">
									{t.title}
								</span>
							</div>
							<span className="font-code text-code text-on-surface-variant">
								{t.time}
							</span>
						</Link>
					))}
				</div>
			</section>

			<section>
				<h2 className="font-label-md text-label-md text-on-surface-variant mb-sm uppercase tracking-wider">
					Inactive Threads
				</h2>
				<div className="bg-surface-container-lowest border border-outline-variant/20 rounded overflow-hidden opacity-80">
					{inactiveThreads.map((t) => (
						<Link
							key={t.id}
							to="/chat"
							className="group flex items-center justify-between px-lg py-sm border-b border-lilac-ash/10 hover:bg-dusty-grape/10 transition-colors cursor-pointer h-10 no-underline"
						>
							<div className="flex items-center gap-md">
								<span className="material-symbols-outlined text-[16px] text-on-surface-variant">
									history
								</span>
								<span className="font-body-md text-body-md text-on-surface-variant truncate max-w-[300px]">
									{t.title}
								</span>
							</div>
							<span className="font-code text-code text-on-surface-variant/70">
								{t.time}
							</span>
						</Link>
					))}
				</div>
			</section>
		</div>
	);
}
