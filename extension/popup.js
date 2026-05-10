// PromptFix popup logic
// Fetches service status, config, history; manages default mode selection.

const SERVICE_URL_DEFAULT = "http://127.0.0.1:52849";

// --- DOM refs ---
const els = {
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  offlineBanner: document.getElementById("offlineBanner"),
  provider: document.getElementById("provider"),
  model: document.getElementById("model"),
  serviceStatus: document.getElementById("serviceStatus"),
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
  if (els.offlineBanner) {
    els.offlineBanner.style.display = ok === false ? "block" : "none";
  }
}

// --- Score badge helper ---

function scoreBadge(score) {
  if (score === null || score === undefined) return "";
  const color = score >= 85 ? "#3fb950" : score >= 60 ? "#d29922" : "#f85149";
  return `<span class="score-badge" style="background:${color}20;color:${color};border:1px solid ${color}40">${score}</span>`;
}

// --- Copy to clipboard helper ---

async function copyToClipboard(text, btnEl) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      // Fallback for non-HTTPS / older contexts
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    const orig = btnEl.textContent;
    btnEl.textContent = "Copied!";
    btnEl.disabled = true;
    setTimeout(() => {
      btnEl.textContent = orig;
      btnEl.disabled = false;
    }, 1500);
  } catch {
    btnEl.textContent = "Failed";
    setTimeout(() => { btnEl.textContent = "Copy"; }, 1500);
  }
}

// TODO(sprint-3): Diff UI — when popup stores last optimize result locally,
// add a "Show diff" toggle that calls compute_diff via /optimize?include_diff=true.

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

  // Store outputs for copy buttons
  const outputs = entries.map((e) => e.output || "");

  els.history.innerHTML = entries
    .map(
      (e, i) => `
    <div class="history-item">
      <div class="history-input">${escapeHtml(e.input || "")}</div>
      <div class="history-header">
        <div class="history-output">${escapeHtml(e.output || "")}</div>
        <div class="history-actions">
          ${scoreBadge(e.quality_score)}
          <button class="copy-btn" data-idx="${i}" title="Copy optimized prompt">Copy</button>
        </div>
      </div>
      <div class="history-meta">${escapeHtml(e.mode || "?")} | ${escapeHtml(e.provider || "?")} | ${e.ms || 0}ms | ${escapeHtml(e.status || "?")}</div>
    </div>
  `
    )
    .join("");

  els.history.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      copyToClipboard(outputs[parseInt(btn.dataset.idx, 10)], btn);
    });
  });
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
      els.serviceStatus.textContent = "Running";
      els.serviceStatus.style.color = "#3fb950";
      els.uptime.textContent = formatUptime(health.uptime_s || 0);
    } else {
      setStatus(false, "Offline");
      els.provider.textContent = "—";
      els.model.textContent = "—";
      els.serviceStatus.textContent = "Not running";
      els.serviceStatus.style.color = "#f85149";
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
    els.serviceStatus.textContent = "Not running";
    els.serviceStatus.style.color = "#f85149";
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
