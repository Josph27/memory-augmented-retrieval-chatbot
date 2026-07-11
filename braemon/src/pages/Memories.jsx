import { useState, useEffect } from "react";
import { fetchMemories, deleteMemory } from "../api";

export default function Memories() {
	const [expanded, setExpanded] = useState(null);
	const [memories, setMemories] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

	const loadMemories = () => {
		fetchMemories()
			.then((data) => {
				setMemories(data);
				setLoading(false);
			})
			.catch((err) => {
				console.error(err);
				setError("Failed to load memories.");
				setLoading(false);
			});
	};

	useEffect(() => {
		loadMemories();
	}, []);

	const handleDelete = async (memoryId, e) => {
		e.stopPropagation();
		if (!confirm("Are you sure you want to delete this memory?")) return;
		try {
			await deleteMemory(memoryId);
			loadMemories(); // Refresh after delete
		} catch (err) {
			console.error(err);
			alert("Failed to delete memory.");
		}
	};

	const formatDate = (ds) => {
		if (!ds) return "";
		return new Date(ds).toLocaleString(undefined, {
			month: "short",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		});
	};

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
					Total Memories: {loading ? "..." : memories.length}
				</span>
			</div>

			{loading && <div className="text-on-surface-variant">Loading...</div>}
			{error && <div className="text-red-400">{error}</div>}

			{!loading && !error && (
				<div className="flex flex-col">
					{memories.length === 0 ? (
						<div className="px-sm text-on-surface-variant italic">
							No memories found.
						</div>
					) : (
						memories.map((mem, i) => {
							const isExpanded = expanded === i;
							return (
								<div key={mem.memory_id || i}>
									{/* Summary row — always visible */}
									<div
										onClick={() => setExpanded(isExpanded ? null : i)}
										className={`group flex items-center justify-between px-sm hover:bg-surface-container-high transition-colors border-b border-outline-variant/10 cursor-pointer ${isExpanded ? "h-10" : "h-10"}`}
									>
										<div className="flex items-center gap-md flex-1 min-w-0">
											<div className={`w-[2px] h-4 shrink-0 bg-primary`} />
											<span
												className={`font-label-md text-label-md text-primary w-48 ${isExpanded ? "" : "truncate"}`}
											>
												{mem.category || mem.key}
											</span>
											<span
												className={`font-body-sm text-body-sm text-on-surface-variant ${isExpanded ? "hidden" : "truncate"}`}
											>
												{mem.value ? mem.value.slice(0, 80) + "..." : ""}
											</span>
										</div>
										<div className="flex items-center gap-md opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
											<span className="font-label-sm text-label-sm text-on-surface-variant">
												{formatDate(mem.updated_at || mem.created_at)}
											</span>
											<span
												className={`material-symbols-outlined text-[18px] text-on-surface-variant transition-transform ${isExpanded ? "rotate-180" : ""}`}
											>
												expand_more
											</span>
											<button
												className="text-on-surface-variant hover:text-error transition-colors p-1"
												onClick={(e) => handleDelete(mem.memory_id, e)}
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
												{mem.value}
											</p>
											<div className="mt-sm pt-sm border-t border-outline-variant/10 text-on-surface-variant font-code text-[12px]">
												<p>Confidence: {mem.confidence}</p>
												<p>Key: {mem.key}</p>
												<p>ID: {mem.memory_id}</p>
											</div>
										</div>
									)}
								</div>
							);
						})
					)}
				</div>
			)}
		</div>
	);
}
