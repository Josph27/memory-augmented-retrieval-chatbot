import { Link, useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";
import { fetchChats, createChat } from "../api";
import ChatActions from "../components/ChatActions";

export default function Chats() {
	const navigate = useNavigate();
	const [chats, setChats] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

	useEffect(() => {
		fetchChats()
			.then((data) => {
				setChats(data);
				setLoading(false);
			})
			.catch((err) => {
				console.error(err);
				setError("Failed to load chats.");
				setLoading(false);
			});
	}, []);

	const handleNewSession = async () => {
		try {
			const { chat_id } = await createChat();
			navigate(`/chat/${chat_id}`);
		} catch (err) {
			console.error(err);
			alert("Failed to create a new session.");
		}
	};

	const activeThreads = chats.filter((c) => c.active);
	const inactiveThreads = chats.filter((c) => !c.active);

	const handleStateChange = useCallback((id, active) => {
		setChats((prev) => prev.map((c) => (c.id === id ? { ...c, active } : c)));
	}, []);

	const handleDelete = useCallback((deletedId) => {
		setChats((prev) => prev.filter((c) => c.id !== deletedId));
	}, []);

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
		<div className="pt-xl pb-xl px-margin max-w-4xl mx-auto">
			<header className="mb-xl flex justify-between items-end border-b border-outline-variant/20 pb-sm">
				<div>
					<h1 className="font-headline-lg text-headline-lg text-primary">
						Chat Threads
					</h1>
					<p className="font-label-md text-label-md text-on-surface-variant mt-xs">
						Contextual data streams and dialogue histories.
					</p>
				</div>
				<button
					onClick={handleNewSession}
					className="bg-almond-silk text-primary-container px-lg py-sm rounded font-label-md text-label-md hover:bg-surface-tint transition-colors flex items-center gap-sm"
				>
					<span className="material-symbols-outlined text-[16px]">add</span>New
					Session
				</button>
			</header>

			{loading && (
				<div className="text-on-surface-variant mb-xl">Loading...</div>
			)}
			{error && <div className="text-red-400 mb-xl">{error}</div>}

			{!loading && !error && (
				<>
					<section className="mb-xl">
						<h2 className="font-label-md text-label-md text-secondary mb-sm uppercase tracking-wider">
							Active Threads
						</h2>
						<div className="bg-surface-container-low border border-outline-variant/20 rounded overflow-hidden">
							{activeThreads.length === 0 ? (
								<div className="px-lg py-sm text-on-surface-variant italic">
									No active threads.
								</div>
							) : (
								activeThreads.map((t) => (
									<div
										key={t.id}
										className="group flex items-center bg-surface-container-low hover:bg-dusty-grape/20 transition-colors border-b border-lilac-ash/10 h-10"
									>
										<Link
											to={`/chat/${t.id}`}
											className="flex items-center gap-md px-lg py-sm flex-1 min-w-0 no-underline"
										>
											<span className="material-symbols-outlined text-[16px] text-primary shrink-0">
												chat_bubble
											</span>
											<span className="font-body-md text-body-md text-on-surface truncate max-w-[300px]">
												{t.title}
											</span>
										</Link>
										<span className="font-code text-code text-on-surface-variant mr-sm whitespace-nowrap">
											{formatDate(t.updated_at || t.created_at)}
										</span>
										<ChatActions
											chatId={t.id}
											active={true}
											onStateChange={handleStateChange}
											onDelete={handleDelete}
										/>
									</div>
								))
							)}
						</div>
					</section>

					<section>
						<h2 className="font-label-md text-label-md text-on-surface-variant mb-sm uppercase tracking-wider">
							Inactive Threads
						</h2>
						<div className="bg-surface-container-lowest border border-outline-variant/20 rounded overflow-hidden opacity-80">
							{inactiveThreads.length === 0 ? (
								<div className="px-lg py-sm text-on-surface-variant italic">
									No inactive threads.
								</div>
							) : (
								inactiveThreads.map((t) => (
									<div
										key={t.id}
										className="group flex items-center bg-surface-container-lowest hover:bg-dusty-grape/10 transition-colors border-b border-lilac-ash/10 h-10"
									>
										<Link
											to={`/chat/${t.id}`}
											className="flex items-center gap-md px-lg py-sm flex-1 min-w-0 no-underline"
										>
											<span className="material-symbols-outlined text-[16px] text-on-surface-variant shrink-0">
												history
											</span>
											<span className="font-body-md text-body-md text-on-surface-variant truncate max-w-[300px]">
												{t.title}
											</span>
										</Link>
										<span className="font-code text-code text-on-surface-variant/70 mr-sm whitespace-nowrap">
											{formatDate(t.updated_at || t.created_at)}
										</span>
										<ChatActions
											chatId={t.id}
											active={false}
											onStateChange={handleStateChange}
											onDelete={handleDelete}
										/>
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
