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
  quickInput: document.getElementById("quickInput"),
  quickOptimize: document.getElementById("quickOptimize"),
  quickResult: document.getElementById("quickResult"),
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

// --- Local result cache (read-only in popup) ---

async function readCache() {
  try {
    const resp = await chrome.runtime.sendMessage({ action: "getCache" });
    return Array.isArray(resp?.cache) ? resp.cache : [];
  } catch {
    return [];
  }
}

// --- Diff rendering ---

function renderDiffLines(unified) {
  if (!unified || typeof unified !== "string") return "";
  return unified
    .split("\n")
    .map((line) => {
      let cls = "diff-line-ctx";
      if (line.startsWith("+") && !line.startsWith("++")) cls = "diff-line-add";
      else if (line.startsWith("-") && !line.startsWith("--")) cls = "diff-line-del";
      else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) cls = "diff-line-hdr";
      return `<div class="${cls}">${escapeHtml(line) || "\u00a0"}</div>`;
    })
    .join("");
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
  const cacheEntries = await readCache();
  try {
    const resp = await fetch(`${serviceUrl}/history?limit=5`);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    renderHistory(data.entries || [], cacheEntries);
  } catch {
    // Service unavailable — show cache-only if we have it
    if (cacheEntries.length) {
      renderHistory([], cacheEntries);
    } else {
      els.history.innerHTML = '<div class="empty">Service unavailable</div>';
    }
  }
}

function buildHistoryItem(e, i) {
  const output = e.output || e.optimized || "";
  const diffUnified = e.diff?.unified ?? null;
  const hasDiff = diffUnified && !e.diff?.unchanged;

  const metaParts = [
    escapeHtml(e.mode || "?"),
    escapeHtml(e.provider || (e.source ? escapeHtml(e.source) : "?")),
    e.ms ? `${e.ms}ms` : "",
    escapeHtml(e.status || ""),
  ].filter(Boolean);

  return `
    <div class="history-item">
      <div class="history-input">${escapeHtml(e.input || "")}</div>
      <div class="history-header">
        <div class="history-output">${escapeHtml(output)}</div>
        <div class="history-actions">
          ${scoreBadge(e.quality_score)}
          ${hasDiff ? `<button class="diff-toggle" data-idx="${i}">Diff</button>` : ""}
          <button class="copy-btn" data-idx="${i}" title="Copy optimized prompt">Copy</button>
        </div>
      </div>
      ${metaParts.length ? `<div class="history-meta">${metaParts.join(" | ")}</div>` : ""}
      <div class="diff-view" id="diff-${i}" style="display:none;"></div>
    </div>
  `;
}

function renderHistory(entries, cacheEntries) {
  // Merge: deduplicate by output text, cache items fill diff if history item lacks it
  const seen = new Set();
  const merged = [];
  for (const e of entries) {
    const key = (e.output || e.optimized || "").slice(0, 120);
    if (!seen.has(key)) {
      seen.add(key);
      // Try to enrich with diff from matching cache entry
      if (!e.diff) {
        const cached = (cacheEntries || []).find(
          (c) => (c.output || "").slice(0, 120) === key
        );
        if (cached?.diff) e.diff = cached.diff;
        if (e.quality_score == null && cached?.quality_score != null) {
          e.quality_score = cached.quality_score;
        }
      }
      merged.push(e);
    }
  }

  // Also add cache-only entries (not in server history)
  for (const c of (cacheEntries || [])) {
    const key = (c.output || "").slice(0, 120);
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(c);
    }
  }

  if (!merged.length) {
    els.history.innerHTML = '<div class="empty">No history yet</div>';
    return;
  }

  const outputs = merged.map((e) => e.output || e.optimized || "");
  const diffs   = merged.map((e) => e.diff?.unified ?? null);

  els.history.innerHTML = merged.map((e, i) => buildHistoryItem(e, i)).join("");

  els.history.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      copyToClipboard(outputs[parseInt(btn.dataset.idx, 10)], btn);
    });
  });

  els.history.querySelectorAll(".diff-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      const panel = document.getElementById(`diff-${idx}`);
      if (!panel) return;
      const open = panel.style.display !== "none";
      if (open) {
        panel.style.display = "none";
        btn.textContent = "Diff";
      } else {
        panel.innerHTML = renderDiffLines(diffs[idx]);
        panel.style.display = "block";
        btn.textContent = "Hide";
      }
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

// --- Call the local PromptFix service ---

async function callService(text, mode, extraBody = {}) {
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
      body: JSON.stringify({ text, mode, ...extraBody }),
    });
  } catch (e) {
    throw new Error("PromptFix service is not running. Run: promptfix service");
  }

  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.error || `Service returned ${resp.status}`);
  }

  return await resp.json();
}

// --- Quick Optimize ---

els.quickOptimize.addEventListener("click", async () => {
  const text = els.quickInput.value.trim();
  if (!text) {
    els.quickResult.textContent = "Please enter some text first.";
    els.quickResult.style.display = "block";
    els.quickResult.style.color = "#f85149";
    return;
  }

  const mode = await chrome.storage.sync.get({ defaultMode: "short" }).then((s) => s.defaultMode);
  els.quickOptimize.disabled = true;
  els.quickOptimize.textContent = "Optimizing…";
  els.quickResult.style.display = "none";

  try {
    const result = await callService(text, mode, { include_diff: true });
    const output = result.optimized || "";

    // Show result inline
    els.quickResult.innerHTML = `<div style="white-space:pre-wrap;word-break:break-word;">${escapeHtml(output)}</div>`;
    els.quickResult.style.display = "block";
    els.quickResult.style.color = "#c9d1d9";

    // Auto-copy to clipboard (fire-and-forget, must not block UI)
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(output).catch(() => {});
    }

    // Refresh history so the new item appears
    const serviceUrl = await getServiceUrl();
    await loadHistory(serviceUrl);
  } catch (err) {
    els.quickResult.textContent = err.message;
    els.quickResult.style.display = "block";
    els.quickResult.style.color = "#f85149";
  } finally {
    els.quickOptimize.disabled = false;
    els.quickOptimize.textContent = "Optimize Prompt";
  }
});

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
