import { endChat, reactivateChat, deleteChat } from "../api";

export default function ChatActions({
	chatId,
	active,
	onStateChange,
	onConsolidate,
	showDelete,
	onDelete,
}) {
	const handleEnd = async (e) => {
		e.preventDefault();
		e.stopPropagation();
		await endChat(chatId);
		onStateChange?.(chatId, false);
	};

	const handleReactivate = async (e) => {
		e.preventDefault();
		e.stopPropagation();
		await reactivateChat(chatId);
		onStateChange?.(chatId, true);
	};

	const handleConsolidate = (e) => {
		e.preventDefault();
		e.stopPropagation();
		onConsolidate?.(chatId);
	};

	const handleDelete = async (e) => {
		e.preventDefault();
		e.stopPropagation();
		await deleteChat(chatId);
		onDelete?.(chatId);
	};

	return (
		<div
			className="flex items-center gap-xs shrink-0 opacity-0 group-hover:opacity-100 transition-opacity ml-auto"
			onClick={(e) => e.preventDefault()}
		>
			{active ? (
				<button
					onClick={handleEnd}
					title="End chat (move to inactive)"
					className="hover:bg-surface-container-highest/50 p-1 rounded transition-colors"
				>
					<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-on-surface">
						pause
					</span>
				</button>
			) : (
				<button
					onClick={handleReactivate}
					title="Reactivate chat"
					className="hover:bg-surface-container-highest/50 p-1 rounded transition-colors"
				>
					<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-primary">
						resume
					</span>
				</button>
			)}
			<button
				onClick={handleConsolidate}
				title="Consolidate memories"
				className="hover:bg-surface-container-highest/50 p-1 rounded transition-colors"
			>
				<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-primary">
					psychology
				</span>
			</button>
			{showDelete && (
				<button
					onClick={handleDelete}
					title="Delete chat"
					className="hover:bg-error/10 p-1 rounded transition-colors"
				>
					<span className="material-symbols-outlined text-[14px] text-on-surface-variant hover:text-error">
						delete
					</span>
				</button>
			)}
		</div>
	);
}
