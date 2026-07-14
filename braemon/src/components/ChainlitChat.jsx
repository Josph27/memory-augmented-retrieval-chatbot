import { useEffect, useRef, useState } from "react";
import {
	useChatSession,
	useChatMessages,
	useChatInteract,
	useChatData,
	sessionIdState,
} from "@chainlit/react-client";
import { useRecoilState } from "recoil";
import { endChat, forkChat } from "../api";
import { useNavigate } from "react-router-dom";
import { v4 as uuidv4 } from "uuid";

// ── Trace section builders ──

function formatValue(value) {
	if (value === null || value === undefined) return "—";
	if (typeof value === "boolean") return value ? "true" : "false";
	if (typeof value === "number") {
		if (Number.isInteger(value)) return value.toLocaleString();
		return value.toFixed(1);
	}
	return String(value);
}

function kvRows(obj, labels) {
	const rows = [];
	for (const [key, label] of Object.entries(labels)) {
		rows.push({ key: label, value: formatValue(obj[key]) });
	}
	return rows;
}

function overviewToRows(ov) {
	return kvRows(ov, {
		routingMode: "Routing mode",
		routingFallback: "Routing fallback",
		routeIntent: "Intent",
		confidence: "Confidence",
		contextProfile: "Context profile",
		enabledSources: "Enabled sources",
		orchestrationRequested: "Orch. requested",
		orchestrationEffective: "Orch. effective",
		orchestrationFallback: "Orch. fallback",
		evidenceContractSatisfied: "Evidence satisfied",
	});
}

function budgetToRows(tb) {
	return kvRows(tb, {
		nativeContextWindow: "Native window",
		systemPromptTokens: "System tokens",
		currentQueryTokens: "Query tokens",
		chatTemplateOverhead: "Template overhead",
		selectedMemoryTokens: "Memory tokens",
		finalPromptTokens: "Final prompt tokens",
	});
}

function funnelToRows(rf) {
	const rows = [
		{ key: "Retrieved", value: formatValue(rf.retrievedCount) },
		{ key: "Selected", value: formatValue(rf.selectedCount) },
	];
	if (rf.includedBySource && Object.keys(rf.includedBySource).length > 0) {
		rows.push({
			key: "By source",
			value: Object.entries(rf.includedBySource)
				.map(([s, c]) => `${s}: ${c}`)
				.join(", "),
		});
	}
	if (rf.droppedBySource && Object.keys(rf.droppedBySource).length > 0) {
		rows.push({
			key: "Dropped by source",
			value: Object.entries(rf.droppedBySource)
				.map(([s, c]) => `${s}: ${c}`)
				.join(", "),
		});
	}
	if (rf.documentFallback !== undefined && rf.documentFallback !== null) {
		rows.push({ key: "Doc fallback", value: formatValue(rf.documentFallback) });
	}
	return rows;
}

function timingsToRows(tm) {
	return kvRows(tm, {
		routePlanningMs: "Route planning",
		retrievalMs: "Retrieval",
		rerankingMs: "Reranking",
		budgetPlanningMs: "Budget planning",
		selectionMs: "Selection",
		langgraphOrchestrationMs: "LangGraph orch.",
		contextComparisonMs: "Context comparison",
		mainModelCallMs: "Model call",
		updateMemoryMs: "Memory update",
		totalTurnMs: "Total turn",
	}).filter((row) => row.value !== "—");
}

function configToRows(cfg) {
	return kvRows(cfg, {
		routingMode: "Routing mode",
		rerankerMode: "Reranker mode",
		orchestrationMode: "Orch. mode",
		memoryUpdatePolicy: "Memory policy",
		documentTopK: "Document top-K",
		gistExtractor: "Gist extractor",
		gistMaxMessagesPerGist: "Max msg/gist",
		chunkSize: "Chunk size",
		chunkOverlap: "Chunk overlap",
		embeddingModel: "Embedding model",
	});
}

