# PromptFix

<p align="center">
  <strong>The Open-Source Prompt Engineering Workbench</strong><br>
  <em>Stop writing bad prompts. Start shipping better AI code agents.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-167%20passing-success?style=flat-square&logo=pytest" alt="Tests">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/provider-Groq%20%7C%20Ollama%20%7C%20OpenAI-orange?style=flat-square" alt="Providers">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#evaluation-center">Eval Center</a> •
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#contributing">Contributing</a>
</p>

---

## What is PromptFix?

PromptFix is a **local, open-source prompt rewriter** that turns rough coding requests into clear, actionable prompts for AI coding agents.

Select text anywhere → Right-click or press a hotkey → Get an optimized prompt.

**Input:**
```
kral login token refresh bozuldu başka yeri bozma
```

**Output:**
```
Investigate and fix the login token refresh issue with minimal, targeted
changes. Inspect the existing auth/session/token refresh flow first, avoid
unrelated refactors or config/secrets changes, run relevant tests if
available, and summarize the root cause, fix, and verification steps.
```

---

## Features

| | Feature | Description |
|---|---|---|
| 🔄 | **One-Click Rewrite** | Right-click menu + global hotkeys (Windows) |
| 🧠 | **Intent Detection** | Auto-detects bugfix/feature/performance/review in Turkish & English |
| 🛡️ | **Output Guard** | Validates output, retries on failure, deterministic fallback |
| � | **Quality Score** | Heuristic 0-100 score with breakdown: specificity, actionability, safety, and more |
| 🔀 | **Before/After Diff** | See exactly what changed between your original and the optimized prompt |
| 💬 | **Threaded Chat** | Discord-like chat with streaming, snippets, slash commands |
| 🧪 | **Evaluation Center** | Built-in benchmark suite: 40 tests, rule-based + LLM judge |
| ⚡ | **Sub-Second Speed** | Groq for speed, Ollama for privacy, OpenAI-compatible for flexibility |
| 🔁 | **Multi-Provider Fallback** | Automatically retries with other configured providers if the primary fails |
| 🚦 | **Rate Limiting** | Per-IP request limits on all endpoints (60 req/min for optimize & chat) |

---

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Set your API key (3 options)

**Option A: .env file (easiest)**
```bash
cp .env.example .env
# Edit .env and add your key
```

**Option B: Environment variable**
```cmd
setx GROQ_API_KEY "your_groq_api_key"
```
Then open a **new terminal**.

**Option C: Config file**
```yaml
# ~/.promptfix/config.yaml
providers:
  groq:
    api_key: "your_key_here"  # Direct key (not recommended for shared systems)
```

### 3. Run setup

```bash
promptfix init
```

### 4. Start the local service

```bash
promptfix service
```

### 5. Install the Chrome extension

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder

### 6. Use it

**Browser — context menu:** Select text → Right-click → **PromptFix** → choose a mode:

| Menu item | Mode | Best for |
|---|---|---|
| Optimize Coding Prompt | `short` | General code tasks |
| Fast Rewrite | `fast` | Quick one-liner fixes |
| Agent Prompt | `agent` | Multi-step agent tasks |
| Explain Mode | `explain` | Understanding / root-cause analysis |
| Raw Rewrite | `raw` | Unstructured free-form rewrite |

**Browser — popup:** Click the extension icon to see:
- **Service status** (Connected / Offline) with provider, model, and uptime
- **Recent history** — each item shows:
  - Truncated input and output
  - **Score badge** (colour-coded: 🟢 85+, 🟡 60–84, 🔴 <60) — only shown when score data is available
  - **Copy button** — copies the optimised prompt to the clipboard; shows "Copied!" feedback for 1.5 s; falls back gracefully if Clipboard API is unavailable
- **Default mode selector** — saved to sync storage

**Diff toggle:** When a history item has diff data available, a "Diff" button appears next to the copy button. Clicking it expands an inline panel showing the before/after diff with colour coding:
- Green lines (`+`) — additions in the optimised prompt
- Red lines (`-`) — removals from the original prompt
- Grey lines — context and diff headers

The panel scrolls if the diff is long. Click "Hide" to collapse it.

**Local result cache:** Every optimize request sent through the extension (context menu or popup) is cached locally in `chrome.storage.local`:
- Stores the last **5** results only
- Entries expire after **24 hours** automatically
- Cache persists if the service goes offline — popup can still show recent history with diff
- **Never stored:** API key, service token, provider credentials, or config data
- Cache is read-only from the popup; only the background service worker writes to it

**Offline state:** When the service is not running the popup shows a red "Service offline — run: `promptfix service`" banner. Recent locally-cached results are still shown.

