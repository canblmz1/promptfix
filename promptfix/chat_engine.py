"""Chat engine: orchestrates conversation flow with context.

Discord-like UX:
- Slash commands: /mode, /clear, /save, /load, /threads, /help, /snippet
- Normal text: optimized via provider with thread context
- System remembers last N messages for context
"""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

from promptfix.chat_session import ChatThread, ChatMessage, save_thread, load_thread, list_threads, create_thread, delete_thread
from promptfix.config import load_config
from promptfix.rewriter import create_provider, rewrite
from promptfix.templates import SYSTEM_PROMPT


VALID_MODES = {"fast", "short", "agent", "raw", "explain"}


def _system_prompt_for_mode(mode: str) -> str:
    """Build a system prompt that includes mode instructions."""
    from promptfix.templates import MODE_INSTRUCTIONS
    mode_instr = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["short"])
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Current mode: {mode}\n"
        f"Mode instruction: {mode_instr}\n\n"
        f"You are in a conversation. Maintain continuity with previous messages. "
        f"If the user asks a follow-up, reference earlier context when relevant."
    )


class ChatResult:
    def __init__(self, content: str, mode: str, status: str, metadata: dict | None = None):
        self.content = content
        self.mode = mode
        self.status = status  # "ok", "command", "error"
        self.metadata = metadata or {}


def process_message(
    thread: ChatThread,
    text: str,
    config: dict | None = None,
    provider=None,
) -> ChatResult:
    """Process one user message. Returns result + updates thread in-memory."""
    if config is None:
        config = load_config()
    if provider is None:
        provider = create_provider(config)

    text = text.strip()
    if not text:
        return ChatResult("", thread.current_mode, "error", {"error": "Empty message"})

    # Expand snippets before processing
    from promptfix.snippets import expand_snippets
    text = expand_snippets(text)

    # --- Slash commands ---
    if text.startswith("/"):
        return _handle_command(thread, text, config)

    # --- Normal chat: optimize with context ---
    thread.add_message("user", text, mode=thread.current_mode)

    # Build messages with conversation context
    context_msgs = thread.get_context_messages(limit=10)
    messages = [{"role": "system", "content": _system_prompt_for_mode(thread.current_mode)}]

    # Add context from thread (excluding the last user message since we'll add it)
    for msg in context_msgs[:-1]:
        messages.append(msg)

    # Add the current message with intent
    messages.append({"role": "user", "content": text})

    try:
        raw_output = provider.complete(messages)

        # Apply guard cleaning
        from promptfix.guard import clean_output
        cleaned = clean_output(raw_output)

        # Validate
        from promptfix.intent import parse_intent
        from promptfix.guard import validate_output
        intent = parse_intent(text)
        val_result = validate_output(cleaned, intent)

        if not val_result.valid:
            # Fallback to rewrite() for full pipeline with retry/fallback
            result = rewrite(
                text=text,
                mode=thread.current_mode,
                config=config,
                provider=provider,
                source="chat",
            )
            cleaned = result.optimized
            status = result.validation_status
            duration_ms = result.duration_ms
        else:
            status = "valid"
            duration_ms = 0

        thread.add_message("assistant", cleaned, mode=thread.current_mode, metadata={
            "validation_status": status,
            "duration_ms": duration_ms,
        })
        save_thread(thread)

        return ChatResult(
            content=cleaned,
            mode=thread.current_mode,
            status="ok",
            metadata={
                "validation_status": status,
                "duration_ms": duration_ms,
                "thread_id": thread.id,
            },
        )

    except Exception as e:
        return ChatResult(
            content=f"Error: {e}",
            mode=thread.current_mode,
            status="error",
            metadata={"error": str(e)},
        )