function buildTraceSections(trace) {
	const sections = [];

	// Section 1: Turn Overview
	if (trace.turnOverview) {
		sections.push({
			label: "Turn Overview",
			kvRows: overviewToRows(trace.turnOverview),
		});
	}

	// Section 2: Token Budget
	if (trace.tokenBudget) {
		sections.push({
			label: "Token Budget",
			kvRows: budgetToRows(trace.tokenBudget),
		});
	}

	// Section 3: Retrieval Funnel
	if (trace.retrievalFunnel) {
		const funnelSection = {
			label: "Retrieval Funnel",
			kvRows: funnelToRows(trace.retrievalFunnel),
		};
		const droppedReasons = trace.retrievalFunnel.droppedReasons;
		if (Array.isArray(droppedReasons) && droppedReasons.length > 0) {
			funnelSection.dropReasons = droppedReasons;
		}
		const funnelSections = [funnelSection];
		if (
			Array.isArray(trace.retrievalFunnel.retrievalErrors) &&
			trace.retrievalFunnel.retrievalErrors.length > 0
		) {
			funnelSections.push({
				label: "Retrieval Errors",
				items: trace.retrievalFunnel.retrievalErrors,
			});
		}
		sections.push(...funnelSections);
	}

	// Section 4: Selected Evidence (existing)
	if (Array.isArray(trace.retrieved) && trace.retrieved.length > 0) {
		sections.push({
			label: "Selected Evidence",
			rows: trace.retrieved,
			tokenCostCol: trace.retrieved.some((r) => r.tokenCost !== undefined),
		});
	}

	// Section 5: Saved Memories (existing)
	if (Array.isArray(trace.saved) && trace.saved.length > 0) {
		sections.push({ label: "Saved Memories", rows: trace.saved });
	}

	// Section 6: Timing
	if (trace.timing) {
		const timingRows = timingsToRows(trace.timing);
		if (timingRows.length > 0) {
			sections.push({
				label: "Timing (ms)",
				kvRows: timingRows,
			});
		}
	}

	// Section 7: Config Snapshot
	if (trace.configSnapshot) {
		sections.push({
			label: "Config Snapshot",
			kvRows: configToRows(trace.configSnapshot),
		});
	}

	// Backward compat: old orchestration string (only if no turnOverview)
	if (!trace.turnOverview && trace.orchestration) {
		sections.push({
			label: "Orchestration",
			text: String(trace.orchestration),
		});
	}

	// Backward compat: old retrieval_errors key (only if no retrievalFunnel)
	if (
		!trace.retrievalFunnel &&
		Array.isArray(trace.retrieval_errors) &&
		trace.retrieval_errors.length > 0
	) {
		sections.push({
			label: "Retrieval Errors",
			items: trace.retrieval_errors,
		});
	}

	return sections;
}

// ── Trace section rendering helpers ──

function DropReasons({ reasons }) {
	const [open, setOpen] = useState(false);
	if (!reasons || reasons.length === 0) return null;
	return (
		<div className="mt-xs">
			<button
				onClick={() => setOpen(!open)}
				className="text-label-sm text-on-surface-variant/60 hover:text-on-surface-variant transition-colors flex items-center gap-xs"
			>
				<span className="material-symbols-outlined text-[12px]">
					{open ? "expand_less" : "expand_more"}
				</span>
				Drop reasons ({reasons.length})
			</button>
			{open && (
				<div className="mt-xs ml-sm text-code text-[12px] leading-tight space-y-0.5">
					{reasons.map((d, i) => (
						<div key={i} className="text-on-surface-variant/70">
							{d.source}/{d.reason}: {d.count}
						</div>
					))}
				</div>
			)}
		</div>
	);
}

