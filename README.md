# PromptFix

<p align="center">
  <strong>The Open-Source Prompt Engineering Workbench</strong><br>
  <em>Stop writing bad prompts. Start shipping better AI code agents.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-160%20passing-success?style=flat-square&logo=pytest" alt="Tests">
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
| 💬 | **Threaded Chat** | Discord-like chat with streaming, snippets, slash commands |
| 📊 | **Evaluation Center** | Built-in benchmark suite: 40 tests, rule-based + LLM judge |
| ⚡ | **Sub-Second Speed** | Groq for speed, Ollama for privacy, OpenAI-compatible for flexibility |

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
promptfix setup
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

**Browser:** Select text → Right-click → **PromptFix** → **Optimize Coding Prompt**

**Any app:** Select text → press `Ctrl+Alt+S` (requires `promptfix tray`)

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
# One-shot optimize
promptfix once "login token bozuldu başka yeri bozma" --mode short

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
