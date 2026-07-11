import { useEffect, useRef, useState } from "react";
import {
	useChatSession,
	useChatMessages,
	useChatInteract,
	useChatData,
} from "@chainlit/react-client";
import { createChat } from "../api";
import { useNavigate } from "react-router-dom";

function Message({ msg }) {
	const isUser = msg.type === "user_message";
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
					{msg.output}
				</p>
				{/* Defer docs UI until we map Chainlit elements to msg.docs */}
			</div>
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
	const navigate = useNavigate();

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

	const handleNewChat = async () => {
		try {
			const { chat_id } = await createChat();
			navigate(`/chat/${chat_id}`);
		} catch (err) {
			console.error(err);
			alert("Failed to create new chat");
		}
	};

	return (
		<div className="flex flex-col h-full bg-background w-full">
			{/* Messages Area */}
			<div
				ref={scrollRef}
				className="flex-1 overflow-y-auto px-margin pt-sm pb-0 flex flex-col gap-sm min-h-0"
				style={{ overscrollBehavior: "none" }}
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
					<div className="text-on-surface-variant italic pl-md max-w-4xl mx-auto w-full">
						Processing...
					</div>
				)}
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
							onClick={handleNewChat}
							className="bg-almond-silk text-primary-container px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs"
						>
							<span className="material-symbols-outlined text-[14px]">add</span>
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
							disabled={!connected}
						/>
						<button
							onClick={handleSend}
							disabled={!input.trim() || !connected}
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
