import { useState, useEffect, useCallback } from "react";
import {
	fetchDocuments,
	deleteDocument,
	deactivateDocument,
	activateDocument,
} from "../api";

function Documents() {
	const [docs, setDocs] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

	const loadDocuments = useCallback(() => {
		setLoading(true);
		setError(null);
		// Fetch active and deleted independently so a failure in one
		// does not discard successful results from the other.
		Promise.allSettled([
			fetchDocuments(),
			fetchDocuments({ status: "deleted" }),
		])
			.then(([activeResult, deletedResult]) => {
				const merged = [];
				const errors = [];
				if (activeResult.status === "fulfilled") {
					merged.push(...activeResult.value);
				} else {
					console.error("Active documents fetch failed:", activeResult.reason);
					errors.push("active");
				}
				if (deletedResult.status === "fulfilled") {
					merged.push(...deletedResult.value);
				} else {
					console.error(
						"Inactive documents fetch failed:",
						deletedResult.reason,
					);
				}
				setDocs(merged);
				if (errors.length === 2) {
					setError("Failed to load documents.");
				} else if (errors.length === 1) {
					setError(
						`Could not load ${errors[0]} documents — showing available data.`,
					);
				}
				setLoading(false);
			})
			.catch((err) => {
				console.error(err);
				setError("Failed to load documents.");
				setLoading(false);
			});
	}, []);

	useEffect(() => {
		loadDocuments();
	}, [loadDocuments]);

	const handleDeactivate = async (docId, e) => {
		e.stopPropagation();
		try {
			await deactivateDocument(docId);
			setDocs((prev) =>
				prev.map((d) => (d.id === docId ? { ...d, status: "deleted" } : d)),
			);
		} catch (err) {
			console.error(err);
		}
	};

	const handleActivate = async (docId, e) => {
		e.stopPropagation();
		try {
			await activateDocument(docId);
			setDocs((prev) =>
				prev.map((d) => (d.id === docId ? { ...d, status: "Ready" } : d)),
			);
		} catch (err) {
			console.error(err);
		}
	};

	const handleDelete = async (docId, e) => {
		e.stopPropagation();
		try {
			await deleteDocument(docId);
			// Remove from the local list immediately so the UI updates,
			// then refresh from the server to stay in sync.
			setDocs((prev) => prev.filter((d) => d.id !== docId));
			loadDocuments();
		} catch (err) {
			console.error(err);
			setError("Failed to delete document. Check console for details.");
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

	const activeDocs = docs.filter((d) => d.status !== "deleted");
	const inactiveDocs = docs.filter((d) => d.status === "deleted");

	return (
		<div className="pt-xl pb-xl px-margin max-w-[1200px] mx-auto w-full">
			{/* Header */}
			<div className="mb-lg flex flex-col md:flex-row justify-between items-start md:items-end gap-md">
				<div>
					<h1 className="font-display text-display text-primary">
						Document Library
					</h1>
				</div>
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
			</div>

			{/* Quick Stats */}
			<div className="mb-xl bg-secondary-container rounded py-sm px-md flex items-center gap-md">
				<span className="font-label-md text-label-md text-secondary uppercase tracking-wider">
					Quick Stats:
				</span>
				<span className="font-body-md text-body-md text-on-secondary-container">
					Active: {loading ? "..." : activeDocs.length}
				</span>
				<span className="font-body-md text-body-md text-on-secondary-container">
					Inactive: {loading ? "..." : inactiveDocs.length}
				</span>
				<button
					onClick={loadDocuments}
					className="ml-auto bg-brand-purple/20 border border-brand-purple/30 text-brand-purple px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs hover:bg-brand-purple/40 transition-colors"
					disabled={loading}
				>
					<span
						className={`material-symbols-outlined text-[14px] ${loading ? "animate-spin" : ""}`}
					>
						{loading ? "progress_activity" : "refresh"}
					</span>
					Refresh
				</button>
			</div>

			{loading && <div className="text-on-surface-variant">Loading...</div>}
			{error && <div className="text-error mb-lg">{error}</div>}

			{!loading && !error && (
				<>
					{/* Active Documents */}
					<section className="mb-xl">
						<h2 className="font-label-md text-label-md text-secondary uppercase tracking-wider mb-sm">
							Active Documents
						</h2>
						<div className="bg-surface-container-low border border-outline-variant/20 rounded overflow-hidden">
							{activeDocs.length === 0 ? (
								<div className="px-lg py-sm text-on-surface-variant italic">
									No active documents.
								</div>
							) : (
								activeDocs.map((doc) => (
									<div
										key={doc.id}
										className="group flex items-center bg-surface-container-low hover:bg-dusty-grape/20 transition-colors border-b border-lilac-ash/10 h-10"
									>
										<div className="flex items-center gap-md px-lg py-sm flex-1 min-w-0">
											<div className="w-[2px] h-4 shrink-0 bg-primary" />
											<span
												className="font-label-md text-label-md text-primary truncate max-w-[300px]"
												title={doc.file_name}
											>
												{doc.file_name}
											</span>
											<span className="font-body-sm text-body-sm text-on-surface-variant truncate">
												Chunks: {doc.chunk_count}
											</span>
										</div>
										<span className="font-code text-code text-on-surface-variant mr-sm whitespace-nowrap">
											{formatDate(doc.updated_at || doc.created_at)}
										</span>
										<div className="flex items-center gap-xs opacity-0 group-hover:opacity-100 transition-opacity mr-2 shrink-0">
											<button
												onClick={(e) => handleDeactivate(doc.id, e)}
												title="Deactivate document"
												className="hover:bg-surface-container-highest/50 p-1 rounded transition-colors"
											>
												<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-on-surface">
													archive
												</span>
											</button>
											<button
												onClick={(e) => handleDelete(doc.id, e)}
												title="Delete document"
												className="hover:bg-error/10 p-1 rounded transition-colors"
											>
												<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-error">
													delete
												</span>
											</button>
										</div>
									</div>
								))
							)}
						</div>
					</section>

					{/* Inactive Documents */}
					<section>
						<h2 className="font-label-md text-label-md text-on-surface-variant mb-sm uppercase tracking-wider">
							Inactive Documents
						</h2>
						<div className="bg-surface-container-lowest border border-outline-variant/20 rounded overflow-hidden opacity-80">
							{inactiveDocs.length === 0 ? (
								<div className="px-lg py-sm text-on-surface-variant italic">
									No inactive documents.
								</div>
							) : (
								inactiveDocs.map((doc) => (
									<div
										key={doc.id}
										className="group flex items-center bg-surface-container-lowest hover:bg-dusty-grape/10 transition-colors border-b border-lilac-ash/10 h-10"
									>
										<div className="flex items-center gap-md px-lg py-sm flex-1 min-w-0">
											<div className="w-[2px] h-4 shrink-0 bg-outline-variant" />
											<span
												className="font-label-md text-label-md text-on-surface-variant truncate max-w-[300px]"
												title={doc.file_name}
											>
												{doc.file_name}
											</span>
											<span className="font-body-sm text-body-sm text-on-surface-variant/70 truncate">
												Chunks: {doc.chunk_count}
											</span>
										</div>
										<span className="font-code text-code text-on-surface-variant/70 mr-sm whitespace-nowrap">
											{formatDate(doc.updated_at || doc.created_at)}
										</span>
										<div className="flex items-center gap-xs opacity-0 group-hover:opacity-100 transition-opacity mr-2 shrink-0">
											<button
												onClick={(e) => handleActivate(doc.id, e)}
												title="Activate document"
												className="hover:bg-surface-container-highest/50 p-1 rounded transition-colors"
											>
												<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-primary">
													unarchive
												</span>
											</button>
											<button
												onClick={(e) => handleDelete(doc.id, e)}
												title="Delete document"
												className="hover:bg-error/10 p-1 rounded transition-colors"
											>
												<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-error">
													delete
												</span>
											</button>
										</div>
									</div>
								))
							)}
						</div>
					</section>
				</>
			)}
		</div>
	);
}

export default Documents;
