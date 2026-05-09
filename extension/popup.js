// PromptFix popup logic
// Fetches service status, config, history; manages default mode selection.

const SERVICE_URL_DEFAULT = "http://127.0.0.1:52849";

// --- DOM refs ---
const els = {
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  provider: document.getElementById("provider"),
  model: document.getElementById("model"),
  uptime: document.getElementById("uptime"),
  history: document.getElementById("history"),
  modeBtns: document.querySelectorAll(".mode-btn"),
};

// --- Helpers ---

async function getServiceUrl() {
  const items = await chrome.storage.sync.get({
    serviceUrl: SERVICE_URL_DEFAULT,
  });
  return items.serviceUrl.replace(/\/+$/, "");
}

function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function setStatus(ok, text) {
  els.statusDot.className = "status-dot" + (ok ? " ok" : ok === false ? " err" : "");
  els.statusText.textContent = text;
}

// --- Mode selection ---

async function loadMode() {
  const items = await chrome.storage.sync.get({ defaultMode: "short" });
  setActiveMode(items.defaultMode);
}

function setActiveMode(mode) {
  els.modeBtns.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });
}

els.modeBtns.forEach((btn) => {
  btn.addEventListener("click", async () => {
    const mode = btn.dataset.mode;
    setActiveMode(mode);
    await chrome.storage.sync.set({ defaultMode: mode });
  });
});

// --- History ---

async function loadHistory(serviceUrl) {
  try {
    const resp = await fetch(`${serviceUrl}/history?limit=5`);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    renderHistory(data.entries || []);
  } catch {
    els.history.innerHTML = '<div class="empty">Service unavailable</div>';
  }
}

function renderHistory(entries) {
  if (!entries.length) {
    els.history.innerHTML = '<div class="empty">No history yet</div>';
    return;
  }
  els.history.innerHTML = entries
    .map(
      (e) => `
    <div class="history-item">
      <div class="history-input">${escapeHtml(e.input || "")}</div>
      <div class="history-output">${escapeHtml(e.output || "")}</div>
      <div class="history-meta">${e.mode || "?"} | ${e.provider || "?"} | ${e.ms || 0}ms | ${e.status || "?"}</div>
    </div>
  `
    )
    .join("");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// --- Main status loader ---

async function loadStatus() {
  const serviceUrl = await getServiceUrl();
  setStatus(null, "Checking...");

  try {
    const [healthResp, configResp] = await Promise.all([
      fetch(`${serviceUrl}/health`).catch(() => null),
      fetch(`${serviceUrl}/config-safe`).catch(() => null),
    ]);

    if (healthResp && healthResp.ok) {
      const health = await healthResp.json();
      setStatus(true, "Connected");
      els.provider.textContent = health.provider || "—";
      els.model.textContent = health.model || "—";
      els.uptime.textContent = formatUptime(health.uptime_s || 0);
    } else {
      setStatus(false, "Offline");
      els.provider.textContent = "—";
      els.model.textContent = "—";
      els.uptime.textContent = "—";
    }

    if (configResp && configResp.ok) {
      const cfg = await configResp.json();
      if (cfg.default_mode) setActiveMode(cfg.default_mode);
    }

    await loadHistory(serviceUrl);
  } catch {
    setStatus(false, "Offline");
    els.provider.textContent = "—";
    els.model.textContent = "—";
    els.uptime.textContent = "—";
    els.history.innerHTML = '<div class="empty">Service unavailable</div>';
  }
}

// --- Actions ---

function openChat() {
  chrome.tabs.create({ url: chrome.runtime.getURL("chat.html") });
}

function openOptions() {
  chrome.runtime.openOptionsPage();
}

// --- Init ---

document.addEventListener("DOMContentLoaded", () => {
  loadMode();
  loadStatus();
});
