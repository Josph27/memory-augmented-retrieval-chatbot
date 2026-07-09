import { useState, useEffect, useContext } from "react";
import { Link } from "react-router-dom";
import { ChainlitContext } from "@chainlit/react-client";

function Chats() {
	const client = useContext(ChainlitContext);
	const [threads, setThreads] = useState([]);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState(null);

	useEffect(() => {
		if (!client) return;
		setIsLoading(true);
		setError(null);
		client
			.listThreads({ first: 50 }, {})
			.then((result) => {
				setThreads(result.data || []);
			})
			.catch((err) => {
				setError(err.message || "Failed to load threads");
			})
			.finally(() => setIsLoading(false));
	}, [client]);
	const activeThreads = threads.filter((t) => !t.metadata?.ended);
	const inactiveThreads = threads.filter((t) => t.metadata?.ended);

	const formatTime = (timestamp) => {
		if (!timestamp) return "";
		const d = new Date(timestamp);
		return d.toLocaleDateString(undefined, {
			month: "short",
			day: "numeric",
		});
	};

	const formatName = (t) => t.name || `Thread ${t.id?.slice(0, 8)}`;

	if (isLoading) {
		return (
			<div className="pt-xl pb-xl px-margin max-w-4xl mx-auto flex items-center justify-center min-h-[50vh]">
				<div className="flex flex-col items-center gap-md">
					<div className="w-8 h-8 border-2 border-almond-silk border-t-transparent rounded-full animate-spin" />
					<p className="font-label-md text-on-surface-variant">
						Loading threads...
					</p>
				</div>
			</div>
		);
	}

	if (error) {
		return (
			<div className="pt-xl pb-xl px-margin max-w-4xl mx-auto">
				<div className="glass-panel p-xl rounded-lg text-center">
					<span className="material-symbols-outlined text-4xl text-error mb-md block">
						error
					</span>
					<p className="font-body-lg text-error">Failed to load threads</p>
					<p className="font-body-sm text-on-surface-variant mt-sm">{error}</p>
				</div>
			</div>
		);
	}

	return (
		<div className="pt-xl pb-xl px-margin max-w-4xl mx-auto">
			{/* Header */}
			<header className="mb-xl flex justify-between items-end border-b border-outline-variant/20 pb-sm">
				<div>
					<h1 className="font-headline-lg text-headline-lg text-primary">
						Chat Threads
					</h1>
					<p className="font-label-md text-label-md text-on-surface-variant mt-xs">
						Contextual data streams and dialogue histories.
					</p>
				</div>
				<Link
					to="/chat"
					className="bg-almond-silk text-primary-container px-lg py-sm rounded font-label-md text-label-md hover:bg-surface-tint transition-colors flex items-center gap-sm"
				>
					<span className="material-symbols-outlined text-[16px]">add</span>
					New Session
				</Link>
			</header>

			{threads.length === 0 ? (
				<div className="text-center py-xl">
					<p className="font-body-lg text-on-surface-variant">
						No threads yet. Start a new chat!
					</p>
				</div>
			) : (
				<>
					{/* Active Threads */}
					{activeThreads.length > 0 && (
						<section className="mb-xl">
							<h2 className="font-label-md text-label-md text-secondary mb-sm uppercase tracking-wider">
								Active Threads
							</h2>
							<div className="bg-surface-container-low border border-outline-variant/20 rounded overflow-hidden">
								{activeThreads.map((t) => (
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
												{formatName(t)}
											</span>
										</div>
										<div className="flex items-center gap-md">
											<span className="font-code text-code text-on-surface-variant">
												{formatTime(t.createdAt)}
											</span>
										</div>
									</Link>
								))}
							</div>
						</section>
					)}

					{/* Inactive Threads */}
					{inactiveThreads.length > 0 && (
						<section>
							<h2 className="font-label-md text-label-md text-on-surface-variant mb-sm uppercase tracking-wider">
								Inactive Threads
							</h2>
							<div className="bg-surface-container-lowest border border-outline-variant/20 rounded overflow-hidden opacity-80">
								{inactiveThreads.map((t) => (
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
												{formatName(t)}
											</span>
										</div>
										<div className="flex items-center gap-md">
											<span className="font-code text-code text-on-surface-variant/70">
												{formatTime(t.createdAt)}
											</span>
										</div>
									</Link>
								))}
							</div>
						</section>
					)}
				</>
			)}
		</div>
	);
}

export default Chats;