def process_message_stream(
    thread: ChatThread,
    text: str,
    config: dict | None = None,
    provider=None,
) -> Generator[dict[str, Any], None, None]:
    """Process one user message with streaming. Yields chunks + final result."""
    if config is None:
        config = load_config()
    if provider is None:
        provider = create_provider(config)

    text = text.strip()
    if not text:
        yield {"type": "error", "content": "Empty message"}
        return

    # Expand snippets before processing
    from promptfix.snippets import expand_snippets
    text = expand_snippets(text)

    # --- Slash commands (not streamable) ---
    if text.startswith("/"):
        result = _handle_command(thread, text, config)
        yield {"type": "result", "content": result.content, "status": result.status, "metadata": result.metadata}
        return

    # --- Normal chat: optimize with context ---
    thread.add_message("user", text, mode=thread.current_mode)

    # Build messages with conversation context
    context_msgs = thread.get_context_messages(limit=10)
    messages = [{"role": "system", "content": _system_prompt_for_mode(thread.current_mode)}]

    for msg in context_msgs[:-1]:
        messages.append(msg)

    messages.append({"role": "user", "content": text})

    full_content = ""
    try:
        # Stream chunks
        for chunk in provider.stream_complete(messages):
            full_content += chunk
            yield {"type": "chunk", "content": chunk}

        # Apply guard cleaning
        from promptfix.guard import clean_output
        cleaned = clean_output(full_content)

        # Validate
        from promptfix.intent import parse_intent
        from promptfix.guard import validate_output
        intent = parse_intent(text)
        val_result = validate_output(cleaned, intent)

        if not val_result.valid:
            # For streaming, just note validation issue but keep the streamed content
            status = "invalid_stream"
            duration_ms = 0
        else:
            status = "valid"
            duration_ms = 0

        thread.add_message("assistant", cleaned, mode=thread.current_mode, metadata={
            "validation_status": status,
            "duration_ms": duration_ms,
        })
        save_thread(thread)

        yield {
            "type": "result",
            "content": cleaned,
            "status": "ok",
            "metadata": {
                "validation_status": status,
                "duration_ms": duration_ms,
                "thread_id": thread.id,
            },
        }

    except Exception as e:
        yield {"type": "error", "content": f"Error: {e}"}


