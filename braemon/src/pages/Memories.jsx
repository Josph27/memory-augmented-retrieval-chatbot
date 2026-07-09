const memories = [
	{
		title: "Project Phoenix Specs",
		preview: "Initial architecture definitions for the new routing module...",
		time: "2 hours ago",
		color: "bg-primary",
	},
	{
		title: "Client Meeting Notes - Acme",
		preview:
			"Key takeaways regarding the Q3 delivery schedule and expected SLAs...",
		time: "Yesterday",
		color: "bg-secondary",
	},
	{
		title: "User Persona V2",
		preview:
			"Updated demographics focusing on technical power users in the enterprise sector...",
		time: "Oct 12",
		color: "bg-tertiary",
	},
	{
		title: "API Key Configurations",
		preview: "Draft settings for staging environment authentication flows...",
		time: "Oct 10",
		color: "bg-primary-fixed-dim",
	},
];

function Memories() {
	return (
		<div className="pt-xl pb-xl px-margin max-w-[1200px] mx-auto w-full">
			{/* Header */}
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

			{/* Quick Stats */}
			<div className="mb-xl bg-secondary-container rounded py-sm px-md flex items-center">
				<span className="font-label-md text-label-md text-secondary uppercase tracking-wider mr-sm">
					Quick Stats:
				</span>
				<span className="font-body-md text-body-md text-on-secondary-container">
					Total Memories: 1,284
				</span>
			</div>

			{/* Memory List */}
			<div className="flex flex-col">
				{memories.map((mem, i) => (
					<div
						key={i}
						className="h-10 group flex items-center justify-between px-sm hover:bg-surface-container-high transition-colors border-b border-outline-variant/10 cursor-pointer"
					>
						<div className="flex items-center gap-md flex-1 min-w-0">
							<div className={`w-[2px] h-4 ${mem.color}`} />
							<span className="font-label-md text-label-md text-primary w-48 truncate">
								{mem.title}
							</span>
							<span className="font-body-sm text-body-sm text-on-surface-variant truncate">
								{mem.preview}
							</span>
						</div>
						<div className="flex items-center gap-md opacity-0 group-hover:opacity-100 transition-opacity">
							<span className="font-label-sm text-label-sm text-on-surface-variant">
								{mem.time}
							</span>
							<button className="text-on-surface-variant hover:text-error transition-colors p-1">
								<span className="material-symbols-outlined text-[18px]">
									delete
								</span>
							</button>
						</div>
					</div>
				))}
			</div>
		</div>
	);
}

export default Memories;
