import { Link, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { fetchChats, createChat, endChat, reactivateChat, deleteChat } from "../api";

function Home() {
	const navigate = useNavigate();
	const [chats, setChats] = useState([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		fetchChats({ limit: 20 })
			.then((data) => {
				setChats(data);
				setLoading(false);
			})
			.catch((err) => {
				console.error(err);
				setLoading(false);
			});
	}, []);

	const handleNewChat = async (e) => {
		e.preventDefault();
		try {
			const { chat_id } = await createChat();
			navigate(`/chat/${chat_id}`);
		} catch (err) {
			console.error(err);
			alert("Failed to create chat");
		}
	};
	return (
		<div className="px-margin py-lg max-w-7xl mx-auto flex flex-col gap-lg lg:h-[calc(100vh-3rem)] lg:overflow-hidden">
			{/* Hero */}
			<div className="flex flex-col items-center justify-center gap-md text-center max-w-3xl mx-auto py-sm shrink-0">
				<header className="space-y-sm">
					<h1 className="font-display text-display text-on-surface">
						Technical Retrieval Workspace
					</h1>
				</header>
				<div className="mt-md">
					<Link
						to="/chat"
						onClick={handleNewChat}
						className="group relative overflow-hidden rounded-lg bg-almond-silk text-primary-container font-headline-md text-headline-md px-xl py-lg flex items-center justify-center gap-md hover:bg-[#d2c2cf] transition-all duration-300 mx-auto min-w-[200px]"
					>
						<span className="material-symbols-outlined">add_circle</span>
						<span>New Chat</span>
						<div className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg pointer-events-none" />
					</Link>
				</div>
			</div>

			{/* Bottom Section: Two Columns */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-lg flex-1 min-h-0">
				{/* Left: Continue Chat */}
				<div className="lg:col-span-8 flex flex-col gap-md min-h-0">
					<div className="glass-panel p-lg rounded-lg flex flex-col gap-md flex-1 min-h-0">
						<div className="flex items-center justify-between border-b border-outline-variant/20 pb-sm shrink-0">
							<h3 className="font-label-md text-label-md text-on-surface uppercase tracking-wider flex items-center gap-2">
								<span className="material-symbols-outlined text-on-surface-variant text-sm">
									history
								</span>
								Continue Chat
							</h3>
							<span className="font-label-sm text-on-surface-variant">
								Last 30 Days
							</span>
						</div>
						<ul className="space-y-sm font-body-sm text-body-sm text-on-surface-variant overflow-y-auto custom-scrollbar pr-2 flex-1 min-h-0">
							{loading && <li>Loading...</li>}
							{!loading && chats.length === 0 && <li>No recent chats.</li>}
							{!loading &&
								chats.map((chat) => {
									const activeStyle = chat.active
										? "border-l-2 border-almond-silk"
										: "border-l-2 border-outline-variant";
									return (
										<Link
											key={chat.id}
											to={`/chat/${chat.id}`}
											className={`flex items-center gap-sm ${activeStyle} pl-sm py-xs hover:bg-surface-container transition-colors rounded-r no-underline text-on-surface-variant`}
										>
											<span className="truncate">
												{chat.title || "Untitled"}
											</span>
										</Link>
									);
								})}
						</ul>
					</div>
				</div>

				{/* Right: Quick Actions */}
				<div className="lg:col-span-4 flex flex-col sm:flex-row lg:flex-col gap-md">
					<Link
						to="/chats"
						className="glass-panel flex-1 rounded-lg hover:bg-[#4a4e69]/30 transition-all duration-300 flex flex-col items-center justify-center p-xl gap-sm text-center group cursor-pointer border border-outline-variant/30 hover:border-[#c9ada7]/50"
					>
						<span className="material-symbols-outlined text-4xl text-almond-silk group-hover:scale-110 transition-transform">
							forum
						</span>
						<h3 className="font-headline-md text-headline-md text-on-surface">
							Chats
						</h3>
						<p className="font-body-sm text-body-sm text-on-surface-variant max-w-[200px]">
							Browse and manage all active workspace conversations.
						</p>
					</Link>
					<Link
						to="/documents"
						className="glass-panel flex-1 rounded-lg hover:bg-[#4a4e69]/30 transition-all duration-300 flex flex-col items-center justify-center p-xl gap-sm text-center group cursor-pointer border border-outline-variant/30 hover:border-lilac-ash/50"
					>
						<span className="material-symbols-outlined text-4xl text-lilac-ash group-hover:scale-110 transition-transform">
							description
						</span>
						<h3 className="font-headline-md text-headline-md text-on-surface">
							Documents
						</h3>
						<p className="font-body-sm text-body-sm text-on-surface-variant max-w-[200px]">
							Access indexed files, code snippets, and structured data.
						</p>
					</Link>
					<Link
						to="/memories"
						className="glass-panel flex-1 rounded-lg hover:bg-[#4a4e69]/30 transition-all duration-300 flex flex-col items-center justify-center p-xl gap-sm text-center group cursor-pointer border border-outline-variant/30 hover:border-primary/50"
					>
						<span className="material-symbols-outlined text-4xl text-primary group-hover:scale-110 transition-transform">
							psychology
						</span>
						<h3 className="font-headline-md text-headline-md text-on-surface">
							Memories
						</h3>
						<p className="font-body-sm text-body-sm text-on-surface-variant max-w-[200px]">
							Explore contextual vectors and persistent system states.
						</p>
					</Link>
				</div>
			</div>
		</div>
	);
}

export default Home;