**Any app (hotkeys):** Select text → press `Ctrl+Alt+S` (requires `promptfix tray`)

---

## Evaluation Center

PromptFix ships with a built-in **evaluation framework** inspired by enterprise prompt testing tools.

### Run the full suite

```bash
# Rule-based scoring (fast, free)
promptfix eval

# With LLM judge (more accurate, uses tokens)
promptfix eval --judge

# Generate HTML report
promptfix eval --report eval-report.html

# CI mode (fails if score < 75)
promptfix eval --ci --threshold 80

# JSON output
promptfix eval --format json
```

### What's tested?

- **40 test cases** (20 Turkish + 20 English)
- **Bugfix, Feature, Performance, Agent, Review** intents
- **Constraint adherence**: "başka yeri bozma" → must include "minimal/targeted"
- **Output cleanliness**: No markdown fences, no "Here is" prefixes
- **Intent alignment**: Correct task type & domain detection

### Sample output

```
┌─────────────────────────┬────────┬─────────┬────────┬──────────┐
│ Test                    │ Score  │ Mode    │ Status │ Duration │
├─────────────────────────┼────────┼─────────┼────────┼──────────┤
│ Auth bugfix (TR)        │  94/100│ short   │ ✅ PASS│    450ms │
│ API 500 error (TR)      │  88/100│ short   │ ✅ PASS│    380ms │
│ New API endpoint (EN)   │  92/100│ agent   │ ✅ PASS│    520ms │
│ Dashboard render (TR)   │  85/100│ explain │ ✅ PASS│    610ms │
└─────────────────────────┴────────┴─────────┴────────┴──────────┘
Total: 40/40 passed | Avg: 89/100 | Provider: groq
```

### Add your own tests

Create `evals/my-suite.yaml`:

```yaml
tests:
  - name: "My custom test"
    input: "fix the login bug minimal changes"
    mode: short
    asserts:
      - type: contains
        value: ["minimal", "auth"]
      - type: not_contains
        value: ["refactor"]
      - type: intent_match
        task_type: bugfix
        domain: auth
```

Run it:
```bash
promptfix eval --suite evals/my-suite.yaml
```

---

## Modes

| Mode | Hotkey | Description |
|------|--------|-------------|
| **fast** | — | Ultra-compact, max 60 words |
| **short** | Ctrl+Alt+S | Compact paragraph, max 120 words (default) |
| **agent** | Ctrl+Alt+P | Structured: Task / Context / Instructions / Constraints / Validation / Deliverables |
| **raw** | Ctrl+Alt+R | Plain rewrite, no structure |
| **explain** | — | Include root-cause reasoning, max 300 words |

---

## Before / After Diff

See exactly what changed between your original prompt and the optimized version.

```bash
# Show colored diff in the terminal
promptfix once "kral login token refresh bozuldu başka yeri bozma" --diff
```

Sample output:
```
--- original
+++ optimized
-kral login token refresh bozuldu başka yeri bozma
+Investigate and fix the login token refresh issue with minimal, targeted changes.
+Inspect the existing auth/session/token refresh flow first, avoid unrelated refactors,
+run relevant tests if available, and summarize the root cause, fix, and verification steps.
```

Via the API:
```json
POST /optimize
{ "text": "fix login bug", "mode": "short", "include_diff": true }
```

Response includes a `diff` object:
```json
{
  "optimized": "Investigate and fix the login...",
  "diff": {
    "unified": "--- original\n+++ optimized\n...",
    "unchanged": false
  }
}
```

---

## Quality Score

Every rewrite is automatically scored on 5 dimensions (0–20 each, total 0–100):

| Dimension | What it checks |
|---|---|
| **specificity** | Concrete action verbs vs. vague filler |
| **conciseness** | Word count in ideal range for the mode |
| **actionability** | Deliverable / verification signals present |
| **safety** | No conversational openers or broadening words |
| **intent_alignment** | Output reflects detected task type and domain |

```bash
# Show score breakdown in terminal
promptfix once "login token bozuldu başka yeri bozma" --score
```

Sample output:
```
 Quality Score Breakdown
┌─────────────────┬───────┬─────┐
│ Dimension       │ Score │ Max │
├─────────────────┼───────┼─────┤
│ specificity     │  16   │  20 │
│ conciseness     │  20   │  20 │
│ actionability   │  15   │  20 │
│ safety          │  20   │  20 │
│ intent_alignment│  16   │  20 │
│ TOTAL           │  87   │ 100 │
└─────────────────┴───────┴─────┘
Grade: A
```