def _handle_command(thread: ChatThread, text: str, config: dict) -> ChatResult:
    """Parse and execute slash commands."""
    parts = text[1:].split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "mode":
        mode = arg.strip().lower()
        if mode in VALID_MODES:
            thread.set_mode(mode)
            save_thread(thread)
            return ChatResult(
                f"Mode switched to **{mode}**.",
                mode,
                "command",
            )
        modes = ", ".join(VALID_MODES)
        return ChatResult(
            f"Unknown mode. Valid modes: {modes}",
            thread.current_mode,
            "error",
        )

    elif cmd == "clear":
        thread.messages.clear()
        save_thread(thread)
        return ChatResult(
            "Thread cleared. Previous messages removed.",
            thread.current_mode,
            "command",
        )

    elif cmd == "history":
        count = len(thread.messages)
        lines = [f"Thread: {thread.title} ({count} messages)\n"]
        for i, msg in enumerate(thread.messages[-10:], 1):
            prefix = "U" if msg.role == "user" else "A" if msg.role == "assistant" else "S"
            preview = msg.content[:60].replace("\n", " ")
            if len(msg.content) > 60:
                preview += "..."
            lines.append(f"  {i}. [{prefix}] {preview}")
        return ChatResult(
            "\n".join(lines),
            thread.current_mode,
            "command",
        )

    elif cmd == "threads":
        all_threads = list_threads()[:10]
        lines = ["Recent threads:\n"]
        for i, t in enumerate(all_threads, 1):
            marker = " *" if t.id == thread.id else ""
            lines.append(f"  {i}. {t.title} ({t.id}){marker}")
        return ChatResult(
            "\n".join(lines),
            thread.current_mode,
            "command",
        )

    elif cmd == "load":
        tid = arg.strip()
        loaded = load_thread(tid)
        if loaded:
            # Return a special result that signals caller to switch thread
            return ChatResult(
                f"Loaded thread: {loaded.title} ({loaded.id})",
                loaded.current_mode,
                "command",
                metadata={"switch_to_thread": loaded},
            )
        return ChatResult(
            f"Thread not found: {tid}",
            thread.current_mode,
            "error",
        )

    elif cmd == "new":
        title = arg.strip() or "Untitled"
        new_thread = create_thread(mode=thread.current_mode, provider=config.get("provider", "groq"), title=title)
        return ChatResult(
            f"Created new thread: {new_thread.title} ({new_thread.id})",
            new_thread.current_mode,
            "command",
            metadata={"switch_to_thread": new_thread},
        )

    elif cmd == "delete":
        tid = arg.strip() or thread.id
        if delete_thread(tid):
            return ChatResult(
                f"Deleted thread: {tid}",
                thread.current_mode,
                "command",
            )
        return ChatResult(
            f"Thread not found: {tid}",
            thread.current_mode,
            "error",
        )

    elif cmd == "snippet":
        return _handle_snippet_command(thread, arg)

    elif cmd == "preset":
        return _handle_preset_command(thread, arg, config)

    elif cmd == "help":
        help_text = """\
**PromptFix Chat Commands**

`/mode <fast|short|agent|raw|explain>` — Switch optimization mode
`/clear` — Clear current thread messages
`/history` — Show recent messages in thread
`/threads` — List all saved threads
`/new [title]` — Create a new thread
`/load <id>` — Load a thread by ID
`/delete [id]` — Delete current or specified thread
`/snippet add <name> <content>` — Save a snippet
`/snippet list` — List saved snippets
`/snippet use <name>` — Insert a snippet
`/snippet delete <name>` — Delete a snippet
`/preset list` — List available presets
`/preset use <name>` — Apply a preset to next message
`/help` — Show this help

**Snippets:**
Use `:snippet_name:` in any message to auto-expand a saved snippet.

**Modes:**
- **fast**: Ultra-compact, 60 words
- **short**: Compact paragraph, 120 words
- **raw**: Clean rewrite, no structure
- **agent**: Structured output (Task, Context, Instructions...)
- **explain**: Include root-cause reasoning
"""
        return ChatResult(help_text, thread.current_mode, "command")

    else:
        return ChatResult(
            f"Unknown command: /{cmd}. Type /help for available commands.",
            thread.current_mode,
            "error",
        )


def _handle_snippet_command(thread: ChatThread, arg: str) -> ChatResult:
    """Handle /snippet subcommands."""
    from promptfix.snippets import add_snippet, get_snippet, delete_snippet, list_snippets

    parts = arg.strip().split(maxsplit=1)
    if not parts:
        return ChatResult(
            "Usage: /snippet add <name> <content> | /snippet list | /snippet use <name> | /snippet delete <name>",
            thread.current_mode,
            "command",
        )

    subcmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    if subcmd == "add":
        snippet_parts = rest.split(maxsplit=1)
        if len(snippet_parts) < 2:
            return ChatResult(
                "Usage: /snippet add <name> <content>",
                thread.current_mode,
                "error",
            )
        name, content = snippet_parts
        if add_snippet(name, content):
            return ChatResult(
                f"Snippet **{name}** saved.",
                thread.current_mode,
                "command",
            )
        return ChatResult(
            "Failed to save snippet.",
            thread.current_mode,
            "error",
        )

    elif subcmd == "list":
        snippets = list_snippets()
        if not snippets:
            return ChatResult(
                "No snippets saved. Use `/snippet add <name> <content>` to create one.",
                thread.current_mode,
                "command",
            )
        lines = ["Saved snippets:\n"]
        for name, preview in snippets:
            lines.append(f"  **{name}**: {preview}")
        return ChatResult(
            "\n".join(lines),
            thread.current_mode,
            "command",
        )

    elif subcmd == "use":
        name = rest.strip()
        content = get_snippet(name)
        if content:
            return ChatResult(
                f"**{name}**: {content}",
                thread.current_mode,
                "command",
            )
        return ChatResult(
            f"Snippet not found: {name}",
            thread.current_mode,
            "error",
        )

    elif subcmd == "delete":
        name = rest.strip()
        if delete_snippet(name):
            return ChatResult(
                f"Snippet **{name}** deleted.",
                thread.current_mode,
                "command",
            )
        return ChatResult(
            f"Snippet not found: {name}",
            thread.current_mode,
            "error",
        )

    else:
        return ChatResult(
            f"Unknown snippet command: {subcmd}. Use add, list, use, or delete.",
            thread.current_mode,
            "error",
        )


