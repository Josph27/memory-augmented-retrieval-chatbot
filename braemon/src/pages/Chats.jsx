import { Link, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { fetchChats, createChat } from "../api";

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
									<Link
										key={t.id}
										to={`/chat/${t.id}`}
										className="group flex items-center justify-between px-lg py-sm border-b border-lilac-ash/10 hover:bg-dusty-grape/20 transition-colors cursor-pointer h-10 no-underline"
									>
										<div className="flex items-center gap-md">
											<span className="material-symbols-outlined text-[16px] text-primary">
												chat_bubble
											</span>
											<span className="font-body-md text-body-md text-on-surface truncate max-w-[300px]">
												{t.title}
											</span>
										</div>
										<span className="font-code text-code text-on-surface-variant">
											{formatDate(t.updated_at || t.created_at)}
										</span>
									</Link>
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
									<Link
										key={t.id}
										to={`/chat/${t.id}`}
										className="group flex items-center justify-between px-lg py-sm border-b border-lilac-ash/10 hover:bg-dusty-grape/10 transition-colors cursor-pointer h-10 no-underline"
									>
										<div className="flex items-center gap-md">
											<span className="material-symbols-outlined text-[16px] text-on-surface-variant">
												history
											</span>
											<span className="font-body-md text-body-md text-on-surface-variant truncate max-w-[300px]">
												{t.title}
											</span>
										</div>
										<span className="font-code text-code text-on-surface-variant/70">
											{formatDate(t.updated_at || t.created_at)}
										</span>
									</Link>
								))
							)}
						</div>
					</section>
				</>
			)}
		</div>
	);
}