The API always returns `score_breakdown` in the `/optimize` response:
```json
{
  "optimized": "...",
  "quality_score": 87,
  "score_breakdown": {
    "total": 87,
    "grade": "A",
    "breakdown": { "specificity": 16, "conciseness": 20, ... },
    "suggestions": []
  }
}
```

---

## Agent Safety Checklist

Use the `agent-safety-checklist` preset to generate prompts that enforce safe coding-agent behavior:

- Read relevant files before writing code
- Produce a short plan before implementing
- Change only the minimum files necessary
- Never touch secrets, API keys, or production config
- Flag database migrations and breaking changes explicitly
- Run existing tests after the change
- Report changed files, test outcome, and risks

```bash
# Via CLI preset
promptfix preset use agent-safety-checklist "deploy the new payment service"

# In chat
/preset agent-safety-checklist

# With text flag
promptfix preset use agent-safety-checklist --text "login token refresh bozuldu başka yeri bozma"
```

This is the safest mode for giving tasks to AI coding agents in critical codebases.

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌──────────────┐
│  Browser Extension  │────▶│  Local Service       │────▶│  Groq / LLM  │
│  (right-click menu) │◀────│  127.0.0.1:52849     │◀────│  Provider    │
└─────────────────────┘     └─────────────────────┘     └──────────────┘
                                      ▲
                             ┌─────────┴─────────┐
                             │  Global Hotkeys    │
                             │  (Windows tray)    │
                             └───────────────────┘
```

One shared **PromptFix Core** — extension, hotkeys, CLI, and evaluation all use the same rewrite pipeline.

---

## CLI Reference

```bash
# Interactive first-time setup (choose provider, enter API key, test connection)
promptfix init

# One-shot optimize
promptfix once "login token bozuldu başka yeri bozma" --mode short

# One-shot with diff view
promptfix once "login token bozuldu başka yeri bozma" --diff

# One-shot with quality score breakdown
promptfix once "login token bozuldu başka yeri bozma" --score

# Combine both
promptfix once "login token bozuldu başka yeri bozma" --diff --score

# Start local service
promptfix service

# Start tray with global hotkeys
promptfix tray

# Interactive chat
promptfix chat
promptfix chat --mode agent

# Evaluation suite
promptfix eval
promptfix eval --judge --report report.html

# Provider management
promptfix provider list
promptfix provider use groq
promptfix provider doctor groq

# Debug tools
promptfix debug-intent "login token refresh bozuldu"
promptfix debug-rewrite "login token refresh bozuldu" --mode agent

# Reload config without restarting
curl -X POST http://127.0.0.1:52849/config/reload
```

---

## Chat Features

- **Slash commands**: `/mode`, `/clear`, `/history`, `/threads`, `/new`, `/load`, `/delete`, `/snippet`, `/help`
- **Snippets**: Save reusable prompt fragments, expand with `:snippet_name:`
- **Streaming**: Real-time token-by-token responses
- **Thread persistence**: Auto-saved JSON threads in `~/.promptfix/threads/`

---

## Security

- API keys stored **only** in environment variables or `~/.promptfix/config.yaml` (never sent to the browser)
- Local service binds to **127.0.0.1 only** — not reachable from outside your machine
- Browser extension **never sees API keys**
- **CORS restricted** to `chrome-extension://`, `moz-extension://`, and `localhost` origins — unknown web origins are blocked
- **Input length limited** to 32 000 characters per request — oversized payloads are rejected with HTTP 413
- **All endpoints protected** by the optional service token (`service.token` in config) — including `/history`, `/threads`, `/chat`, and `/suggestions`
- **Thread IDs validated** as UUID v4 on every endpoint — path-traversal attempts are rejected with HTTP 400
- Optional service token for extra authentication (`service.token` in config)
- **Live config reload** — `POST /config/reload` re-reads `~/.promptfix/config.yaml` and resets the provider without restarting the service
- **Hotkeys are Windows-only** — importing `hotkeys.py` on Linux/macOS no longer crashes; `promptfix tray` exits gracefully with an informative message
- **Rate limiting** — all endpoints have per-IP rate limits (default 300 req/min globally; `/optimize`, `/chat`, `/chat/stream` capped at 60 req/min; `/history` at 30 req/min; `/config/reload` at 10 req/min)
- **Multi-provider fallback** — if the primary LLM provider fails, PromptFix automatically tries all other configured providers before raising an error
- No SaaS backend, no user accounts, no database

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Quick start for developers:

```bash
pip install -e ".[dev]"
pytest -v
promptfix eval --ci
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built with ❤️ for the open-source AI community.</sub><br>
  <sub>If PromptFix helps you write better prompts, consider giving it a ⭐ on GitHub!</sub>
</p>