function SectionBlock({ section, bordered = false }) {
	return (
		<div
			className={`mb-md ${bordered ? "border-r border-outline-variant/10 pr-md" : ""}`}
		>
			<div className="text-label-sm text-on-surface-variant font-bold mb-xs uppercase tracking-wider">
				{section.label}
			</div>
			{section.text && (
				<pre className="text-code text-on-surface-variant whitespace-pre-wrap bg-surface-container-lowest p-sm rounded-sm text-[12px] leading-tight">
					{section.text}
				</pre>
			)}
			{section.kvRows && (
				<div className="grid grid-cols-[minmax(0,160px)_1fr] gap-x-sm gap-y-0 text-code text-[12px] leading-tight">
					{section.kvRows.map((row, j) => (
						<div key={j} className="contents">
							<div
								className="py-xs pr-sm text-on-surface-variant/70 truncate"
								title={row.key}
							>
								{row.key}
							</div>
							<div className="py-xs text-on-surface-variant truncate">
								{row.value}
							</div>
						</div>
					))}
				</div>
			)}
			{section.dropReasons && <DropReasons reasons={section.dropReasons} />}
			{section.rows && (
				<table className="w-full text-code text-[12px] leading-tight border-collapse">
					<thead>
						<tr className="border-b border-outline-variant/30">
							{Object.keys(section.rows[0] || {})
								.slice(0, 8)
								.map((k) => (
									<th
										key={k}
										className="text-left text-on-surface-variant/70 font-normal py-xs pr-sm whitespace-nowrap"
									>
										{k}
									</th>
								))}
						</tr>
					</thead>
					<tbody>
						{section.rows.map((row, j) => (
							<tr
								key={j}
								className="border-b border-outline-variant/10 hover:bg-surface-container-high/50"
							>
								{Object.values(row)
									.slice(0, 8)
									.map((val, k) => (
										<td
											key={k}
											className="py-xs pr-sm text-on-surface-variant max-w-[300px] truncate"
										>
											{typeof val === "string" && val.length > 100
												? val.slice(0, 100) + "..."
												: String(val ?? "")}
										</td>
									))}
							</tr>
						))}
					</tbody>
				</table>
			)}
			{section.items && (
				<ul className="text-code text-[12px] text-on-surface-variant leading-tight space-y-xs list-disc pl-md">
					{section.items.map((item, j) => (
						<li key={j} className="bg-surface-container-lowest p-sm rounded-sm">
							{String(item)}
						</li>
					))}
				</ul>
			)}
		</div>
	);
}

function SectionPair({ left, right }) {
	if (!left && !right) return null;
	if (!right) return <SectionBlock section={left} />;
	if (!left) return <SectionBlock section={right} />;
	return (
		<div className="border-b border-outline-variant/10 mb-md">
			<div className="grid grid-cols-2 gap-md">
				<SectionBlock section={left} bordered />
				<SectionBlock section={right} />
			</div>
		</div>
	);
}

function TraceContent({ sections }) {
	const byLabel = {};
	for (const s of sections) {
		byLabel[s.label] = s;
	}

	const hasConfig = !!byLabel["Config Snapshot"];
	const hasEvidenceBelow =
		!!byLabel["Selected Evidence"] ||
		!!byLabel["Saved Memories"] ||
		!!byLabel["Orchestration"] ||
		!!byLabel["Retrieval Errors"];

	return (
		<>
			<SectionPair
				left={byLabel["Turn Overview"]}
				right={byLabel["Timing (ms)"]}
			/>
			<SectionPair
				left={byLabel["Token Budget"]}
				right={byLabel["Retrieval Funnel"]}
			/>
			{hasConfig && (
				<div
					className={
						hasEvidenceBelow ? "border-b border-outline-variant/10 mb-md" : ""
					}
				>
					<SectionBlock section={byLabel["Config Snapshot"]} />
				</div>
			)}
			{byLabel["Selected Evidence"] && (
				<SectionBlock section={byLabel["Selected Evidence"]} />
			)}
			{byLabel["Saved Memories"] && (
				<SectionBlock section={byLabel["Saved Memories"]} />
			)}
			{byLabel["Orchestration"] && (
				<SectionBlock section={byLabel["Orchestration"]} />
			)}
			{byLabel["Retrieval Errors"] && (
				<SectionBlock section={byLabel["Retrieval Errors"]} />
			)}
		</>
	);
}

