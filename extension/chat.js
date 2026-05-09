// PromptFix Extension Chat UI
// Connects to local service /chat/stream endpoint for Discord-like UX.

const SERVICE_URL_DEFAULT = "http://127.0.0.1:52849";

// State
let currentThreadId = null;
let currentMode = "short";
let isLoading = false;
let messages = [];
let streamingEl = null;
let streamingContent = "";

// Autocomplete state
let autocompleteIndex = -1;
let autocompleteItems = [];

// DOM refs
const els = {
  chatArea: document.getElementById("chatArea"),
  inputBox: document.getElementById("inputBox"),
  sendBtn: document.getElementById("sendBtn"),
  modeBadge: document.getElementById("modeBadge"),
  modeBar: document.getElementById("modeBar"),
  threadTitle: document.getElementById("threadTitle"),
  statusText: document.getElementById("statusText"),
  drawer: document.getElementById("drawer"),
  overlay: document.getElementById("overlay"),
  openDrawer: document.getElementById("openDrawer"),
  closeDrawer: document.getElementById("closeDrawer"),
  threadList: document.getElementById("threadList"),
  autocomplete: document.getElementById("autocomplete"),
};

// --- Helpers ---

async function getServiceUrl() {
  const items = await chrome.storage.sync.get({ serviceUrl: SERVICE_URL_DEFAULT });
  return items.serviceUrl.replace(/\/+$/, "");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatTime() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function setStatus(text, ok = true) {
  els.statusText.textContent = text;
  els.statusText.style.color = ok ? "#4ade80" : "#f85149";
}

function setMode(mode) {
  currentMode = mode;
  els.modeBadge.textContent = mode;
  document.querySelectorAll(".mode-chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.mode === mode);
  });
}

// --- Message rendering ---

function formatContent(content) {
  return escapeHtml(content)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/\*(.+?)\*/g, "<i>$1</i>")
    .replace(/`(.+?)`/g, '<code style="background:#0d1117;padding:1px 4px;border-radius:3px;">$1</code>')
    .replace(/\n/g, "<br>");
}

function addMessage(role, content, meta = "") {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerHTML = formatContent(content);

  if (meta) {
    const metaDiv = document.createElement("div");
    metaDiv.className = "message-meta";
    metaDiv.textContent = meta;
    div.appendChild(metaDiv);
  }

  els.chatArea.appendChild(div);
  els.chatArea.scrollTop = els.chatArea.scrollHeight;
  return div;
}

function clearChat() {
  els.chatArea.innerHTML = "";
  messages = [];
}

function showStreaming() {
  const div = document.createElement("div");
  div.className = "streaming";
  div.id = "streamingMessage";
  els.chatArea.appendChild(div);
  els.chatArea.scrollTop = els.chatArea.scrollHeight;
  streamingEl = div;
  streamingContent = "";
}

function appendStreamingChunk(chunk) {
  if (!streamingEl) return;
  streamingContent += chunk;
  streamingEl.innerHTML = formatContent(streamingContent);
  els.chatArea.scrollTop = els.chatArea.scrollHeight;
}

function finishStreaming(meta = "") {
  if (!streamingEl) return;
  streamingEl.className = "message assistant";
  streamingEl.id = "";
  if (meta) {
    const metaDiv = document.createElement("div");
    metaDiv.className = "message-meta";
    metaDiv.textContent = meta;
    streamingEl.appendChild(metaDiv);
  }
  streamingEl = null;
  streamingContent = "";
}

function removeStreaming() {
  if (streamingEl) {
    streamingEl.remove();
    streamingEl = null;
    streamingContent = "";
  }
}

// --- Autocomplete ---

function showAutocomplete(items) {
  if (!items || items.length === 0) {
    hideAutocomplete();
    return;
  }
  autocompleteItems = items;
  autocompleteIndex = -1;
  els.autocomplete.innerHTML = "";
  items.forEach((item, idx) => {
    const div = document.createElement("div");
    div.className = "autocomplete-item";
    div.dataset.index = idx;
    const typeClass = item.type || "command";
    div.innerHTML = `
      <span class="label">${escapeHtml(item.label)}</span>
      <span class="type ${typeClass}">${escapeHtml(item.type)}</span>
    `;
    div.addEventListener("click", () => selectAutocomplete(idx));
    els.autocomplete.appendChild(div);
  });
  els.autocomplete.classList.add("show");
}

function hideAutocomplete() {
  els.autocomplete.classList.remove("show");
  autocompleteItems = [];
  autocompleteIndex = -1;
}

function selectAutocomplete(index) {
  if (index < 0 || index >= autocompleteItems.length) return;
  const item = autocompleteItems[index];
  if (item.type === "snippet") {
    els.inputBox.value = els.inputBox.value.replace(/:[^\s]*$/, item.label);
  } else if (item.type === "command") {
    els.inputBox.value = item.label + " ";
  } else {
    els.inputBox.value = item.label;
  }
  hideAutocomplete();
  els.inputBox.focus();
}

