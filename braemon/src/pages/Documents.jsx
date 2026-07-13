import { useState, useEffect, useRef, useCallback } from "react";
import { fetchDocuments, uploadDocumentFile, deleteDocument } from "../api";

function Documents() {
	const [docs, setDocs] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const [uploading, setUploading] = useState(false);
	const [uploadProgress, setUploadProgress] = useState(0);
	const [uploadError, setUploadError] = useState(null);
	const fileInputRef = useRef(null);

	useEffect(() => {
		fetchDocuments()
			.then((data) => {
				setDocs(data);
				setLoading(false);
			})
			.catch((err) => {
				console.error(err);
				setError("Failed to load documents.");
				setLoading(false);
			});
	}, []);

	const loadDocuments = useCallback(() => {
		fetchDocuments()
			.then(setDocs)
			.catch((err) => console.error(err));
	}, []);

	const handleDelete = useCallback(
		async (docId, e) => {
			e.stopPropagation();
			try {
				await deleteDocument(docId);
				loadDocuments();
			} catch (err) {
				console.error(err);
				alert("Failed to delete document.");
			}
		},
		[loadDocuments],
	);

	const handleUpload = useCallback(
		async (e) => {
			const file = e.target.files?.[0];
			if (!file) return;
			setUploading(true);
			setUploadProgress(0);
			setUploadError(null);
			try {
				await uploadDocumentFile(file, setUploadProgress);
				setUploading(false);
				loadDocuments();
			} catch (err) {
				setUploadError(err?.message || "Upload failed");
				setUploading(false);
			}
			// Reset input for re-selection
			if (fileInputRef.current) fileInputRef.current.value = "";
		},
		[loadDocuments],
	);

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
					<input
						type="file"
						ref={fileInputRef}
						style={{ display: "none" }}
						onChange={handleUpload}
					/>
					<button
						onClick={() => fileInputRef.current?.click()}
						disabled={uploading}
						className="bg-primary text-on-primary font-label-md text-label-md px-lg py-sm rounded hover:opacity-90 transition-opacity flex items-center gap-xs whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<span className="material-symbols-outlined text-[18px]">
							{uploading ? "hourglass_top" : "upload"}
						</span>
						{uploading
							? `Uploading ${Math.round(uploadProgress)}%`
							: "Upload Documents"}
					</button>
				</div>
			</div>

			{/* Upload error */}
			{uploadError && (
				<div className="mb-lg bg-error/10 border border-error/30 rounded py-sm px-md text-error text-body-sm">
					{uploadError}
				</div>
			)}

			{/* Quick Stats */}
			<div className="mb-xl bg-secondary-container rounded py-sm px-md flex items-center">
				<span className="font-label-md text-label-md text-secondary uppercase tracking-wider mr-sm">
					Quick Stats:
				</span>
				<span className="font-body-md text-body-md text-on-secondary-container">
					Total Documents: {loading ? "..." : docs.length}
				</span>
			</div>

			{/* Document List */}
			{loading && <div className="text-on-surface-variant">Loading...</div>}
			{error && <div className="text-red-400">{error}</div>}
			{!loading && !error && (
				<div className="flex flex-col">
					{docs.length === 0 ? (
						<div className="px-sm text-on-surface-variant italic">
							No documents found.
						</div>
					) : (
						docs.map((doc, i) => (
							<div
								key={i}
								className="h-10 group flex items-center justify-between px-sm hover:bg-surface-container-high transition-colors border-b border-outline-variant/10 cursor-pointer"
							>
								<div className="flex items-center gap-md flex-1 min-w-0">
									<div
										className={`w-[2px] h-4 ${doc.status === "Ready" ? "bg-primary" : "bg-secondary"}`}
									/>
									<span
										className="font-label-md text-label-md text-primary w-48 truncate"
										title={doc.file_name}
									>
										{doc.file_name}
									</span>
									<span className="font-body-sm text-body-sm text-on-surface-variant truncate">
										Chunks: {doc.chunk_count}
									</span>
									<span className="font-body-sm text-body-sm text-on-surface-variant truncate">
										Status: {doc.status}
									</span>
								</div>
								<div className="flex items-center gap-md opacity-0 group-hover:opacity-100 transition-opacity">
									<span className="font-label-sm text-label-sm text-on-surface-variant">
										{formatDate(doc.updated_at || doc.created_at)}
									</span>
									<button
										onClick={(e) => handleDelete(doc.id, e)}
										className="text-on-surface-variant p-1 hover:bg-error/10 rounded transition-colors"
										title="Delete document"
									>
										<span className="material-symbols-outlined text-[18px]">
											delete
										</span>
									</button>
								</div>
							</div>
						))
					)}
				</div>
			)}
		</div>
	);
}

export default Documents;
