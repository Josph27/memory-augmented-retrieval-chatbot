import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import {
	useChatSession,
	useChatMessages,
	useChatInteract,
	useChatData,
} from "@chainlit/react-client";

export default function Chat() {
	const { chatId } = useParams();
	const { connect, disconnect, idToResume } = useChatSession();
	const { messages } = useChatMessages();
	const { sendMessage, setIdToResume } = useChatInteract();
	const { connected, error, loading } = useChatData();
	const [input, setInput] = useState("");

	// Connect on mount
	useEffect(() => {
		connect({ userEnv: {} });
		return () => disconnect();
	}, []);

	// Resume thread when chatId changes
	useEffect(() => {
		if (chatId) setIdToResume(chatId);
	}, [chatId, setIdToResume]);

	// Update URL when thread is assigned
	useEffect(() => {
		if (idToResume && !chatId) {
			window.history.replaceState(null, "", `/chat/${idToResume}`);
		}
	}, [idToResume, chatId]);

	const handleSend = useCallback(() => {
		const text = input.trim();
		if (!text) return;
		sendMessage({
			name: "user",
			type: "user_message",
			output: text,
		});
		setInput("");
	}, [input, sendMessage]);

	const visible = messages.filter(
		(m) => m.type === "user_message" || m.type === "assistant_message",
	);

	return (
		<div className="h-screen flex flex-col overflow-hidden">
			<main className="flex-1 flex flex-col bg-background relative pb-8">
				{/* Status bar */}
				<div className="h-8 bg-surface-container-low flex items-center px-margin gap-md border-b border-outline-variant/20 font-label-sm text-label-sm">
					<div
						className={`w-2 h-2 rounded-full ${
							connected ? "bg-[#34d399]" : error ? "bg-error" : "bg-[#fbbf24]"
						}`}
					/>
					<span className="text-on-surface-variant">
						{connected ? "Connected" : error ? "Error" : "Connecting..."}
					</span>
					<span className="text-outline">|</span>
					<span className="text-on-surface-variant">
						{visible.length} messages
						{loading ? " · thinking..." : ""}
					</span>
				</div>

				{/* Messages */}
				<div className="flex-1 overflow-y-auto p-margin pb-20 flex flex-col gap-2">
					{visible.length === 0 && (
						<div className="flex-1 flex items-center justify-center">
							<p className="font-body-lg text-on-surface-variant/50">
								Send a message to start...
							</p>
						</div>
					)}
					{visible.map((msg, i) => {
						const isUser = msg.type === "user_message";
						return (
							<div
								key={msg.id || i}
								className="w-full max-w-4xl mx-auto flex flex-col"
							>
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
										dangerouslySetInnerHTML={
											!isUser ? { __html: msg.output } : undefined
										}
									>
										{isUser ? msg.output : undefined}
									</p>
								</div>
							</div>
						);
					})}
				</div>

				{/* Input */}
				<div className="absolute bottom-0 w-full bg-surface/90 backdrop-blur-sm border-t border-outline-variant/20 p-margin">
					<div className="max-w-4xl mx-auto relative flex items-center">
						<span className="material-symbols-outlined absolute left-sm text-on-surface-variant text-[20px]">
							terminal
						</span>
						<input
							className="w-full bg-surface-container-lowest border border-outline-variant/50 rounded-sm py-2 pl-xl pr-12 text-body-md text-on-surface placeholder:text-on-surface-variant/50 focus:border-almond-silk focus:ring-0 focus:outline-none transition-colors"
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
			</main>
		</div>
	);
}