function updateAutocompleteSelection() {
  const items = els.autocomplete.querySelectorAll(".autocomplete-item");
  items.forEach((item, idx) => {
    item.classList.toggle("selected", idx === autocompleteIndex);
  });
}

async function fetchSuggestions(text) {
  if (!text || text.length < 1) {
    hideAutocomplete();
    return;
  }
  const serviceUrl = await getServiceUrl();
  try {
    const resp = await fetch(`${serviceUrl}/suggestions?text=${encodeURIComponent(text)}&thread_id=${currentThreadId || ""}`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.suggestions && data.suggestions.length > 0) {
      showAutocomplete(data.suggestions);
    } else {
      hideAutocomplete();
    }
  } catch (e) {
    hideAutocomplete();
  }
}

// --- Thread management ---

async function loadThreads() {
  const serviceUrl = await getServiceUrl();
  try {
    const resp = await fetch(`${serviceUrl}/threads`);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    renderThreadList(data.threads || []);
  } catch (e) {
    els.threadList.innerHTML = '<div style="padding:12px;color:#484f58;font-size:12px;">Service offline</div>';
  }
}

function renderThreadList(threads) {
  els.threadList.innerHTML = "";
  if (!threads.length) {
    els.threadList.innerHTML = '<div style="padding:12px;color:#484f58;font-size:12px;">No threads yet</div>';
    return;
  }
  threads.forEach((t) => {
    const div = document.createElement("div");
    div.className = "thread-item" + (t.id === currentThreadId ? " active" : "");
    div.innerHTML = `
      <div class="thread-title">${escapeHtml(t.title)}</div>
      <div class="thread-id">${t.id} | ${t.message_count} msgs | ${t.current_mode}</div>
    `;
    div.addEventListener("click", () => switchToThread(t.id));
    els.threadList.appendChild(div);
  });
}

function switchToThread(threadId) {
  currentThreadId = threadId;
  clearChat();
  setStatus("Loaded");
  els.threadTitle.textContent = threadId;
  loadThreadMessages(threadId);
  closeDrawerFn();
}

async function loadThreadMessages(threadId) {
  const serviceUrl = await getServiceUrl();
  try {
    const resp = await fetch(`${serviceUrl}/threads/${threadId}`);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const thread = await resp.json();
    setMode(thread.current_mode);
    els.threadTitle.textContent = thread.title || threadId;
    thread.messages.forEach((m) => {
      addMessage(m.role, m.content, m.timestamp);
    });
  } catch (e) {
    addMessage("system", `Failed to load thread: ${e.message}`);
  }
}

function newThread() {
  currentThreadId = null;
  clearChat();
  setMode("short");
  els.threadTitle.textContent = "New thread";
  setStatus("Ready");
}

// --- Sending messages (streaming) ---

