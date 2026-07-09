const docs = [
	{
		title: "arch_diagram_v3.pdf",
		size: "2.4 MB",
		time: "2 hours ago",
		color: "bg-primary",
	},
	{
		title: "meeting_notes_q3.txt",
		size: "14 KB",
		time: "Yesterday",
		color: "bg-secondary",
	},
	{
		title: "user_data_export.csv",
		size: "8.1 MB",
		time: "Oct 12",
		color: "bg-tertiary",
	},
	{
		title: "ui_mockup_final.png",
		size: "1.2 MB",
		time: "Oct 10",
		color: "bg-primary-fixed-dim",
	},
];

function Documents() {
	return (
		<div className="pt-xl pb-xl px-margin max-w-[1200px] mx-auto w-full">
			{/* Header */}
			<div className="mb-lg flex flex-col md:flex-row justify-between items-start md:items-end gap-md">
				<div>
					<h1 className="font-display text-display text-primary">
						Document Library
					</h1>
				</div>
				<div className="flex items-center gap-md w-full md:w-auto">
					<div className="relative w-full md:w-96">
						<span className="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-outline">
							search
						</span>
						<input
							className="w-full bg-surface-container-high border border-outline-variant rounded text-on-surface pl-8 pr-sm py-sm font-body-md text-body-md focus:outline-none focus:border-primary focus:ring-0 transition-colors placeholder:text-on-surface-variant/50"
							placeholder="Search documents..."
							type="text"
						/>
					</div>
					<button className="bg-primary text-on-primary font-label-md text-label-md px-lg py-sm rounded hover:opacity-90 transition-opacity flex items-center gap-xs whitespace-nowrap">
						<span className="material-symbols-outlined text-[18px]">
							upload
						</span>
						Upload Documents
					</button>
				</div>
			</div>

			{/* Quick Stats */}
			<div className="mb-xl bg-secondary-container rounded py-sm px-md flex items-center">
				<span className="font-label-md text-label-md text-secondary uppercase tracking-wider mr-sm">
					Quick Stats:
				</span>
				<span className="font-body-md text-body-md text-on-secondary-container">
					Total Documents: 124
				</span>
			</div>

			{/* Document List */}
			<div className="flex flex-col">
				{docs.map((doc, i) => (
					<div
						key={i}
						className="h-10 group flex items-center justify-between px-sm hover:bg-surface-container-high transition-colors border-b border-outline-variant/10 cursor-pointer"
					>
						<div className="flex items-center gap-md flex-1 min-w-0">
							<div className={`w-[2px] h-4 ${doc.color}`} />
							<span className="font-label-md text-label-md text-primary w-48 truncate">
								{doc.title}
							</span>
							<span className="font-body-sm text-body-sm text-on-surface-variant truncate">
								{doc.size}
							</span>
						</div>
						<div className="flex items-center gap-md opacity-0 group-hover:opacity-100 transition-opacity">
							<span className="font-label-sm text-label-sm text-on-surface-variant">
								{doc.time}
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

export default Documents;
