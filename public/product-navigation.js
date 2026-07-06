(() => {
  const SOURCE = "memory-chatbot-ui";
  const TOOLBAR_ID = "memory-chatbot-controls";
  const HOME_ID = "memory-chatbot-home";
  let productState = { view: "home", active: null, chatId: null };
  let renderScheduled = false;

  function removeElement(id) {
    document.getElementById(id)?.remove();
  }

  function sendLifecycleAction(action) {
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
      background: "color-mix(in srgb, var(--background, #fff) 94%, currentColor 6%)",
      fontSize: "13px",
    });

    if (productState.active === true) {
      toolbar.appendChild(lifecycleButton("End Chat", "end"));
    }
    toolbar.appendChild(lifecycleButton("Fork Chat", "fork"));
    toolbar.appendChild(lifecycleButton("New Chat", "new"));
    toolbar.appendChild(lifecycleButton("Home", "home"));
    if (!mountInChatColumn(toolbar)) toolbar.remove();
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

  function setNativeHomeContentVisible(visible) {
    const main = document.querySelector("main");
    if (!main) return;
    if (visible) {
      main.querySelectorAll(":scope > [data-memory-home-hidden]").forEach((element) => {
        element.style.display = element.dataset.previousDisplay || "";
        delete element.dataset.previousDisplay;
        delete element.dataset.memoryHomeHidden;
      });
      return;
    }
    Array.from(main.children).forEach((element) => {
      const isProductHome = element.id === HOME_ID;
      const isHeader =
        element.tagName === "HEADER" ||
        Boolean(element.querySelector("a[href*='readme']"));
      if (isProductHome || isHeader || element.dataset.memoryHomeHidden) return;
      element.dataset.previousDisplay = element.style.display || "";
      element.dataset.memoryHomeHidden = "true";
      element.style.display = "none";
    });
  }

  function renderHome(show) {
    removeElement(HOME_ID);
    setNativeHomeContentVisible(!show);
    if (!show) return;
    removeElement(TOOLBAR_ID);
    const home = document.createElement("section");
    home.id = HOME_ID;
    Object.assign(home.style, {
      position: "relative",
      maxWidth: "720px",
      margin: "18vh auto 0",
      padding: "32px",
      borderRadius: "18px",
      textAlign: "center",
      background: "var(--background, rgba(20, 20, 20, 0.96))",
      boxShadow: "0 8px 32px rgba(0, 0, 0, 0.16)",
    });
    home.innerHTML =
      "<h1>Memory Retrieval Chatbot</h1>" +
      "<p>Select a chat or start a new one.</p>" +
      '<button id="new-chat-button" type="button">New Chat</button>';
    home.querySelector("#new-chat-button").addEventListener("click", () => {
      sendLifecycleAction("new");
    });
    (document.querySelector("main") || document.body).appendChild(home);
    setNativeHomeContentVisible(false);
    synchronizeNativeNewChat();
  }

  function applyProductState(data) {
    productState = {
      view: data.view,
      active: data.active,
      chatId: data.chat_id || null,
    };
    const isHome = data.view === "home";
    removeElement(TOOLBAR_ID);
    renderHome(isHome);
    setComposerEnabled(data.active !== false);
    document.body.dataset.memoryChatView = data.view || "";
    document.body.dataset.memoryChatActive =
      data.active === null || data.active === undefined ? "" : String(data.active);
    renderControls();
    synchronizeNativeNewChat();
    synchronizeSidebarStatus();
  }

  window.addEventListener("message", (event) => {
    const data = event.data;
    if (!data || data.source !== SOURCE) return;
    if (data.command === "product-state") applyProductState(data);
    if (data.command === "refresh-sidebar") window.location.reload();
    if (data.command === "product-error" && data.message) {
      window.alert(String(data.message).slice(0, 240));
    }
  });

  new MutationObserver(() => {
    setComposerEnabled(productState.active !== false);
    synchronizeNativeNewChat();
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
  }).observe(document.documentElement, { childList: true, subtree: true });

  synchronizeNativeNewChat();
})();