async function sendMessage() {
  const text = els.inputBox.value.trim();
  if (!text || isLoading) return;

  // Add user message immediately
  addMessage("user", text, formatTime());
  els.inputBox.value = "";
  els.inputBox.style.height = "40px";
  hideAutocomplete();

  // Handle local commands
  if (text.startsWith("/")) {
    const localResult = handleLocalCommand(text);
    if (localResult) return;
  }

  isLoading = true;
  els.sendBtn.disabled = true;
  showStreaming();

  const serviceUrl = await getServiceUrl();
  try {
    const resp = await fetch(`${serviceUrl}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, thread_id: currentThreadId, mode: currentMode }),
    });

    if (!resp.ok) {
      removeStreaming();
      const err = await resp.json().catch(() => ({}));
      addMessage("system", err.error || `Error ${resp.status}`, formatTime());
      setStatus("Error", false);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const dataStr = line.slice(6);
          if (dataStr === "[DONE]") continue;
          try {
            const data = JSON.parse(dataStr);
            if (data.type === "chunk") {
              appendStreamingChunk(data.content);
            } else if (data.type === "error") {
              removeStreaming();
              addMessage("system", data.content, formatTime());
              setStatus("Error", false);
            } else if (data.type === "result") {
              const meta = `${data.mode || currentMode} | ${data.metadata?.validation_status || ""}`;
              finishStreaming(meta);
              currentThreadId = data.metadata?.thread_id || currentThreadId;
              setStatus("Done");
            }
          } catch (e) {
            // ignore parse errors
          }
        }
      }
    }

    // If streaming finished without explicit result
    if (streamingEl) {
      finishStreaming(currentMode);
    }

  } catch (e) {
    removeStreaming();
    addMessage("system", `Cannot connect to PromptFix service. Run: promptfix service`, formatTime());
    setStatus("Offline", false);
  } finally {
    isLoading = false;
    els.sendBtn.disabled = false;
  }
}

function handleLocalCommand(text) {
  const parts = text.slice(1).split(/\s+/);
  const cmd = parts[0].toLowerCase();

  if (cmd === "clear") {
    clearChat();
    addMessage("system", "Chat cleared.", formatTime());
    return true;
  } else if (cmd === "new") {
    newThread();
    addMessage("system", "New thread started.", formatTime());
    return true;
  } else if (cmd === "help") {
    addMessage("system", `/mode <fast|short|agent|raw|explain> — Switch mode
/clear — Clear messages
/new — Start new thread
/snippet add <name> <content> — Save snippet
/snippet list — List snippets
/snippet use <name> — Show snippet
/help — Show this help`, formatTime());
    return true;
  }
  // Other commands go to server (non-streaming fallback for commands)
  sendCommandToServer(text);
  return true;
}

async function sendCommandToServer(text) {
  isLoading = true;
  els.sendBtn.disabled = true;

  const serviceUrl = await getServiceUrl();
  try {
    const resp = await fetch(`${serviceUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, thread_id: currentThreadId, mode: currentMode }),
    });

    hideTyping();

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      addMessage("system", err.error || `Error ${resp.status}`, formatTime());
      setStatus("Error", false);
      return;
    }

    const data = await resp.json();
    currentThreadId = data.thread_id;
    els.threadTitle.textContent = currentThreadId;

    if (data.status === "command") {
      addMessage("system", data.content, formatTime());
    } else if (data.status === "error") {
      addMessage("system", data.content, formatTime());
      setStatus("Error", false);
    } else {
      const meta = `${data.mode} | ${data.metadata?.duration_ms || 0}ms | ${data.metadata?.validation_status || ""}`;
      addMessage("assistant", data.content, meta);
      setStatus("Done");
    }

    if (data.mode && data.mode !== currentMode) {
      setMode(data.mode);
    }

  } catch (e) {
    addMessage("system", `Cannot connect to PromptFix service.`, formatTime());
    setStatus("Offline", false);
  } finally {
    isLoading = false;
    els.sendBtn.disabled = false;
  }
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "typing";
  div.id = "typingIndicator";
  div.textContent = "PromptFix is thinking...";
  els.chatArea.appendChild(div);
  els.chatArea.scrollTop = els.chatArea.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById("typingIndicator");
  if (el) el.remove();
}

// --- Drawer ---

function openDrawerFn() {
  els.drawer.classList.add("open");
  els.overlay.classList.add("show");
  loadThreads();
}

function closeDrawerFn() {
  els.drawer.classList.remove("open");
  els.overlay.classList.remove("show");
}

// --- Event listeners ---

els.sendBtn.addEventListener("click", sendMessage);
els.inputBox.addEventListener("keydown", (e) => {
  if (els.autocomplete.classList.contains("show")) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      autocompleteIndex = Math.min(autocompleteIndex + 1, autocompleteItems.length - 1);
      updateAutocompleteSelection();
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      autocompleteIndex = Math.max(autocompleteIndex - 1, -1);
      updateAutocompleteSelection();
      return;
    }
    if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      if (autocompleteIndex >= 0) {
        selectAutocomplete(autocompleteIndex);
      } else if (autocompleteItems.length > 0) {
        selectAutocomplete(0);
      }
      return;
    }
    if (e.key === "Escape") {
      hideAutocomplete();
      return;
    }
  }

  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Debounced autocomplete
let suggestDebounce;
els.inputBox.addEventListener("input", () => {
  els.inputBox.style.height = "auto";
  els.inputBox.style.height = Math.min(els.inputBox.scrollHeight, 80) + "px";

  clearTimeout(suggestDebounce);
  const text = els.inputBox.value;
  if (text.startsWith("/") || text.includes(":")) {
    suggestDebounce = setTimeout(() => fetchSuggestions(text), 150);
  } else {
    hideAutocomplete();
  }
});

els.modeBar.addEventListener("click", (e) => {
  if (e.target.classList.contains("mode-chip")) {
    setMode(e.target.dataset.mode);
  }
});

els.openDrawer.addEventListener("click", openDrawerFn);
els.closeDrawer.addEventListener("click", closeDrawerFn);
els.overlay.addEventListener("click", closeDrawerFn);

// Close autocomplete when clicking outside
document.addEventListener("click", (e) => {
  if (!els.autocomplete.contains(e.target) && e.target !== els.inputBox) {
    hideAutocomplete();
  }
});

// --- Init ---

document.addEventListener("DOMContentLoaded", () => {
  setMode("short");
  getServiceUrl().then((url) => {
    fetch(`${url}/health`)
      .then(() => setStatus("Ready"))
      .catch(() => setStatus("Offline", false));
  });
});
