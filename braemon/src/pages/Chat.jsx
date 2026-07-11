import { useParams, Link, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import ChainlitChat from "../components/ChainlitChat";
import { fetchChats } from "../api";

export default function Chat() {
	const { chatId } = useParams();
	const navigate = useNavigate();
	const [chats, setChats] = useState([]);
	const [inactiveOpen, setInactiveOpen] = useState(false);

	useEffect(() => {
		// Fetch chats whenever chatId changes so the sidebar is up-to-date
		fetchChats({ limit: 50 }).then(setChats).catch(console.error);
	}, [chatId]);

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
						<div className="px-4 py-sm border-b border-outline-variant/20 shrink-0">
							<h2 className="text-headline-md font-bold text-primary text-[16px]">
								Active Threads
							</h2>
						</div>
						<div className="flex-1 overflow-y-auto px-2 py-sm">
							{activeThreads.map((t) => {
								const isActive = t.id === chatId;
								return (
									<Link
										key={t.id}
										to={`/chat/${t.id}`}
										className={
											isActive
												? "bg-secondary-container/30 text-secondary border-l-2 border-secondary px-3 py-2 flex items-center gap-sm transition-all duration-150 rounded-r text-[13px] no-underline"
												: "text-on-surface-variant px-3 py-2 hover:bg-surface-container-highest/50 transition-colors flex items-center gap-sm rounded-r text-[13px] no-underline"
										}
									>
										<span className="material-symbols-outlined text-[14px]">
											chat_bubble
										</span>
										<span className="truncate">{t.title || "Untitled"}</span>
									</Link>
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
										<Link
											key={t.id}
											to={`/chat/${t.id}`}
											className={
												isActive
													? "bg-secondary-container/30 text-secondary border-l-2 border-secondary px-3 py-2 flex items-center gap-sm transition-all duration-150 rounded-r text-[13px] no-underline"
													: "text-on-surface-variant/70 px-3 py-2 hover:bg-surface-container-highest/30 transition-colors flex items-center gap-sm rounded-r text-[13px] no-underline"
											}
										>
											<span className="material-symbols-outlined text-[14px]">
												history
											</span>
											<span className="truncate">{t.title || "Untitled"}</span>
										</Link>
									);
								})}
							</div>
						)}
					</div>
				</aside>

				{/* Main Chat Area */}
				<main className="flex-1 ml-64 flex flex-col bg-background">
					<ChainlitChat key={chatId} chatId={chatId} />
				</main>
			</div>
		</div>
	);
}
