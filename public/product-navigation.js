(() => {
  const SOURCE = "memory-chatbot-ui";
  const CONTROL_MARKER = "__MEMORY_CHATBOT_CONTROLS__";
  const CONTROL_LABELS = new Set(["End Chat", "Fork Chat", "New Chat", "Home"]);
  const TOOLBAR_ID = "memory-chatbot-controls";
  const HOME_ID = "memory-chatbot-home";
  let productState = { view: "home", active: null };

  function removeElement(id) {
    document.getElementById(id)?.remove();
  }

  function actionButtonsFor(marker) {
    let container = marker;
    for (let depth = 0; container && depth < 6; depth += 1) {
      const buttons = Array.from(container.querySelectorAll("button")).filter((button) =>
        CONTROL_LABELS.has((button.textContent || "").trim()),
      );
      if (buttons.length >= 2) return { container, buttons };
      container = container.parentElement;
    }
    return null;
  }

  function findControlMarker() {
    return Array.from(document.querySelectorAll("p, span, div"))
      .filter((element) => (element.textContent || "").trim() === CONTROL_MARKER)
      .at(-1);
  }

  function renderControls() {
    if (productState.view === "home" || document.getElementById(TOOLBAR_ID)) return;
    const marker = findControlMarker();
    if (!marker) return;
    const found = actionButtonsFor(marker);
    if (!found) return;

    removeElement(TOOLBAR_ID);
    const toolbar = document.createElement("div");
    toolbar.id = TOOLBAR_ID;
    toolbar.setAttribute("role", "toolbar");
    toolbar.setAttribute("aria-label", "Chat lifecycle controls");
    Object.assign(toolbar.style, {
      position: "fixed",
      top: "12px",
      right: "72px",
      zIndex: "1000",
      display: "flex",
      gap: "8px",
      padding: "6px",
      borderRadius: "10px",
      background: "var(--background, rgba(20, 20, 20, 0.92))",
      boxShadow: "0 2px 12px rgba(0, 0, 0, 0.18)",
    });

    found.buttons.forEach((original) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = (original.textContent || "").trim();
      button.className = original.className;
      button.addEventListener("click", () => original.click());
      toolbar.appendChild(button);
    });
    found.container.style.display = "none";
    document.body.appendChild(toolbar);
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

  function renderHome(show) {
    removeElement(HOME_ID);
    if (!show) return;
    removeElement(TOOLBAR_ID);
    const home = document.createElement("section");
    home.id = HOME_ID;
    Object.assign(home.style, {
      position: "fixed",
      inset: "25% 15% auto 25%",
      zIndex: "50",
      maxWidth: "720px",
      padding: "32px",
      borderRadius: "18px",
      textAlign: "center",
      background: "var(--background, rgba(20, 20, 20, 0.96))",
      boxShadow: "0 8px 32px rgba(0, 0, 0, 0.16)",
    });
    home.innerHTML =
      "<h1>Memory Retrieval Chatbot</h1>" +
      "<p>Select a persisted chat from the sidebar, or use New Chat to begin.</p>";
    document.body.appendChild(home);
  }

  function applyProductState(data) {
    productState = { view: data.view, active: data.active };
    const isHome = data.view === "home";
    removeElement(TOOLBAR_ID);
    renderHome(isHome);
    setComposerEnabled(data.active !== false);
    document.body.dataset.memoryChatView = data.view || "";
    document.body.dataset.memoryChatActive =
      data.active === null || data.active === undefined ? "" : String(data.active);
    if (!isHome) window.setTimeout(renderControls, 0);
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
    renderControls();
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
