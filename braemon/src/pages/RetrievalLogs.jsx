import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { fetchRetrievalLog } from "../api";

const COLS = [
	["#", "rank"],
	["File", "file_name"],
	["Chunk", "chunk_index"],
	["Similarity", "similarity_score"],
	["Reranker", "score"],
	["CrossEnc", "cross_encoder_score"],
	["Window", "window_expanded"],
	["InPrompt", "in_prompt"],
	["Mode", "retrieval_mode"],
];

function formatVal(key, chunk) {
	const v = chunk[key];
	if (v == null) return "\u2014";
	if (key === "window_expanded") return v ? "\u00b11" : "\u00b7";
	if (key === "in_prompt") return v ? "\ud83d\udfe2" : "\ud83d\udd34";
	if (
		key === "similarity_score" ||
		key === "score" ||
		key === "cross_encoder_score"
	) {
		return Number(v).toFixed(4);
	}
	return String(v);
}

export default function RetrievalLogs() {
	const { chatId, turnIndex } = useParams();
	const [chunks, setChunks] = useState([]);
	const [sortKey, setSortKey] = useState("rank");
	const [sortDir, setSortDir] = useState(1);
	const [expanded, setExpanded] = useState({});
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

	useEffect(() => {
		fetchRetrievalLog(chatId, turnIndex)
			.then(setChunks)
			.catch((e) => setError(e.message))
			.finally(() => setLoading(false));
	}, [chatId, turnIndex]);

	const sorted = [...chunks].sort((a, b) => {
		const av = a[sortKey] ?? 0;
		const bv = b[sortKey] ?? 0;
		return (av > bv ? 1 : -1) * sortDir;
	});

	const toggleSort = (key) => {
		if (sortKey === key) setSortDir(-sortDir);
		else {
			setSortKey(key);
			setSortDir(-1);
		}
	};

	if (loading) {
		return (
			<div style={{ padding: 32, color: "#888" }}>Loading retrieval log…</div>
		);
	}
	if (error) {
		return <div style={{ padding: 32, color: "#e55" }}>Error: {error}</div>;
	}

	return (
		<div style={{ padding: 24, maxWidth: "100%", overflow: "auto" }}>
			<h2 style={{ marginBottom: 16, color: "#e0e0ff" }}>
				Retrieval Log — Turn {turnIndex}
			</h2>
			<table
				style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}
			>
				<thead>
					<tr>
						{COLS.map(([label, key]) => (
							<th
								key={key}
								onClick={() => toggleSort(key)}
								style={{
									cursor: "pointer",
									padding: "8px 12px",
									background: "#1a1a2e",
									color: "#e0e0ff",
									textAlign: "left",
									borderBottom: "2px solid #6c63ff",
									whiteSpace: "nowrap",
								}}
							>
								{label} {sortKey === key ? (sortDir > 0 ? "▲" : "▼") : ""}
							</th>
						))}
					</tr>
				</thead>
				<tbody>
					{sorted.map((chunk, i) => (
						<>
							<tr
								key={i}
								onClick={() =>
									setExpanded((prev) => ({ ...prev, [i]: !prev[i] }))
								}
								style={{
									cursor: "pointer",
									background: i % 2 === 0 ? "#0f0f23" : "#1a1a2e",
									borderBottom: "1px solid #2a2a4a",
								}}
							>
								{COLS.map(([, key]) => (
									<td
										key={key}
										style={{
											padding: "6px 12px",
											color: "#ccc",
											whiteSpace: "nowrap",
										}}
									>
										{formatVal(key, chunk)}
									</td>
								))}
							</tr>
							{expanded[i] && (
								<tr>
									<td
										colSpan={COLS.length}
										style={{
											padding: "12px 16px",
											background: "#0a0a1a",
											color: "#aaa",
											fontSize: 12,
											lineHeight: 1.6,
											whiteSpace: "pre-wrap",
											borderBottom: "1px solid #333",
											maxHeight: 400,
											overflow: "auto",
										}}
									>
										{chunk.content}
									</td>
								</tr>
							)}
						</>
					))}
				</tbody>
			</table>
			{chunks.length === 0 && (
				<p style={{ color: "#888", padding: 32 }}>
					No document chunks in this turn.
				</p>
			)}
		</div>
	);
}
