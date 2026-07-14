import { useParams, Link, useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback, useRef } from "react";
import ChainlitChat from "../components/ChainlitChat";
import ChatActions from "../components/ChatActions";
import { fetchChats, createChat, consolidateChat } from "../api";

export default function Chat() {
	const { chatId } = useParams();
	const navigate = useNavigate();
	const [chats, setChats] = useState([]);
	const [inactiveOpen, setInactiveOpen] = useState(false);
	const [consolidating, setConsolidating] = useState(false);
	const [consolidateError, setConsolidateError] = useState(null);
	const consolidateTimeoutRef = useRef(null);

	const refreshChats = useCallback(() => {
		fetchChats({ limit: 50 }).then(setChats).catch(console.error);
	}, []);

	useEffect(() => {
		refreshChats();
	}, [chatId, refreshChats]);

	const handleStateChange = useCallback((id, active) => {
		setChats((prev) => prev.map((c) => (c.id === id ? { ...c, active } : c)));
	}, []);

	const handleNewChat = async () => {
		try {
			const { chat_id } = await createChat();
			navigate(`/chat/${chat_id}`);
		} catch (err) {
			console.error(err);
		}
	};

	const handleConsolidate = async (targetChatId) => {
		const cid = targetChatId || chatId;
		if (!cid) return;

		setConsolidating(true);
		setConsolidateError(null);

		const timeoutPromise = new Promise((_, reject) => {
			consolidateTimeoutRef.current = setTimeout(() => {
				reject(
					new Error(
						"Memory consolidation timed out after 30 seconds — the model may be unresponsive.",
					),
				);
			}, 30000);
		});

		try {
			await Promise.race([consolidateChat(cid), timeoutPromise]);
		} catch (err) {
			setConsolidateError(err.message || "Memory consolidation failed");
		} finally {
			clearTimeout(consolidateTimeoutRef.current);
			consolidateTimeoutRef.current = null;
			setConsolidating(false);
		}
	};

	const activeThreads = chats.filter((c) => c.active);
	const inactiveThreads = chats.filter((c) => !c.active);

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
						{consolidateError && (
							<div className="mx-2 mt-2 px-3 py-2 rounded-sm text-[13px] bg-error/10 border border-error/30 text-error">
								<span className="material-symbols-outlined text-[14px] align-text-bottom mr-1">
									error
								</span>
								{consolidateError}
							</div>
						)}
						<div className="px-4 py-sm border-b border-outline-variant/20 shrink-0 flex items-center justify-between">
							<h2 className="text-headline-md font-bold text-primary text-[16px]">
								Active Threads
							</h2>
							<button
								onClick={handleNewChat}
								className="hover:bg-surface-container-highest/50 p-1 rounded transition-colors text-on-surface-variant hover:text-primary"
								title="New chat"
							>
								<span className="material-symbols-outlined text-[18px]">
									add
								</span>
							</button>
						</div>
						<div className="flex-1 overflow-y-auto px-2 py-sm">
							{activeThreads.map((t) => {
								const isActive = t.id === chatId;
								return (
									<div key={t.id} className="group flex items-center relative">
										<Link
											to={`/chat/${t.id}`}
											className={
												isActive
													? "bg-secondary-container/30 text-secondary border-l-2 border-secondary px-3 py-2 flex items-center gap-sm transition-all duration-150 rounded-r text-[13px] no-underline flex-1 min-w-0"
													: "text-on-surface-variant px-3 py-2 hover:bg-surface-container-highest/50 transition-colors flex items-center gap-sm rounded-r text-[13px] no-underline flex-1 min-w-0"
											}
										>
											<span className="material-symbols-outlined text-[14px] shrink-0">
												chat_bubble
											</span>
											<span className="truncate">{t.title || "Untitled"}</span>
										</Link>
										<div className="absolute right-0 inset-y-0 flex items-center opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-l from-surface-container-low via-surface-container-low/80 to-transparent pl-6 pr-1">
											<ChatActions
												chatId={t.id}
												active={true}
												onStateChange={handleStateChange}
												onConsolidate={handleConsolidate}
											/>
										</div>
									</div>
								);
							})}
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
								{inactiveThreads.map((t) => {
									const isActive = t.id === chatId;
									return (
										<div
											key={t.id}
											className="group flex items-center relative"
										>
											<Link
												to={`/chat/${t.id}`}
												className={
													isActive
														? "bg-secondary-container/30 text-secondary border-l-2 border-secondary px-3 py-2 flex items-center gap-sm transition-all duration-150 rounded-r text-[13px] no-underline flex-1 min-w-0"
														: "text-on-surface-variant/70 px-3 py-2 hover:bg-surface-container-highest/30 transition-colors flex items-center gap-sm rounded-r text-[13px] no-underline flex-1 min-w-0"
												}
											>
												<span className="material-symbols-outlined text-[14px] shrink-0">
													history
												</span>
												<span className="truncate">
													{t.title || "Untitled"}
												</span>
											</Link>
											<div className="absolute right-0 inset-y-0 flex items-center opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-l from-surface-container-low via-surface-container-low/80 to-transparent pl-6 pr-1">
												<ChatActions
													chatId={t.id}
													active={false}
													onStateChange={handleStateChange}
													onConsolidate={handleConsolidate}
												/>
											</div>
										</div>
									);
								})}
							</div>
						)}
					</div>
				</aside>

				{/* Main Chat Area */}
				<main className="flex-1 ml-64 flex flex-col bg-background">
					<ChainlitChat
						key={chatId}
						chatId={chatId}
						onConsolidate={handleConsolidate}
					/>
				</main>
			</div>

			{/* Consolidation overlay */}
			{consolidating && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm">
					<div
						className="w-16 h-16 rounded-full animate-spin"
						style={{
							background:
								"conic-gradient(from 0deg, #6b5b95, #c5c3e4, #c9ada7, #9a8c98, #6b5b95)",
							mask: "radial-gradient(farthest-side, transparent calc(100% - 5px), #000 calc(100% - 4px))",
							WebkitMask:
								"radial-gradient(farthest-side, transparent calc(100% - 5px), #000 calc(100% - 4px))",
						}}
					/>
				</div>
			)}
		</div>
	);
}
