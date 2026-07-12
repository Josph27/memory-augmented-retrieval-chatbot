import { useEffect, useRef, useState } from "react";
import {
	useChatSession,
	useChatMessages,
	useChatInteract,
	useChatData,
	sessionIdState,
} from "@chainlit/react-client";
import { useRecoilState } from "recoil";
import { createChat, endChat, forkChat } from "../api";
import { useNavigate } from "react-router-dom";
import { v4 as uuidv4 } from "uuid";

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
				{msg.elements && msg.elements.length > 0 && (
					<div className="mt-sm pt-sm border-t border-outline-variant/20 flex flex-wrap gap-sm">
						{msg.elements.map((doc, j) => (
							<span
								key={doc.id || j}
								className="bg-surface-container-high text-on-surface-variant px-sm py-1 rounded text-label-sm border border-outline-variant/30 flex items-center gap-1"
								title={doc.name}
							>
								<span className="material-symbols-outlined text-[12px]">
									{doc.name?.endsWith(".pdf") ? "description" : "draft"}
								</span>
								{doc.name}
							</span>
						))}
					</div>
				)}
			</div>
		</div>
	);
}

export default function ChainlitChat({ chatId }) {
	const { setIdToResume, sendMessage, uploadFile } = useChatInteract();
	const { connect, disconnect, idToResume } = useChatSession();
	const { messages } = useChatMessages();
	const { loading, connected } = useChatData();
	const [sessionId, setSessionId] = useRecoilState(sessionIdState);
	const [targetSessionId] = useState(() => uuidv4());
	const [input, setInput] = useState("");
	const [attachedFile, setAttachedFile] = useState(null);
	const fileInputRef = useRef(null);
	const scrollRef = useRef(null);
	const hasConnected = useRef(false);
	const navigate = useNavigate();

	useEffect(() => {
		if (hasConnected.current) return;

		let pendingUpdate = false;

		if (sessionId !== targetSessionId) {
			setSessionId(targetSessionId);
			pendingUpdate = true;
		}

		if (chatId && idToResume !== chatId) {
			setIdToResume(chatId);
			pendingUpdate = true;
		}
		if (!chatId && idToResume) {
			setIdToResume(undefined);
			pendingUpdate = true;
		}

		if (pendingUpdate) return; // Wait for Recoil state to sync

		hasConnected.current = true;
		connect({ userEnv: {} });

		return () => {
			if (connect && typeof connect.cancel === "function") {
				connect.cancel();
			}
			disconnect();
		};
	}, [
		chatId,
		idToResume,
		setIdToResume,
		connect,
		disconnect,
		sessionId,
		targetSessionId,
		setSessionId,
	]);

	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, [messages]);

	const handleSend = () => {
		const text = input.trim();
		// Block if file is still uploading
		if (attachedFile && !attachedFile.fileRef && !attachedFile.error) return;

		if (!text && !attachedFile?.fileRef) return;

		const fileRefs = attachedFile?.fileRef ? [attachedFile.fileRef] : [];
		sendMessage(
			{ type: "user_message", output: text || "", name: "user" },
			fileRefs,
		);

		setInput("");
		setAttachedFile(null);
	};

	const handleFileChange = (e) => {
		const file = e.target.files?.[0];
		if (!file) return;

		setAttachedFile({ file, progress: 0, fileRef: null, error: null });

		const { promise } = uploadFile(file, (progress) => {
			setAttachedFile((prev) => (prev ? { ...prev, progress } : null));
		});

		promise
			.then((fileRef) => {
				setAttachedFile((prev) =>
					prev ? { ...prev, fileRef, progress: 100 } : null,
				);
			})
			.catch((error) => {
				console.error("Upload failed:", error?.message || error);
				setAttachedFile((prev) =>
					prev ? { ...prev, error: "Upload failed" } : null,
				);
			});

		// Reset input to allow re-selecting the same file
		if (fileInputRef.current) {
			fileInputRef.current.value = "";
		}
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

	const handleEndChat = async () => {
		if (!chatId) return;
		try {
			await endChat(chatId);
			navigate(`/chats`);
		} catch (err) {
			console.error(err);
			alert("Failed to end chat");
		}
	};

	const handleForkChat = async () => {
		if (!chatId) return;
		try {
			const { chat_id } = await forkChat(chatId);
			navigate(`/chat/${chat_id}`);
		} catch (err) {
			console.error(err);
			alert("Failed to fork chat");
		}
	};

	const flatMessages = [];
	const flatten = (msgs) => {
		msgs.forEach((m) => {
			flatMessages.push(m);
			if (m.steps) flatten(m.steps);
		});
	};
	flatten(messages);

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
				{flatMessages.map((msg) => (
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
							onClick={handleEndChat}
							disabled={!connected}
							className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs hover:bg-dusty-grape/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<span className="material-symbols-outlined text-[14px]">
								stop_circle
							</span>
							End Chat
						</button>
						<button
							onClick={() => fileInputRef.current?.click()}
							disabled={!connected}
							className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs hover:bg-dusty-grape/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<span className="material-symbols-outlined text-[14px]">
								upload_file
							</span>
							Upload Doc
						</button>
						<input
							type="file"
							ref={fileInputRef}
							style={{ display: "none" }}
							onChange={handleFileChange}
						/>
						<button
							onClick={handleForkChat}
							disabled={!connected}
							className="bg-dusty-grape/20 border border-lilac-ash/30 text-almond-silk px-3 py-1 rounded-sm text-label-sm flex items-center gap-xs hover:bg-dusty-grape/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
					{attachedFile && (
						<div className="flex items-center justify-between bg-surface-container-high border border-outline-variant/30 rounded-sm px-sm py-xs mb-xs">
							<div className="flex items-center gap-xs">
								<span className="material-symbols-outlined text-[14px] text-on-surface-variant">
									description
								</span>
								<span className="font-label-sm text-on-surface text-sm truncate max-w-[200px]">
									{attachedFile.file.name}
								</span>
								{!attachedFile.fileRef && !attachedFile.error && (
									<span className="text-xs text-almond-silk ml-2">
										{Math.round(attachedFile.progress)}%
									</span>
								)}
								{attachedFile.error && (
									<span className="text-xs text-error ml-2">Failed</span>
								)}
							</div>
							<button
								onClick={() => setAttachedFile(null)}
								className="text-on-surface-variant hover:text-error transition-colors"
							>
								<span className="material-symbols-outlined text-[16px]">
									close
								</span>
							</button>
						</div>
					)}
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