// ── Message component ──

function Message({ msg }) {
	const isUser = msg.type === "user_message";
	const isError = typeof msg.id === "string" && msg.id.startsWith("error:");
	const isIndexed = typeof msg.id === "string" && msg.id.startsWith("indexed:");

	// Trace is pre-extracted from <!--breamon-trace:...--> at the flatMessages
	// level and stored in msg.metadata.trace.  The output string is already clean.
	const displayText = msg.output || "";
	const trace = msg.metadata?.trace || null;

	// Use msg.id — the Chainlit database message ID — as the localStorage
	// key component.  It is a required string field on IStep and is stable
	// across page reloads.  msg.createdAt changes format (number vs string)
	// between WebSocket streaming and REST reload, so it cannot be relied
	// on for cross-session persistence.
	const storageKey = `breamon-expanded-${msg.id}`;
	const [expanded, setExpanded] = useState(() => {
		try {
			return localStorage.getItem(storageKey) === "1";
		} catch {
			return false;
		}
	});

	const toggleExpanded = () => {
		setExpanded((prev) => {
			const next = !prev;
			try {
				localStorage.setItem(storageKey, next ? "1" : "0");
			} catch {}
			return next;
		});
	};

	const traceSections = trace ? buildTraceSections(trace) : [];

	return (
		<div
			className={`w-full max-w-4xl mx-auto flex flex-col ${isUser ? "translate-x-[20px]" : isError || isIndexed ? "" : "-translate-x-[20px]"}`}
		>
			{isIndexed ? (
				<div className="bg-brand-purple text-white px-md py-sm rounded-sm flex items-center gap-sm font-label-md text-label-md">
					<span className="material-symbols-outlined text-[18px]">
						check_circle
					</span>
					{displayText}
				</div>
			) : (
				<>
					{isError && (
						<div className="flex items-center gap-xs mb-1">
							<span className="material-symbols-outlined text-[16px] text-brand-purple">
								error
							</span>
							<span className="text-label-sm text-brand-purple font-bold uppercase tracking-wider">
								ERROR:
							</span>
						</div>
					)}
					<div
						className={
							isError
								? "bg-surface-dim border-[4px] border-brand-purple p-md rounded-sm"
								: isIndexed
									? "bg-brand-purple text-white px-md py-sm rounded-sm"
									: traceSections.length > 0
										? "bg-surface-dim border-l-[4px] border-brand-purple p-md rounded-tl-sm border-t-outline-variant/40 border-r-outline-variant/40 rounded-tr-sm"
										: isUser
											? "bg-surface-container border-r-[4px] border-almond-silk p-md border-t-outline-variant/40 border-b-outline-variant/40 border-l-outline-variant/40 rounded-sm"
											: "bg-surface-dim border-l-[4px] border-brand-purple p-md border-t-outline-variant/40 border-b-outline-variant/40 border-r-outline-variant/40 rounded-sm"
						}
					>
						<p
							className={`${isUser ? "font-code text-right" : "font-body-md"} text-on-surface leading-relaxed whitespace-pre-wrap`}
						>
							{displayText}
						</p>
						{msg.elements && msg.elements.length > 0 && (
							<div className="mt-sm pt-sm border-t border-outline-variant/20 flex flex-wrap gap-sm">
								{msg.elements.map((doc, j) => (
									<span
										key={doc.id || j}
										className="bg-surface-container-high text-on-surface-variant px-sm py-1 rounded text-label-sm border border-outline-variant/30 flex items-center gap-1"
										title={doc.name}
									>
										<span className="material-symbols-outlined text-[12px]">
											{doc.name?.endsWith(".pdf") ? "description" : "draft"}
										</span>
										{doc.name}
									</span>
								))}
							</div>
						)}
					</div>
					{traceSections.length > 0 && (
						<div className="border-t-[3px] border-almond-silk bg-surface-dim rounded-b-sm border-b border-r border-l border-outline-variant/20">
							<button
								onClick={toggleExpanded}
								className="w-full flex items-center justify-between px-md py-xs text-label-sm text-almond-silk hover:text-white transition-colors select-none"
							>
								<span>system info</span>
								<span className="material-symbols-outlined text-[14px]">
									{expanded ? "expand_less" : "expand_more"}
								</span>
							</button>
							{expanded && (
								<div className="px-md pb-md max-h-[32rem] overflow-y-auto custom-scrollbar">
									<TraceContent sections={traceSections} />
								</div>
							)}
						</div>
					)}
				</>
			)}
		</div>
	);
}

