import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";

const defaultMessages = [
	{
		role: "system",
		text: "Initialization sequence complete. Data streams successfully parsed from prior memory nodes. Awaiting command input to begin document analysis and synthesis.",
		docs: null,
	},
	{
		role: "user",
		text: "> pull latest architecture schematics\n> cross-reference with security protocols",
	},
	{
		role: "system",
		text: "Executing query. Schematics located in node `[SYS_ARCH_v2.4]`. Security cross-referencing indicates 3 potential vulnerabilities in the current auth flow. Would you like a detailed breakdown or a summary report?",
		docs: ["SYS_ARCH_v2.4.pdf", "SEC_PROTO_v1.2.md"],
	},
	{ role: "user", text: "> detailed breakdown of all 3 vulnerabilities" },
	{
		role: "system",
		text: "Vulnerability 1: Token injection in auth middleware — the JWT validation step does not verify the `alg` header, allowing an attacker to forge tokens using the `none` algorithm. Vulnerability 2: Session fixation via cookie reuse — session IDs are not rotated after login, enabling pre-existing cookies to be hijacked. Vulnerability 3: Insufficient rate limiting on the `/auth/reset` endpoint — allows brute-force enumeration of valid user accounts at up to 1,200 requests per minute. All three are classified as HIGH severity under OWASP Top 10 (2021).",
		docs: [
			"CVE-2024-1234.pdf",
			"OWASP_Top10_2021.pdf",
			"Pentest_Report_Q2.pdf",
		],
	},
	{ role: "user", text: "> what's the recommended remediation timeline?" },
	{
		role: "system",
		text: "Based on CVSS scores and exploitability metrics, the recommended remediation timeline is as follows: Vulnerability 1 (CVSS 9.8) — patch within 24 hours. The `alg: none` bypass is trivially exploitable and has been observed in active exploitation campaigns since March 2024. Vulnerability 2 (CVSS 7.5) — rotate all session tokens within 72 hours and deploy session rotation middleware. Vulnerability 3 (CVSS 6.5) — implement IP-based rate limiting within the current sprint cycle (2 weeks). I've prepared a patch diff for the JWT middleware. Would you like me to apply it to the staging environment?",
		docs: [
			"patch_jwt_middleware.diff",
			"Rate_Limiting_Implementation_Guide.md",
		],
	},
	{
		role: "user",
		text: "> yes, apply to staging and run the integration test suite",
	},
	{
		role: "system",
		text: "Patch applied to staging environment `api.staging.braemon.io`. Running integration test suite now... Tests 1-47 passed. Test 48 (JWT validation edge case) detected expected rejection of `alg: none` tokens. Test 49 (session rotation on login) passed — new tokens generated, old tokens invalidated. Test 50 (rate limit threshold) passed — endpoint now returns 429 after 5 attempts per minute. All 50 integration tests passed. Staging deployment verified. Ready for production promotion.",
		docs: null,
	},
	{ role: "user", text: "> excellent. promote to production." },
	{
		role: "system",
		text: "Promotion initiated. Blue-green deployment targeting `api.prod.braemon.io`. Health checks passing on new instances. Traffic shifting 10% → 50% → 100%. Production deployment complete. All monitors green — latency within SLA (p95 < 120ms), error rate 0.00%. Security patches are now live across all production nodes.",
		docs: ["Deployment_Log_2026-07-09.json", "Health_Check_Report.pdf"],
	},
];

const activeThreads = [
	"System Architecture Review v2",
	"Debug Stream: Auth Module Error",
	"Query Log Optimization",
];
const inactiveThreads = [
	"Database Migration Plan Assessment",
	"API Rate Limiting Logic Review",
	"Frontend Performance Audit 2024",
	"React Router V6 Integration Strategy",
	"Tailwind Custom Config Setup",
];

const slug = (s) =>
	s
		.toLowerCase()
		.replace(/\s+/g, "-")
		.replace(/[^a-z0-9-]/g, "");

