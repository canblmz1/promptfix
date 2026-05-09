DEV.TO ARTICLE DRAFT:

Title: I Built a Local Prompt Rewriter Because My Prompts Were Trash
Tags: #opensource #python #ai #buildinpublic #productivity

---

## The Problem

Every developer does this:

```
"fix the bug pls"
"make it faster"
"add dark mode but don't break anything"
```

And then gets Frankenstein code that breaks half the codebase.

The AI isn't dumb. **Our prompts are.**

We dump vague, emotional, half-formed thoughts into ChatGPT and expect production-ready code. It doesn't work.

## The Solution

I built [PromptFix](https://github.com/canblmz1/promptfix) — an open-source, local-first tool that rewrites your lazy prompts into structured, production-ready ones.

### Before
```
"kral login bozuldu başka yeri bozma"
```

### After
```
"Investigate and fix the login token refresh issue with minimal, targeted changes. Inspect the existing auth middleware and token validation flow first, avoid unrelated refactors..."
```

## Why Another AI Tool?

Because existing tools either:
- Are SaaS products that see your data
- Require complex setup
- Don't validate their outputs
- Don't support non-English prompts

PromptFix is different:

### 1. 100% Local
Run on Groq API or Ollama (fully offline). Your data never leaves your machine.

### 2. Evaluation Center
40 automated tests, HTML reports, CI integration. Because "it works on my machine" isn't enough.

```bash
promptfix eval run --ci --threshold 0.85
```

### 3. Browser Extension
Select text anywhere → hotkey → better prompt instantly.

### 4. Turkish Support
Because not every developer thinks in English.

### 5. Batteries Included
174 tests, MIT license, CLI + API + extension.

## Architecture

```
User Input
    ↓
[promptfix rewrite]  ← LLM (Groq/Ollama)
    ↓
Structured Prompt
    ↓
[promptfix eval run] ← 40 test cases + scoring
    ↓
Pass/Fail Report
```

## Quick Start

```bash
pip install -e git+https://github.com/canblmz1/promptfix.git
promptfix rewrite "kral su login'i bozma"
```

## What I Learned

1. **Evaluations matter.** Shipping without tests is shipping broken software. The evaluation center caught dozens of regressions.

2. **Local-first is a feature.** Developers are tired of SaaS lock-in. Having a fully offline mode (Ollama) is a selling point.

3. **Open source marketing is hard.** Writing code is 20%. Getting people to use it is 80%.

4. **Turkish developers are underserved.** Most AI tools assume English input. Supporting Turkish slang opened up a niche.

## Try It

```bash
git clone https://github.com/canblmz1/promptfix.git
cd promptfix
pip install -e ".[test]"
promptfix eval run
```

Break it. Tell me what sucks. Open an issue or PR.

---

*Built with Python and vanilla JS because I hate unnecessary complexity.*

#opensource #buildinpublic #python #ai #developerproductivity