export default function ChainlitChat({ chatId, onConsolidate }) {
	const { setIdToResume, sendMessage, uploadFile } = useChatInteract();
	const { connect, disconnect, idToResume } = useChatSession();
	const { messages } = useChatMessages();
	const { loading, connected } = useChatData();
	const [sessionId, setSessionId] = useRecoilState(sessionIdState);
	const [targetSessionId] = useState(() => uuidv4());
	const [input, setInput] = useState("");
	const [attachedFile, setAttachedFile] = useState(null);
	const fileInputRef = useRef(null);
	const scrollRef = useRef(null);
	const hasConnected = useRef(false);
	const loadingStart = useRef(null);
	const [elapsed, setElapsed] = useState(0);
	const [processingStage, setProcessingStage] = useState("indexing");
	const processingLabel = loading
		? processingStage === "indexing"
			? "Indexing files"
			: "Generating answer"
		: null;
	const navigate = useNavigate();

	// Listen for processing-stage window messages from the backend
	useEffect(() => {
		const handler = (event) => {
			const data = event.data;
			if (
				data?.command === "processing-stage" &&
				data?.source === "memory-chatbot-ui"
			) {
				setProcessingStage(data.stage || "indexing");
			}
		};
		window.addEventListener("message", handler);
		return () => window.removeEventListener("message", handler);
	}, []);

	useEffect(() => {
		if (hasConnected.current) return;

		let pendingUpdate = false;

		if (sessionId !== targetSessionId) {
			setSessionId(targetSessionId);
			pendingUpdate = true;
		}

		if (chatId && idToResume !== chatId) {
			setIdToResume(chatId);
			pendingUpdate = true;
		}
		if (!chatId && idToResume) {
			setIdToResume(undefined);
			pendingUpdate = true;
		}

		if (pendingUpdate) return; // Wait for Recoil state to sync

		hasConnected.current = true;
		connect({ userEnv: {} });

		return () => {
			if (connect && typeof connect.cancel === "function") {
				connect.cancel();
			}
			disconnect();
		};
	}, [
		chatId,
		idToResume,
		setIdToResume,
		connect,
		disconnect,
		sessionId,
		targetSessionId,
		setSessionId,
	]);

	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, [messages]);

	useEffect(() => {
		if (loading) {
			setProcessingStage("indexing");
			if (!loadingStart.current) loadingStart.current = Date.now();
			const interval = setInterval(() => {
				setElapsed(Math.round((Date.now() - loadingStart.current) / 1000));
			}, 500);
			return () => clearInterval(interval);
		} else {
			loadingStart.current = null;
			setElapsed(0);
		}
	}, [loading]);

	const handleSend = () => {
		const text = input.trim();
		// Block if file is still uploading
		if (attachedFile && !attachedFile.fileRef && !attachedFile.error) return;

		if (!text && !attachedFile?.fileRef) return;

		const fileRefs = attachedFile?.fileRef ? [attachedFile.fileRef] : [];
		sendMessage(
			{ type: "user_message", output: text || "", name: "user" },
			fileRefs,
		);

		setInput("");
		setAttachedFile(null);
	};

	const handleFileChange = (e) => {
		const file = e.target.files?.[0];
		if (!file) return;

		setAttachedFile({ file, progress: 0, fileRef: null, error: null });

		const { promise } = uploadFile(file, (progress) => {
			setAttachedFile((prev) => (prev ? { ...prev, progress } : null));
		});

		promise
			.then((fileRef) => {
				setAttachedFile((prev) =>
					prev ? { ...prev, fileRef, progress: 100 } : null,
				);
			})
			.catch((error) => {
				console.error("Upload failed:", error?.message || error);
				setAttachedFile((prev) =>
					prev ? { ...prev, error: "Upload failed" } : null,
				);
			});

		// Reset input to allow re-selecting the same file
		if (fileInputRef.current) {
			fileInputRef.current.value = "";
		}
	};

	const handleConsolidate = () => {
		if (!chatId) return;
		onConsolidate?.(chatId);
	};

	const handleEndChat = async () => {
		if (!chatId) return;
		try {
			await endChat(chatId);
			navigate(`/chats`);
		} catch (err) {
			console.error(err);
			alert("Failed to end chat");
		}
	};

	const handleForkChat = async () => {
		if (!chatId) return;
		try {
			const { chat_id } = await forkChat(chatId);
			navigate(`/chat/${chat_id}`);
		} catch (err) {
			console.error(err);
			alert("Failed to fork chat");
		}
	};

	const flatMessages = [];
	const flatten = (msgs) => {
		msgs.forEach((m) => {
			if (Array.isArray(m.steps) && m.steps.length > 0) {
				flatten(m.steps);
			}
			if (m.output || m.elements?.length > 0) {
				flatMessages.push(m);
			}
		});
	};
	flatten(messages);

	// Sort by createdAt to fix streaming race conditions where Chainlit
	// delivers assistant messages before the user echo for the same turn.
	// The IStep type carries createdAt: number | string during live WebSocket
	// streaming.  After reload, the REST API returns correct createdAt order
	// so the stable sort is a no-op.
	//
	// Primary sort: createdAt timestamp (preserves multi-turn order).
	// Secondary sort: user messages before assistant (tiebreaker when
	// timestamps are equal or missing — e.g. partial streaming states).
	flatMessages.sort((a, b) => {
		const parseTs = (v) => {
			if (typeof v === "number") return v;
			if (typeof v === "string") return Date.parse(v) || 0;
			return 0;
		};
		const ta = parseTs(a.createdAt);
		const tb = parseTs(b.createdAt);
		if (ta !== tb) return ta - tb;
		// Same timestamp — user messages before assistant/system
		if (a.type === "user_message" && b.type !== "user_message") return -1;
		if (a.type !== "user_message" && b.type === "user_message") return 1;
		return 0;
	});

	// Strip breamon-trace HTML comments from EVERY message's output so they
	// never appear as visible text, even if Chainlit's internal markdown
	// renderer escapes or otherwise surfaces them.
	// Also extract the trace JSON into msg.metadata so the dropdown still works.
	for (const msg of flatMessages) {
		if (msg.output && /<!--breamon-trace:/.test(msg.output)) {
			const m = msg.output.match(/<!--breamon-trace:([\s\S]*?)-->/);
			if (m) {
				try {
					if (!msg.metadata) msg.metadata = {};
					msg.metadata.trace = JSON.parse(m[1]);
				} catch {
					/* malformed JSON — ignore */
				}
				msg.output = msg.output
					.replace(/<!--breamon-trace:[\s\S]*?-->/, "")
					.trim();
			}
		}
	}
	return (
		<div className="flex flex-col h-full bg-background w-full">
			{/* Messages Area */}
			<div
				ref={scrollRef}
				className="flex-1 overflow-y-auto px-margin pt-sm pb-0 flex flex-col gap-[12px] min-h-0"
				style={{ overscrollBehavior: "none" }}
			>
				{!connected && !loading && (
					<div className="text-on-surface-variant italic text-center mt-xl">
						Connecting to chat server...
					</div>
				)}
				{flatMessages.map((msg) => (
					<Message key={msg.id} msg={msg} />
				))}
				{loading && (
					<div className="flex items-center gap-sm text-on-surface-variant pl-md max-w-4xl mx-auto w-full font-body-md">
						<span className="material-symbols-outlined animate-spin text-[18px] text-brand-purple">
							progress_activity
						</span>
						<span>{processingLabel}</span>
						<span className="inline-flex">
							<span className="animate-[pulse_1s_ease-in-out_infinite]">.</span>
							<span className="animate-[pulse_1s_ease-in-out_0.2s_infinite]">
								.
							</span>
							<span className="animate-[pulse_1s_ease-in-out_0.4s_infinite]">
								.
							</span>
						</span>
						<span className="text-on-surface-variant/50">({elapsed}s)</span>
					</div>
				)}
			</div>

			{/* Input Area */}
			<div className="shrink-0 w-full bg-surface/90 backdrop-blur-sm border-t border-outline-variant/20 p-margin">
				<div className="max-w-4xl mx-auto flex flex-col gap-sm">
					<div className="flex gap-sm items-center">
						<button
							onClick={handleEndChat}
							disabled={!connected || loading}
							className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs hover:bg-dusty-grape/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<span className="material-symbols-outlined text-[14px]">
								stop_circle
							</span>
							End Chat
						</button>
						<button
							onClick={() => fileInputRef.current?.click()}
							disabled={!connected || loading}
							className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs hover:bg-dusty-grape/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<span className="material-symbols-outlined text-[14px]">
								upload_file
							</span>
							Upload Doc
						</button>
						<input
							type="file"
							ref={fileInputRef}
							style={{ display: "none" }}
							onChange={handleFileChange}
						/>
						<button
							onClick={handleForkChat}
							disabled={!connected || loading}
							className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs hover:bg-dusty-grape/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<span className="material-symbols-outlined text-[14px]">
								call_split
							</span>
							Fork Chat
						</button>
						<button
							onClick={handleConsolidate}
							disabled={!connected || loading}
							className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs hover:bg-dusty-grape/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<span className="material-symbols-outlined text-[14px]">
								psychology
							</span>
							Consolidate
						</button>
					</div>
					{attachedFile && (
						<div className="flex items-center justify-between bg-surface-container-high border border-outline-variant/30 rounded-sm px-sm py-xs mb-xs">
							<div className="flex items-center gap-xs">
								<span className="material-symbols-outlined text-[14px] text-on-surface-variant">
									description
								</span>
								<span className="font-label-sm text-on-surface text-sm truncate max-w-[200px]">
									{attachedFile.file.name}
								</span>
								{!attachedFile.fileRef && !attachedFile.error && (
									<span className="text-xs text-almond-silk ml-2">
										{Math.round(attachedFile.progress)}%
									</span>
								)}
								{attachedFile.error && (
									<span className="text-xs text-error ml-2">Failed</span>
								)}
							</div>
							<button
								onClick={() => setAttachedFile(null)}
								className="text-on-surface-variant hover:text-error transition-colors"
							>
								<span className="material-symbols-outlined text-[16px]">
									close
								</span>
							</button>
						</div>
					)}
					<div className="relative flex items-center">
						<span className="material-symbols-outlined absolute left-sm text-on-surface-variant text-[20px]">
							terminal
						</span>
						<input
							className="w-full bg-surface-container-lowest border border-outline-variant/50 rounded-sm py-2 pl-10 pr-12 text-body-md text-on-surface placeholder:text-on-surface-variant/50 focus:border-almond-silk focus:ring-0 focus:outline-none transition-colors"
							placeholder="Enter prompt text..."
							value={input}
							onChange={(e) => setInput(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter" && !e.shiftKey) {
									e.preventDefault();
									handleSend();
								}
							}}
							disabled={!connected}
						/>
						<button
							onClick={handleSend}
							disabled={!input.trim() || !connected || loading}
							className="absolute right-sm text-almond-silk hover:text-white transition-colors disabled:opacity-30"
						>
							<span className="material-symbols-outlined">send</span>
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}