def _handle_preset_command(thread: ChatThread, arg: str, config: dict) -> ChatResult:
    """Handle /preset subcommands."""
    from promptfix.presets import list_presets, get_preset

    parts = arg.strip().split(maxsplit=1)
    if not parts or parts[0].lower() == "list":
        presets = list_presets()
        lines = ["Available presets:\n"]
        for pname, pdesc, source in presets:
            tag = "(builtin)" if source == "builtin" else "(user)"
            lines.append(f"  **{pname}** {tag} — {pdesc}")
        lines.append("\nUse `/preset use <name>` then send your text.")
        return ChatResult("\n".join(lines), thread.current_mode, "command")

    subcmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    if subcmd == "use":
        name = rest.strip()
        preset = get_preset(name)
        if not preset:
            return ChatResult(
                f"Preset not found: {name}. Use `/preset list` to see available presets.",
                thread.current_mode,
                "error",
            )
        thread.pending_preset = name  # type: ignore[attr-defined]
        return ChatResult(
            f"Preset **{name}** armed. Send your text and it will be applied.",
            thread.current_mode,
            "command",
        )

    return ChatResult(
        f"Unknown preset command: {subcmd}. Use list or use.",
        thread.current_mode,
        "error",
    )


def get_suggestions(text: str, thread: ChatThread, limit: int = 5) -> list[dict[str, str]]:
    """Get autocomplete suggestions based on input text.

    Returns suggestions from:
    - Snippet names (:name: syntax)
    - Recent user messages
    - Slash commands
    """
    suggestions = []
    text_lower = text.lower()

    # Snippet suggestions when typing :name
    if text.startswith(":") or ":" in text:
        from promptfix.snippets import list_snippets
        for name, preview in list_snippets():
            if text_lower in f":{name}:" or text_lower.strip(":") in name.lower():
                suggestions.append({
                    "type": "snippet",
                    "label": f":{name}:",
                    "detail": preview,
                })

    # Slash command suggestions
    if text.startswith("/"):
        commands = [
            ("/mode ", "Switch optimization mode"),
            ("/clear", "Clear thread messages"),
            ("/history", "Show message history"),
            ("/threads", "List threads"),
            ("/new ", "Create new thread"),
            ("/load ", "Load thread by ID"),
            ("/delete ", "Delete thread"),
            ("/snippet ", "Manage snippets"),
            ("/help", "Show help"),
        ]
        for cmd, desc in commands:
            if cmd.lower().startswith(text_lower):
                suggestions.append({
                    "type": "command",
                    "label": cmd.strip(),
                    "detail": desc,
                })

    # Recent message suggestions for non-slash, non-snippet text
    if not text.startswith("/") and not text.startswith(":"):
        seen = set()
        for msg in reversed(thread.messages):
            if msg.role == "user" and msg.content.lower().startswith(text_lower) and msg.content != text:
                if msg.content not in seen:
                    seen.add(msg.content)
                    suggestions.append({
                        "type": "history",
                        "label": msg.content[:50] + ("..." if len(msg.content) > 50 else ""),
                        "detail": "Recent message",
                    })
                    if len(suggestions) >= limit:
                        break

    return suggestions[:limit]
