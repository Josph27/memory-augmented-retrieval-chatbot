import { useEffect, useRef, useState } from "react";
import {
	useChatSession,
	useChatMessages,
	useChatInteract,
	useChatData,
} from "@chainlit/react-client";

function Message({ msg }) {
	const isUser = msg.type === "user_message";
	return (
		<div
			className="flex flex-col gap-xs p-md"
			style={{
				borderLeft: `2px solid ${isUser ? "var(--color-accent)" : "var(--color-border)"}`,
				background: "transparent",
			}}
		>
			<span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
				{isUser ? "You" : "Assistant"}
			</span>
			<p className="font-body-md text-body-md text-on-surface whitespace-pre-wrap leading-relaxed">
				{msg.output}
			</p>
		</div>
	);
}

export default function ChainlitChat({ chatId }) {
	const { setIdToResume, sendMessage } = useChatInteract();
	const { connect } = useChatSession();
	const { messages } = useChatMessages();
	const { loading, connected } = useChatData();
	const [input, setInput] = useState("");
	const scrollRef = useRef(null);
	const hasConnected = useRef(false);

	useEffect(() => {
		if (hasConnected.current) return;
		hasConnected.current = true;
		if (chatId) {
			setIdToResume(chatId);
		}
		connect({ userEnv: {} });
	}, [chatId, setIdToResume, connect]);

	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, [messages]);

	const handleSend = () => {
		const text = input.trim();
		if (!text) return;
		sendMessage({ type: "user_message", output: text, name: "user" });
		setInput("");
	};

	return (
		<div className="flex flex-col h-full bg-surface-container-lowest border border-outline-variant/20 rounded">
			{/* Messages Area */}
			<div
				ref={scrollRef}
				className="flex-1 overflow-y-auto px-margin py-md flex flex-col gap-md"
			>
				{!connected && !loading && (
					<div className="text-on-surface-variant italic text-center mt-xl">
						Connecting to chat server...
					</div>
				)}
				{messages.map((msg) => (
					<Message key={msg.id} msg={msg} />
				))}
				{loading && (
					<div className="text-on-surface-variant italic pl-md">
						Processing...
					</div>
				)}
			</div>

			{/* Input Area */}
			<div className="shrink-0 p-md border-t border-outline-variant/20 bg-surface-container-low flex items-center gap-md">
				<input
					className="flex-1 bg-surface-container-highest border border-outline-variant rounded text-on-surface px-md py-sm font-body-md focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/50"
					value={input}
					onChange={(e) => setInput(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === "Enter" && !e.shiftKey) {
							e.preventDefault();
							handleSend();
						}
					}}
					placeholder="Type your message..."
					disabled={!connected}
				/>
				<button
					onClick={handleSend}
					disabled={!input.trim() || !connected}
					className="bg-primary text-on-primary px-lg py-sm rounded font-label-md hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity flex items-center gap-xs"
				>
					<span className="material-symbols-outlined text-[18px]">send</span>
				</button>
			</div>
		</div>
	);
}