const fakeReplies = [
	"Acknowledged. Processing your input through the retrieval pipeline. Relevant context nodes have been identified and are being ranked by semantic similarity.",
	"Query analyzed. The routing agent selected `semantic_v2` mode with [recent_messages, long_term_memories] as active sources. Cross-referencing against the document index now.",
	"I've cross-referenced your query against the indexed knowledge base. The top-ranked candidate is from the architecture documentation. Summarizing the key findings below.",
];

function Message({ msg }) {
	const isUser = msg.role === "user";
	return (
		<div className="w-full max-w-4xl mx-auto flex flex-col">
			<div className="text-label-sm text-on-surface-variant mb-1 flex items-center gap-xs">
				{isUser ? (
					<>
						USER_CMD{" "}
						<span className="material-symbols-outlined text-[14px]">
							person
						</span>
					</>
				) : (
					<>
						<span className="material-symbols-outlined text-[14px]">
							smart_toy
						</span>{" "}
						@RETRIEVAL_AGENT
					</>
				)}
			</div>
			<div
				className={
					isUser
						? "bg-surface-container border-t-[4px] border-r-[4px] border-almond-silk p-md border-b border-l border-outline-variant/20 rounded-sm"
						: "bg-surface-dim border-t-[4px] border-l-[4px] border-brand-purple p-md border-b border-r border-outline-variant/20 rounded-sm"
				}
			>
				<p
					className={`${isUser ? "font-code" : "font-body-md"} text-on-surface leading-relaxed whitespace-pre-wrap`}
				>
					{msg.text}
				</p>
				{msg.docs && (
					<div className="mt-sm pt-sm border-t border-outline-variant/20 flex flex-wrap gap-sm">
						{msg.docs.map((doc, j) => (
							<span
								key={j}
								className="bg-surface-container-high text-on-surface-variant px-sm py-1 rounded text-label-sm border border-outline-variant/30 flex items-center gap-1"
							>
								<span className="material-symbols-outlined text-[12px]">
									{doc.endsWith(".pdf") ? "description" : "security"}
								</span>
								{doc}
							</span>
						))}
					</div>
				)}
			</div>
		</div>
	);
}

