(() => {
	const SOURCE = "memory-chatbot-ui";
	const TOOLBAR_ID = "memory-chatbot-controls";
	const HOME_ID = "memory-chatbot-home";
	const INSPECTOR_ID = "memory-answer-inspector";
	const INSPECT_ACTION_CLASS = "memory-inspect-answer";
	const LIFECYCLE_OVERLAY_ID = "memory-lifecycle-overlay";
	const productState = { view: "home", active: null, chatId: null };
	const answerInspections = [];
	const renderScheduled = false;
	const inspectorRenderScheduled = false;
	const firstProductStateReceived = false;

	// Show the loading overlay immediately — the backend is loading models.
	showLifecycleOverlay("Loading models…");

	function removeElement(id) {
		document.getElementById(id)?.remove();
	}

	function injectOverlayStyles() {
		if (document.getElementById("memory-lifecycle-styles")) return;
		const style = document.createElement("style");
		style.id = "memory-lifecycle-styles";
		style.textContent =
			`#${LIFECYCLE_OVERLAY_ID} {` +
			"position:fixed;inset:0;z-index:9999;display:flex;" +
			"align-items:center;justify-content:center;" +
			"background:color-mix(in srgb, var(--background,#111) 88%, transparent);" +
			"backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);" +
			"}" +
			`#${LIFECYCLE_OVERLAY_ID} .spinner {` +
			"width:52px;height:52px;border:4px solid " +
			"color-mix(in srgb, currentColor 18%, transparent);" +
			"border-top-color:currentColor;border-radius:50%;" +
			"animation:memory-spin 0.85s linear infinite;" +
			"}" +
			"@keyframes memory-spin {" +
			"to {transform:rotate(360deg)}" +
			"}" +
			`#${LIFECYCLE_OVERLAY_ID} .label {` +
			"margin-top:16px;font-size:14px;opacity:0.78;" +
			"}";
		document.head.appendChild(style);
	}

	function showLifecycleOverlay(label) {
		injectOverlayStyles();
		removeElement(LIFECYCLE_OVERLAY_ID);
		const overlay = document.createElement("div");
		overlay.id = LIFECYCLE_OVERLAY_ID;
		overlay.setAttribute("role", "alertdialog");
		overlay.setAttribute("aria-label", label || "Processing");
		const wrapper = document.createElement("div");
		wrapper.style.cssText =
			"display:flex;flex-direction:column;align-items:center;";
		const spinner = document.createElement("div");
		spinner.className = "spinner";
		wrapper.appendChild(spinner);
		const text = document.createElement("span");
		text.className = "label";
		text.textContent = label || "Processing…";
		wrapper.appendChild(text);
		overlay.appendChild(wrapper);
		document.body.appendChild(overlay);
	}

	function hideLifecycleOverlay() {
		removeElement(LIFECYCLE_OVERLAY_ID);
	}

	function sendLifecycleAction(action) {
		const labels = { end: "Consolidating memory…", fork: "Forking chat…" };
		showLifecycleOverlay(labels[action] || "Processing…");
		window.parent.postMessage(
			{
				source: SOURCE,
				command: "lifecycle-action",
				action,
				chat_id: productState.chatId,
			},
			"*",
		);
	}

	function lifecycleButton(label, action) {
		const button = document.createElement("button");
		button.type = "button";
		button.textContent = label;
		button.dataset.lifecycleAction = action;
		Object.assign(button.style, {
			minHeight: "30px",
			padding: "4px 10px",
			border: "1px solid color-mix(in srgb, currentColor 20%, transparent)",
			borderRadius: "7px",
			background: "transparent",
			color: "inherit",
			fontSize: "13px",
			lineHeight: "20px",
			cursor: "pointer",
		});
		button.addEventListener("click", () => sendLifecycleAction(action));
		return button;
	}

	function consolidationLogButton() {
		const button = document.createElement("button");
		button.type = "button";
		button.textContent = "Consolidation Log";
		Object.assign(button.style, {
			minHeight: "30px",
			padding: "4px 10px",
			border: "1px solid color-mix(in srgb, currentColor 20%, transparent)",
			borderRadius: "7px",
			background: "transparent",
			color: "inherit",
			fontSize: "13px",
			lineHeight: "20px",
			cursor: "pointer",
		});
		button.addEventListener("click", () => {
			window.parent.postMessage(
				{
					source: SOURCE,
					command: "consolidation-log",
					chat_id: productState.chatId,
				},
				"*",
			);
		});
		return button;
	}

	function visibleComposer() {
		return Array.from(
			document.querySelectorAll("main textarea, main [contenteditable='true']"),
		).find((element) => element.getClientRects().length > 0);
	}

	function mountInChatColumn(element) {
		const composer = visibleComposer();
		const composerContainer =
			composer?.closest("#message-composer") || composer?.closest("form");
		if (composerContainer?.parentElement) {
			composerContainer.parentElement.insertBefore(element, composerContainer);
			element.dataset.mount = "composer";
			return true;
		}
		const main = document.querySelector("main");
		if (main) {
			main.appendChild(element);
			element.dataset.mount = "chat-bottom";
			return true;
		}
		return false;
	}

	function renderControls() {
		if (productState.view === "home" || !productState.chatId) {
			removeElement(TOOLBAR_ID);
			return;
		}
		let toolbar = document.getElementById(TOOLBAR_ID);
		if (!toolbar) {
			toolbar = document.createElement("div");
			toolbar.id = TOOLBAR_ID;
			toolbar.setAttribute("role", "toolbar");
			toolbar.setAttribute("aria-label", "Chat lifecycle controls");
		}
		toolbar.replaceChildren();
		Object.assign(toolbar.style, {
			display: "flex",
			flexWrap: "wrap",
			justifyContent: "flex-end",
			alignItems: "center",
			gap: "6px",
			width: "100%",
			maxWidth: "768px",
			boxSizing: "border-box",
			margin: "8px auto 4px",
			padding: "6px 8px",
			border: "1px solid color-mix(in srgb, currentColor 12%, transparent)",
			borderRadius: "9px",
			background:
				"color-mix(in srgb, var(--background, #fff) 94%, currentColor 6%)",
			fontSize: "13px",
		});

		if (productState.active === true) {
			toolbar.appendChild(lifecycleButton("End Chat", "end"));
		}
		toolbar.appendChild(lifecycleButton("Fork Chat", "fork"));
		toolbar.appendChild(lifecycleButton("New Chat", "new"));
		toolbar.appendChild(lifecycleButton("Home", "home"));
		toolbar.appendChild(consolidationLogButton());
		if (!mountInChatColumn(toolbar)) toolbar.remove();
	}

	function normalizedText(value) {
		return String(value || "")
			.replace(/\s+/g, " ")
			.trim();
	}

	function answerElement(inspection) {
		const persistedStepId = `message:${inspection.assistant_message_id}`;
		const identified = document.querySelector(
			`[data-step-id="${CSS.escape(persistedStepId)}"], [id="${CSS.escape(persistedStepId)}"]`,
		);
		if (identified) return identified;
		const answerText = inspection.answer_text;
		const expected = normalizedText(answerText);
		if (!expected) return null;
		return Array.from(document.querySelectorAll("main *"))
			.filter((element) => {
				if (
					element.closest(`#${INSPECTOR_ID}`) ||
					element.closest(`.${INSPECT_ACTION_CLASS}`) ||
					element.getClientRects().length === 0
				) {
					return false;
				}
				return (
					normalizedText(element.innerText) === expected &&
					!answerContainer(element)?.querySelector(`.${INSPECT_ACTION_CLASS}`)
				);
			})
			.sort(
				(left, right) => left.childElementCount - right.childElementCount,
			)[0];
	}

	function answerContainer(element) {
		return (
			element?.closest(
				"[data-step-id], [data-testid*='step'], [data-testid*='message'], article, .group",
			) || element?.parentElement
		);
	}

	function inspectButton(inspection) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = INSPECT_ACTION_CLASS;
		button.dataset.assistantMessageId = String(inspection.assistant_message_id);
		button.textContent = "Inspect answer";
		Object.assign(button.style, {
			display: "block",
			margin: "4px 0 0 auto",
			padding: "2px 7px",
			border: "1px solid color-mix(in srgb, currentColor 18%, transparent)",
			borderRadius: "6px",
			background: "transparent",
			color: "inherit",
			fontSize: "11px",
			lineHeight: "18px",
			cursor: "pointer",
			opacity: "0.72",
		});
		button.addEventListener("click", () => openInspector(inspection));
		return button;
	}

	function renderInspectorActions() {
		if (productState.view !== "chat" || !productState.chatId) return;
		answerInspections.forEach((inspection) => {
			const messageId = String(inspection.assistant_message_id || "");
			if (
				!messageId ||
				document.querySelector(
					`.${INSPECT_ACTION_CLASS}[data-assistant-message-id="${CSS.escape(messageId)}"]`,
				)
			) {
				return;
			}
			const answer = answerElement(inspection);
			const container = answerContainer(answer);
			if (container) container.appendChild(inspectButton(inspection));
		});
	}

	function scheduleRenderInspectorActions() {
		if (inspectorRenderScheduled) return;
		inspectorRenderScheduled = true;
		window.requestAnimationFrame(() => {
			inspectorRenderScheduled = false;
			renderInspectorActions();
		});
	}

	function displayValue(value) {
		if (value === null || value === undefined || value === "")
			return "Not recorded";
		if (typeof value === "boolean") return value ? "Yes" : "No";
		if (Array.isArray(value)) return value.length ? value.join(", ") : "None";
		return String(value);
	}

	function section(panel, title) {
		const block = document.createElement("section");
		const heading = document.createElement("h3");
		heading.textContent = title;
		Object.assign(heading.style, {
			margin: "14px 0 7px",
			fontSize: "13px",
			fontWeight: "650",
		});
		block.appendChild(heading);
		panel.appendChild(block);
		return block;
	}

	function field(parent, label, value) {
		const row = document.createElement("div");
		const key = document.createElement("span");
		const rendered = document.createElement("span");
		key.textContent = `${label}: `;
		key.style.fontWeight = "600";
		rendered.textContent = displayValue(value);
		row.append(key, rendered);
		Object.assign(row.style, { margin: "3px 0", overflowWrap: "anywhere" });
		parent.appendChild(row);
	}

	function openInspector(inspection) {
		removeElement(INSPECTOR_ID);
		const toolbar = document.getElementById(TOOLBAR_ID);
		const toolbarTop = toolbar?.getBoundingClientRect().top;
		const protectedBottom =
			typeof toolbarTop === "number"
				? Math.max(150, window.innerHeight - toolbarTop + 8)
				: 150;
		const panel = document.createElement("aside");
		panel.id = INSPECTOR_ID;
		panel.setAttribute("role", "dialog");
		panel.setAttribute("aria-label", "Answer Inspector");
		Object.assign(panel.style, {
			position: "fixed",
			top: "68px",
			right: "16px",
			bottom: `${protectedBottom}px`,
			zIndex: "40",
			width: "min(420px, calc(100vw - 32px))",
			padding: "14px 16px",
			overflowY: "auto",
			border: "1px solid color-mix(in srgb, currentColor 18%, transparent)",
			borderRadius: "12px",
			background: "var(--background, #fff)",
			color: "inherit",
			boxShadow: "0 10px 35px rgba(0, 0, 0, 0.18)",
			fontSize: "12px",
			lineHeight: "1.45",
			boxSizing: "border-box",
		});
		const header = document.createElement("div");
		Object.assign(header.style, {
			display: "flex",
			justifyContent: "space-between",
			alignItems: "center",
			gap: "10px",
		});
		const title = document.createElement("h2");
		title.textContent = "Answer Inspector";
		Object.assign(title.style, { margin: "0", fontSize: "16px" });
		const close = document.createElement("button");
		close.type = "button";
		close.textContent = "Close";
		close.setAttribute("aria-label", "Close Answer Inspector");
		close.addEventListener("click", () => panel.remove());
		header.append(title, close);
		panel.appendChild(header);

		const overview = inspection.overview || {};
		const overviewSection = section(panel, "Overview");
		field(overviewSection, "Requested mode", overview.requested_mode);
		field(overviewSection, "Effective mode", overview.effective_mode);
		field(
			overviewSection,
			"Authoritative context",
			overview.authoritative_context === "langgraph"
				? "LangGraph"
				: overview.authoritative_context === "native"
					? "Native fallback"
					: overview.authoritative_context,
		);
		field(overviewSection, "Graph executed", overview.graph_executed);
		field(
			overviewSection,
			"Native fallback used",
			overview.native_fallback_used,
		);
		field(overviewSection, "Route", overview.route);
		field(overviewSection, "Intent", overview.route_intent);
		field(overviewSection, "Context profile", overview.context_profile);

		const summary = inspection.evidence_summary || {};
		const summarySection = section(panel, "Evidence summary");
		field(
			summarySection,
			"Retrieved candidates",
			summary.retrieved_candidate_count,
		);
		field(
			summarySection,
			"Reranked candidates",
			summary.reranked_candidate_count,
		);
		field(summarySection, "Selected evidence", summary.selected_evidence_count);
		field(
			summarySection,
			"Selected context tokens",
			summary.selected_context_tokens,
		);
		field(summarySection, "Final prompt tokens", summary.final_prompt_tokens);
		field(summarySection, "Evidence valid", summary.evidence_validation);

		const sourcesSection = section(panel, "Selected sources");
		const sources = Array.isArray(inspection.selected_sources)
			? inspection.selected_sources
			: [];
		if (!sources.length) field(sourcesSection, "Evidence", null);
		sources.forEach((source) => {
			const item = document.createElement("article");
			Object.assign(item.style, {
				margin: "7px 0",
				padding: "8px",
				borderRadius: "8px",
				background: "color-mix(in srgb, currentColor 5%, transparent)",
			});
			field(item, "Source", source.source_label || source.source);
			field(item, "Excerpt", source.excerpt);
			field(item, "Rank", source.rank);
			field(item, "Score", source.score);
			field(
				item,
				"Source chat",
				source.source_chat_title || source.source_chat_id,
			);
			field(item, "Messages", source.message_range || source.message_ids);
			field(item, "Timestamp", source.timestamp);
			field(item, "Filename", source.filename);
			field(item, "Document ID", source.document_id);
			field(item, "Chunk", source.chunk_index ?? source.chunk_id);
			sourcesSection.appendChild(item);
		});

		const diagnostics = inspection.retrieval_diagnostics || {};
		const diagnosticsSection = section(panel, "Retrieval diagnostics");
		field(
			diagnosticsSection,
			"Document fallback used",
			diagnostics.document_fallback_used,
		);
		field(
			diagnosticsSection,
			"Evidence valid",
			diagnostics.evidence_validation,
		);
		field(
			diagnosticsSection,
			"Dropped candidates",
			diagnostics.dropped_candidate_count,
		);
		field(diagnosticsSection, "Retrieval errors", diagnostics.retrieval_errors);
		const reasons = (diagnostics.dropped_candidates || [])
			.map((item) => item.reason)
			.filter(Boolean);
		field(diagnosticsSection, "Recorded drop reasons", [...new Set(reasons)]);

		const documents = Array.isArray(inspection.documents)
			? inspection.documents
			: [];
		if (documents.length) {
			const documentsSection = section(panel, "Documents");
			documents.forEach((documentRow) => {
				const label = `${displayValue(documentRow.filename)} — ${displayValue(documentRow.status)}`;
				field(
					documentsSection,
					label,
					`${documentRow.chunk_count ?? "Not recorded"} chunks; selected: ${
						documentRow.selected ? "Yes" : "No"
					}`,
				);
			});
		}
		document.body.appendChild(panel);
		close.focus();
	}

	function scheduleRenderControls() {
		if (renderScheduled) return;
		renderScheduled = true;
		window.requestAnimationFrame(() => {
			renderScheduled = false;
			renderControls();
		});
	}

	function synchronizeNativeNewChat() {
		document.querySelectorAll("#new-chat-button").forEach((button) => {
			if (!button.closest(`#${HOME_ID}`)) {
				button.id = "chainlit-native-new-chat-button";
				button.setAttribute("aria-hidden", "true");
				button.style.display = "none";
			}
		});
	}

	function synchronizeGlobalHeader() {
		Array.from(document.querySelectorAll("body *"))
			.filter(
				(element) =>
					element.children.length === 0 &&
					(element.textContent || "").trim().toLowerCase() === "readme",
			)
			.forEach((label) => {
				const control = label.closest("a, button") || label;
				control.style.display = "none";
				control.setAttribute("aria-hidden", "true");
			});
	}

	function synchronizeSidebarStatus() {
		document
			.querySelectorAll(
				"[id^='thread-'] [data-sidebar='menu-button'] span.truncate",
			)
			.forEach((label) => {
				const text = (label.textContent || "").trim();
				const activeTitle = text.replace(/\s*·\s*active$/i, "");
				if (activeTitle !== text) {
					label.textContent = activeTitle;
					return;
				}
				const endedTitle = text.replace(/\s*·\s*Ended$/i, "");
				if (endedTitle === text) return;
				label.textContent = endedTitle;
				const badge = document.createElement("span");
				badge.textContent = "Ended";
				badge.dataset.chatStatus = "ended";
				Object.assign(badge.style, {
					flex: "none",
					padding: "1px 5px",
					borderRadius: "999px",
					background: "color-mix(in srgb, currentColor 10%, transparent)",
					fontSize: "10px",
					lineHeight: "16px",
					opacity: "0.7",
				});
				label.parentElement?.appendChild(badge);
			});
	}

	function setComposerEnabled(enabled) {
		document
			.querySelectorAll("textarea, [contenteditable='true']")
			.forEach((element) => {
				if ("disabled" in element) element.disabled = !enabled;
				element.setAttribute("aria-disabled", String(!enabled));
				element.style.pointerEvents = enabled ? "" : "none";
				element.style.opacity = enabled ? "" : "0.55";
			});
	}

	function setNativeHomeBrandingVisible(visible) {
		if (visible) {
			document
				.querySelectorAll("[data-memory-native-home-brand]")
				.forEach((element) => {
					element.style.display = element.dataset.previousDisplay || "";
					delete element.dataset.previousDisplay;
					delete element.dataset.memoryNativeHomeBrand;
				});
			return;
		}
		const brandLabel = Array.from(document.querySelectorAll("main *")).find(
			(element) =>
				element.children.length === 0 &&
				(element.textContent || "").trim() === "Chainlit",
		);
		const brand = brandLabel?.parentElement;
		if (!brand || brand.dataset.memoryNativeHomeBrand) return;
		brand.dataset.previousDisplay = brand.style.display || "";
		brand.dataset.memoryNativeHomeBrand = "true";
		brand.style.display = "none";
	}

	function renderHome(show) {
		removeElement(HOME_ID);
		setNativeHomeBrandingVisible(!show);
		if (!show) return;
		removeElement(TOOLBAR_ID);
		const home = document.createElement("section");
		home.id = HOME_ID;
		Object.assign(home.style, {
			position: "absolute",
			inset: "18% 0 auto",
			zIndex: "2",
			maxWidth: "720px",
			margin: "0 auto",
			padding: "16px",
			textAlign: "center",
			pointerEvents: "none",
		});
		home.innerHTML =
			"<h1>Memory Retrieval Chatbot</h1>" +
			"<p>Send a message to start a new chat.</p>";
		(document.querySelector("main") || document.body).appendChild(home);
		setNativeHomeBrandingVisible(false);
		synchronizeNativeNewChat();
		synchronizeGlobalHeader();
	}

	function applyProductState(data) {
		hideLifecycleOverlay();
		const previousChatId = productState.chatId;
		productState = {
			view: data.view,
			active: data.active,
			chatId: data.chat_id || null,
		};
		const isHome = data.view === "home";
		if (isHome || previousChatId !== productState.chatId) {
			answerInspections = [];
			removeElement(INSPECTOR_ID);
			document
				.querySelectorAll(`.${INSPECT_ACTION_CLASS}`)
				.forEach((item) => item.remove());
		}
		removeElement(TOOLBAR_ID);
		renderHome(isHome);
		setComposerEnabled(data.active !== false);
		document.body.dataset.memoryChatView = data.view || "";
		document.body.dataset.memoryChatActive =
			data.active === null || data.active === undefined
				? ""
				: String(data.active);
		renderControls();
		synchronizeNativeNewChat();
		synchronizeSidebarStatus();
	}

	function applyAnswerInspections(data) {
		if (!data.chat_id || data.chat_id !== productState.chatId) return;
		answerInspections = Array.isArray(data.inspections) ? data.inspections : [];
		document
			.querySelectorAll(`.${INSPECT_ACTION_CLASS}`)
			.forEach((item) => item.remove());
		removeElement(INSPECTOR_ID);
		scheduleRenderInspectorActions();
	}

	window.addEventListener("message", (event) => {
		const data = event.data;
		if (!data || data.source !== SOURCE) return;
		if (data.command === "product-state") applyProductState(data);
		if (data.command === "answer-inspections") applyAnswerInspections(data);
		if (data.command === "refresh-sidebar") window.location.reload();
		if (data.command === "navigate-home") window.location.assign("/");
		if (data.command === "product-error" && data.message) {
			window.alert(String(data.message).slice(0, 240));
		}
		if (data.command === "consolidation-log") {
			openConsolidationLog(data.batches || []);
		}
	});

	new MutationObserver(() => {
		setComposerEnabled(productState.active !== false);
		synchronizeNativeNewChat();
		synchronizeGlobalHeader();
		synchronizeSidebarStatus();
		const toolbar = document.getElementById(TOOLBAR_ID);
		const composer = visibleComposer();
		const composerReady = Boolean(
			composer?.closest("#message-composer") || composer?.closest("form"),
		);
		if (
			productState.view !== "home" &&
			productState.chatId &&
			(!toolbar || (composerReady && toolbar.dataset.mount !== "composer"))
		) {
			scheduleRenderControls();
		}
		if (answerInspections.length) scheduleRenderInspectorActions();
	}).observe(document.documentElement, { childList: true, subtree: true });

	synchronizeNativeNewChat();
	synchronizeGlobalHeader();

	// ── Consolidation Log Panel ──────────────────────────────────────────
	const CONSOLIDATION_ID = "memory-consolidation-log";

	function openConsolidationLog(batches) {
		removeElement(CONSOLIDATION_ID);
		if (!batches.length) {
			window.alert(
				"No consolidation log entries for this chat yet. Send messages to trigger memory extraction.",
			);
			return;
		}

		const panel = document.createElement("aside");
		panel.id = CONSOLIDATION_ID;
		panel.setAttribute("role", "dialog");
		panel.setAttribute("aria-label", "Memory Consolidation Log");
		Object.assign(panel.style, {
			position: "fixed",
			top: "68px",
			right: "16px",
			bottom: "120px",
			zIndex: "40",
			width: "min(480px, calc(100vw - 32px))",
			padding: "14px 16px",
			overflowY: "auto",
			border: "1px solid color-mix(in srgb, currentColor 18%, transparent)",
			borderRadius: "12px",
			background: "var(--background, #fff)",
			color: "inherit",
			boxShadow: "0 10px 35px rgba(0, 0, 0, 0.18)",
			fontSize: "12px",
			lineHeight: "1.45",
			boxSizing: "border-box",
		});

		const header = document.createElement("div");
		Object.assign(header.style, {
			display: "flex",
			justifyContent: "space-between",
			alignItems: "center",
			gap: "10px",
		});
		const title = document.createElement("h2");
		title.textContent = "Consolidation Log";
		Object.assign(title.style, { margin: "0", fontSize: "16px" });
		const close = document.createElement("button");
		close.type = "button";
		close.textContent = "Close";
		close.addEventListener("click", () => panel.remove());
		header.append(title, close);
		panel.appendChild(header);

		const summary = document.createElement("p");
		summary.textContent =
			batches.length + " batch" + (batches.length !== 1 ? "es" : "");
		summary.style.cssText = "margin:8px 0;opacity:0.7;font-size:11px;";
		panel.appendChild(summary);

		batches.forEach((batch) => {
			const section = document.createElement("section");
			Object.assign(section.style, {
				margin: "10px 0",
				padding: "10px",
				border: "1px solid color-mix(in srgb, currentColor 10%, transparent)",
				borderRadius: "8px",
			});

			const batchHead = document.createElement("details");
			const summary = document.createElement("summary");
			summary.textContent =
				"Batch [" +
				(batch.batch.message_ids || []).join(", ") +
				"] · " +
				(batch.batch.profile || "unknown");
			summary.style.cssText = "cursor:pointer;font-weight:600;font-size:12px;";
			batchHead.appendChild(summary);

			const msgDiv = document.createElement("div");
			msgDiv.style.cssText = "margin-top:6px;font-size:11px;opacity:0.8;";
			(batch.batch.messages || []).forEach((msg) => {
				const line = document.createElement("div");
				line.textContent =
					"[" + msg.role + "] " + (msg.content || "").slice(0, 400);
				msgDiv.appendChild(line);
			});
			batchHead.appendChild(msgDiv);
			section.appendChild(batchHead);

			const entriesDiv = document.createElement("div");
			entriesDiv.style.cssText = "margin-top:8px;";
			(batch.entries || []).forEach((entry) => {
				const row = document.createElement("div");
				row.style.cssText =
					"display:flex;align-items:flex-start;gap:6px;padding:3px 0;";

				const dot = document.createElement("span");
				dot.textContent = entry.status === "used" ? "🟢" : "🔴";
				dot.style.cssText = "flex:none;font-size:14px;";
				row.appendChild(dot);

				const info = document.createElement("div");
				info.style.cssText = "flex:1;min-width:0;";
				if (entry.status === "used") {
					info.textContent =
						"[" +
						(entry.category || "?") +
						"] " +
						(entry.key || entry.memory_id || "") +
						": " +
						(entry.value || "").slice(0, 150);
				} else {
					info.textContent =
						"[" +
						(entry.category || "?") +
						"] " +
						(entry.key || "?") +
						": " +
						(entry.value || "").slice(0, 120) +
						" — DROPPED: " +
						(entry.drop_reason || "unknown");
				}
				row.appendChild(info);
				entriesDiv.appendChild(row);
			});
			section.appendChild(entriesDiv);
			panel.appendChild(section);
		});

		document.body.appendChild(panel);
		close.focus();
	}
})();
