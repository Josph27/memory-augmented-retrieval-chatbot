import { useState, useEffect, useCallback } from "react";
import {
	fetchMemories,
	deactivateMemory,
	activateMemory,
	deleteMemory,
} from "../api";

export default function Memories() {
	const [expanded, setExpanded] = useState(null);
	const [memories, setMemories] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

	const loadMemories = useCallback(() => {
		setLoading(true);
		// Fetch both active and deleted, then merge
		Promise.all([
			fetchMemories({ status: "active" }),
			fetchMemories({ status: "deleted" }),
		])
			.then(([active, deleted]) => {
				setMemories([...active, ...deleted]);
				setLoading(false);
			})
			.catch((err) => {
				console.error(err);
				setError("Failed to load memories.");
				setLoading(false);
			});
	}, []);

	useEffect(() => {
		loadMemories();
	}, [loadMemories]);

	const handleDeactivate = async (memoryId, e) => {
		e.stopPropagation();
		try {
			await deactivateMemory(memoryId);
			setMemories((prev) =>
				prev.map((m) =>
					m.memory_id === memoryId ? { ...m, status: "deleted" } : m,
				),
			);
		} catch (err) {
			console.error(err);
		}
	};

	const handleDelete = async (memoryId, e) => {
		e.stopPropagation();
		try {
			await deleteMemory(memoryId);
			loadMemories();
		} catch (err) {
			console.error(err);
		}
	};

	const handleActivate = async (memoryId, e) => {
		e.stopPropagation();
		try {
			await activateMemory(memoryId);
			setMemories((prev) =>
				prev.map((m) =>
					m.memory_id === memoryId ? { ...m, status: "active" } : m,
				),
			);
		} catch (err) {
			console.error(err);
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

	const activeMemories = memories.filter((m) => m.status !== "deleted");
	const inactiveMemories = memories.filter((m) => m.status === "deleted");

	const renderMemoryRow = (mem, _index, isActive) => {
		const globalIndex = isActive
			? activeMemories.indexOf(mem)
			: activeMemories.length + inactiveMemories.indexOf(mem);
		const isExpanded = expanded === globalIndex;

		return (
			<div key={mem.memory_id || globalIndex}>
				{/* Summary row — always visible */}
				<div
					onClick={() => setExpanded(isExpanded ? null : globalIndex)}
					className={`group flex items-center justify-between px-sm hover:bg-surface-container-high transition-colors border-b border-outline-variant/10 cursor-pointer h-10`}
				>
					<div className="flex items-center gap-md flex-1 min-w-0">
						<div
							className={`w-[2px] h-4 shrink-0 ${isActive ? "bg-primary" : "bg-outline-variant"}`}
						/>
						<span
							className={`font-label-md text-label-md ${isActive ? "text-primary" : "text-on-surface-variant"} w-48 truncate`}
						>
							{mem.category || mem.key}
						</span>
						<span className="font-body-sm text-body-sm text-on-surface-variant truncate">
							{mem.value ? mem.value.slice(0, 80) + "..." : ""}
						</span>
					</div>
					<div className="flex items-center gap-md shrink-0">
						<span className="font-label-sm text-label-sm text-on-surface-variant opacity-0 group-hover:opacity-100">
							{formatDate(mem.updated_at || mem.created_at)}
						</span>
						<span
							className={`material-symbols-outlined text-[18px] text-on-surface-variant transition-transform ${isExpanded ? "rotate-180" : ""}`}
						>
							expand_more
						</span>
						<div className="flex items-center gap-xs opacity-0 group-hover:opacity-100 transition-opacity">
							{isActive ? (
								<button
									onClick={(e) => handleDeactivate(mem.memory_id, e)}
									title="Deactivate memory"
									className="hover:bg-surface-container-highest/50 p-1 rounded transition-colors"
								>
									<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-on-surface">
										archive
									</span>
								</button>
							) : (
								<button
									onClick={(e) => handleActivate(mem.memory_id, e)}
									title="Activate memory"
									className="hover:bg-surface-container-highest/50 p-1 rounded transition-colors"
								>
									<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-primary">
										unarchive
									</span>
								</button>
							)}
							<button
								onClick={(e) => handleDelete(mem.memory_id, e)}
								title="Delete memory"
								className="hover:bg-error/10 p-1 rounded transition-colors"
							>
								<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-error">
									delete
								</span>
							</button>
						</div>
					</div>
				</div>

				{/* Expanded detail */}
				{isExpanded && (
					<div className="px-8 py-md border-b border-outline-variant/10 bg-surface-container-low/30">
						<p className="font-body-md text-body-md text-on-surface leading-relaxed whitespace-pre-wrap">
							{mem.value}
						</p>
						<div className="mt-sm pt-sm border-t border-outline-variant/10 text-on-surface-variant font-code text-[12px]">
							<p>Confidence: {mem.confidence}</p>
							<p>Key: {mem.key}</p>
							<p>ID: {mem.memory_id}</p>
							<p>Status: {mem.status}</p>
						</div>
					</div>
				)}
			</div>
		);
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

			<div className="mb-xl bg-secondary-container rounded py-sm px-md flex items-center gap-md">
				<span className="font-label-md text-label-md text-secondary uppercase tracking-wider">
					Quick Stats:
				</span>
				<span className="font-body-md text-body-md text-on-secondary-container">
					Active: {loading ? "..." : activeMemories.length}
				</span>
				<span className="font-body-md text-body-md text-on-secondary-container">
					Inactive: {loading ? "..." : inactiveMemories.length}
				</span>
			</div>

			{loading && <div className="text-on-surface-variant">Loading...</div>}
			{error && <div className="text-error mb-lg">{error}</div>}

			{!loading && !error && (
				<>
					{/* Active Memories */}
					<section className="mb-xl">
						<h2 className="font-label-md text-label-md text-secondary uppercase tracking-wider mb-sm">
							Active Memories
						</h2>
						<div className="bg-surface-container-low border border-outline-variant/20 rounded overflow-hidden">
							{activeMemories.length === 0 ? (
								<div className="px-lg py-sm text-on-surface-variant italic">
									No active memories.
								</div>
							) : (
								activeMemories.map((mem, i) => renderMemoryRow(mem, i, true))
							)}
						</div>
					</section>

					{/* Inactive Memories */}
					<section>
						<h2 className="font-label-md text-label-md text-on-surface-variant mb-sm uppercase tracking-wider">
							Inactive Memories
						</h2>
						<div className="bg-surface-container-lowest border border-outline-variant/20 rounded overflow-hidden opacity-80">
							{inactiveMemories.length === 0 ? (
								<div className="px-lg py-sm text-on-surface-variant italic">
									No inactive memories.
								</div>
							) : (
								inactiveMemories.map((mem, i) => renderMemoryRow(mem, i, false))
							)}
						</div>
					</section>
				</>
			)}
		</div>
	);
}