export default function Chat() {
	const [messages, setMessages] = useState(defaultMessages);
	const [input, setInput] = useState("");
	const [inactiveOpen, setInactiveOpen] = useState(false);
	const scrollRef = useRef(null);
	const replyIdx = useRef(0);

	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, [messages]);

	const handleSend = () => {
		const text = input.trim();
		if (!text) return;
		const userMsg = { role: "user", text: `> ${text}` };
		setMessages((prev) => [...prev, userMsg]);
		setInput("");
		// Fake system reply after short delay
		setTimeout(() => {
			const reply = fakeReplies[replyIdx.current % fakeReplies.length];
			replyIdx.current++;
			setMessages((prev) => [
				...prev,
				{ role: "system", text: reply, docs: null },
			]);
		}, 600);
	};

	const newChat = () => {
		setMessages(defaultMessages);
		replyIdx.current = 0;
	};

	return (
		<div
			className="flex flex-col overflow-hidden"
			style={{ height: "calc(100vh - 3rem)", overscrollBehavior: "none" }}
		>
			<div className="flex-1 flex min-h-0">
				{/* Left Sidebar */}
				<aside className="bg-surface-container-low fixed left-0 top-12 bottom-0 w-64 border-r border-outline-variant/20 flex flex-col overflow-hidden">
					<div
						className="flex flex-col min-h-0"
						style={{ flex: inactiveOpen ? "1 1 auto" : "1 1 0%" }}
					>
						<div className="px-4 py-sm border-b border-outline-variant/20 shrink-0">
							<h2 className="text-headline-md font-bold text-primary text-[16px]">
								Active Threads
							</h2>
						</div>
						<div className="flex-1 overflow-y-auto px-2 py-sm">
							{activeThreads.map((title, i) => (
								<Link
									key={i}
									to={`/chat/${slug(title)}`}
									className={
										i === 0
											? "bg-secondary-container/30 text-secondary border-l-2 border-secondary px-3 py-2 flex items-center gap-sm transition-all duration-150 rounded-r text-[13px] no-underline"
											: "text-on-surface-variant px-3 py-2 hover:bg-surface-container-highest/50 transition-colors flex items-center gap-sm rounded-r text-[13px] no-underline"
									}
								>
									<span className="material-symbols-outlined text-[14px]">
										chat_bubble
									</span>
									<span className="truncate">{title}</span>
								</Link>
							))}
						</div>
					</div>
					<div
						className={`border-t border-outline-variant/20 shrink-0 ${inactiveOpen ? "flex flex-col min-h-0" : ""}`}
						style={inactiveOpen ? { flex: "0 1 50%" } : {}}
					>
						<button
							onClick={() => setInactiveOpen(!inactiveOpen)}
							className="w-full px-4 py-sm flex items-center justify-between hover:bg-surface-container-highest/30 transition-colors text-on-surface-variant"
						>
							<h2 className="text-headline-md font-bold text-[16px]">
								Inactive Threads
							</h2>
							<span
								className={`material-symbols-outlined text-[18px] transition-transform ${inactiveOpen ? "rotate-180" : ""}`}
							>
								expand_less
							</span>
						</button>
						{inactiveOpen && (
							<div className="flex-1 overflow-y-auto px-2 py-sm">
								{inactiveThreads.map((title, i) => (
									<Link
										key={i}
										to={`/chat/${slug(title)}`}
										className="text-on-surface-variant/70 px-3 py-2 hover:bg-surface-container-highest/30 transition-colors flex items-center gap-sm rounded-r text-[13px] no-underline"
									>
										<span className="material-symbols-outlined text-[14px]">
											history
										</span>
										<span className="truncate">{title}</span>
									</Link>
								))}
							</div>
						)}
					</div>
				</aside>

				{/* Main Chat Area */}
				<main className="flex-1 ml-64 flex flex-col bg-background">
					<div
						ref={scrollRef}
						className="flex-1 overflow-y-auto px-margin pt-sm pb-0 flex flex-col gap-sm min-h-0"
						style={{ overscrollBehavior: "none" }}
					>
						{messages.map((msg, i) => (
							<Message key={i} msg={msg} />
						))}
					</div>

					{/* Input Area */}
					<div className="shrink-0 w-full bg-surface/90 backdrop-blur-sm border-t border-outline-variant/20 p-margin">
						<div className="max-w-4xl mx-auto flex flex-col gap-sm">
							<div className="flex gap-sm items-center">
								<button
									className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs opacity-50 cursor-not-allowed"
									disabled
								>
									<span className="material-symbols-outlined text-[14px]">
										stop_circle
									</span>
									End Chat
								</button>
								<button
									className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs opacity-50 cursor-not-allowed"
									disabled
								>
									<span className="material-symbols-outlined text-[14px]">
										upload_file
									</span>
									Upload Doc
								</button>
								<button
									className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs opacity-50 cursor-not-allowed"
									disabled
								>
									<span className="material-symbols-outlined text-[14px]">
										call_split
									</span>
									Fork Chat
								</button>
								<button
									onClick={newChat}
									className="bg-almond-silk text-primary-container px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs"
								>
									<span className="material-symbols-outlined text-[14px]">
										add
									</span>
									New Chat
								</button>
							</div>
							<div className="relative flex items-center">
								<span className="material-symbols-outlined absolute left-sm text-on-surface-variant text-[20px]">
									terminal
								</span>
								<input
									className="w-full bg-surface-container-lowest border border-outline-variant/50 rounded-sm py-2 pl-10 pr-12 text-body-md text-on-surface placeholder:text-on-surface-variant/50 focus:border-almond-silk focus:ring-0 focus:outline-none transition-colors"
									placeholder="Enter command or natural language query..."
									value={input}
									onChange={(e) => setInput(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter" && !e.shiftKey) {
											e.preventDefault();
											handleSend();
										}
									}}
								/>
								<button
									onClick={handleSend}
									disabled={!input.trim()}
									className="absolute right-sm text-almond-silk hover:text-white transition-colors disabled:opacity-30"
								>
									<span className="material-symbols-outlined">send</span>
								</button>
							</div>
						</div>
					</div>
				</main>
			</div>
		</div>
	);
}
