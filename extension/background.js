// PromptFix background service worker
// Creates context menu, coordinates with content.js, calls local service

const SERVICE_URL_DEFAULT = "http://127.0.0.1:52849";

// --- Context menu setup ---

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "promptfix-parent",
    title: "PromptFix",
    contexts: ["selection"],
  });
  chrome.contextMenus.create({
    id: "promptfix-short",
    parentId: "promptfix-parent",
    title: "Optimize Coding Prompt",
    contexts: ["selection"],
  });
  chrome.contextMenus.create({
    id: "promptfix-fast",
    parentId: "promptfix-parent",
    title: "Fast Rewrite",
    contexts: ["selection"],
  });
  chrome.contextMenus.create({
    id: "promptfix-agent",
    parentId: "promptfix-parent",
    title: "Agent Prompt",
    contexts: ["selection"],
  });
  chrome.contextMenus.create({
    id: "promptfix-explain",
    parentId: "promptfix-parent",
    title: "Explain Mode",
    contexts: ["selection"],
  });
  chrome.contextMenus.create({
    id: "promptfix-raw",
    parentId: "promptfix-parent",
    title: "Raw Rewrite",
    contexts: ["selection"],
  });
});

const MODE_MAP = {
  "promptfix-short": "short",
  "promptfix-fast": "fast",
  "promptfix-agent": "agent",
  "promptfix-explain": "explain",
  "promptfix-raw": "raw",
};

// --- Context menu click handler ---

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const mode = MODE_MAP[info.menuItemId];
  if (!mode || !tab?.id) return;

  const selectedText = info.selectionText;
  if (!selectedText || !selectedText.trim()) return;

  // Ensure content script is injected
  await ensureContentScript(tab.id);

  // Show loading toast
  sendToTab(tab.id, { action: "showLoading" });

  try {
    const result = await callService(selectedText.trim(), mode);
    sendToTab(tab.id, {
      action: "replaceSelection",
      text: result.optimized,
    });
  } catch (err) {
    sendToTab(tab.id, {
      action: "showError",
      error: err.message,
    });
  }
});

// --- Inject content script if not already present ---

async function ensureContentScript(tabId) {
  try {
    // Try pinging the content script first
    await chrome.tabs.sendMessage(tabId, { action: "ping" });
  } catch {
    // Content script not loaded — inject it
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["content.js"],
      });
    } catch (e) {
      // Some pages (chrome://, edge://) block injection — that's OK
      console.warn("Cannot inject content script:", e.message);
    }
  }
}

// --- Send message to tab with error swallowing ---

function sendToTab(tabId, message) {
  chrome.tabs.sendMessage(tabId, message).catch(() => {
    // Content script may not be injectable on this page
  });
}

// --- Call the local PromptFix service ---

async function callService(text, mode) {
  const [syncItems, localItems] = await Promise.all([
    chrome.storage.sync.get({ serviceUrl: SERVICE_URL_DEFAULT }),
    chrome.storage.local.get({ serviceToken: "" }),
  ]);
  const settings = { serviceUrl: syncItems.serviceUrl, serviceToken: localItems.serviceToken };

  const baseUrl = settings.serviceUrl.replace(/\/+$/, "");
  const url = `${baseUrl}/optimize`;
  const headers = { "Content-Type": "application/json" };
  if (settings.serviceToken) {
    headers["Authorization"] = `Bearer ${settings.serviceToken}`;
  }

  let resp;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ text, mode }),
    });
  } catch (e) {
    throw new Error(
      "PromptFix service is not running. Run: promptfix service"
    );
  }

  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.error || `Service returned ${resp.status}`);
  }

  return await resp.json();
}
