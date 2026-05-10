"""CLI interface for PromptFix."""

from __future__ import annotations

import json
import time

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.align import Align

from promptfix.config import ensure_config, get_config_path, get_provider_config, load_config, save_config
from promptfix.rewriter import RewriteResult, create_provider, rewrite
from promptfix.eval.cli import app as eval_cli_app

app = typer.Typer(name="promptfix", help="Coding-agent prompt rewriter")
app.add_typer(eval_cli_app, name="eval", help="PromptFix Evaluation Center")
console = Console()

# ---------------------------------------------------------------------------
# Provider display names and env-var hints
# ---------------------------------------------------------------------------
_PROVIDER_LABELS = {
    "groq": "Groq (fast, free tier — recommended)",
    "openai_compatible": "OpenAI-compatible (GPT-4, Claude, etc.)",
    "ollama": "Ollama (local, no API key needed)",
}
_PROVIDER_ENV_VARS = {
    "groq": "GROQ_API_KEY",
    "openai_compatible": "OPENAI_API_KEY",
    "ollama": None,
}


@app.command()
def init():
    """Interactive first-time setup wizard — choose a provider and save your API key."""
    console.print(Panel("[bold green]PromptFix Setup Wizard[/bold green]", expand=False))
    config = load_config()

    # 1. Provider selection
    console.print("\n[bold]Which AI provider do you want to use?[/bold]")
    provider_keys = list(_PROVIDER_LABELS.keys())
    for i, key in enumerate(provider_keys, 1):
        console.print(f"  [cyan]{i}[/cyan]. {_PROVIDER_LABELS[key]}")

    choice_raw = console.input("\nEnter number [1]: ").strip() or "1"
    try:
        choice = int(choice_raw) - 1
        if choice < 0 or choice >= len(provider_keys):
            raise ValueError
    except ValueError:
        console.print("[red]Invalid choice. Defaulting to Groq.[/red]")
        choice = 0
    provider_name = provider_keys[choice]

    # 2. API key (skip for Ollama)
    env_var = _PROVIDER_ENV_VARS[provider_name]
    api_key: str | None = None
    if env_var:
        import os
        existing = os.environ.get(env_var, "")
        if existing:
            console.print(f"\n[dim]Found {env_var} in environment — using it.[/dim]")
        else:
            console.print(f"\nEnter your [bold]{env_var}[/bold] (input hidden):")
            api_key = typer.prompt("API key", hide_input=True, default="").strip()
            if not api_key:
                console.print("[yellow]No key entered. You can add it later via environment variable.[/yellow]")
                api_key = None

    # 3. Model selection (optional override)
    from promptfix.config import DEFAULT_CONFIG
    default_model = DEFAULT_CONFIG["providers"][provider_name].get("model", "")
    model_input = console.input(
        f"\nModel name [[dim]{default_model}[/dim]] (Enter to keep default): "
    ).strip()
    model = model_input if model_input else default_model

    # 4. Generate service token
    import secrets
    existing_token = config.get("service", {}).get("token", "")
    if not existing_token:
        token = secrets.token_hex(16)
        config.setdefault("service", {})["token"] = token
        console.print(f"\n[bold yellow]Service token (copy to extension settings):[/bold yellow] [cyan]{token}[/cyan]")
    else:
        console.print(f"\n[dim]Existing service token kept.[/dim]")

    # 5. Save config
    if provider_name not in config.get("providers", {}):
        config.setdefault("providers", {})[provider_name] = {}
    config["provider"] = provider_name
    config["providers"][provider_name]["model"] = model
    if api_key:
        config["providers"][provider_name]["api_key"] = api_key

    save_config(config)
    console.print(f"[green]✓[/green] Config saved to [dim]{get_config_path()}[/dim]")

    # 5. Connection test
    console.print("\n[dim]Testing connection…[/dim]")
    try:
        from promptfix.rewriter import create_provider
        provider = create_provider(config, provider_name)
        ok, msg = provider.health_check()
        if ok:
            console.print(f"[green]✓ {provider_name}: {msg}[/green]")
        else:
            console.print(f"[yellow]⚠ {provider_name}: {msg}[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        console.print("[dim]Check your API key and try again.[/dim]")
        raise typer.Exit(1)

    console.print("\n[bold green]Setup complete![/bold green] Run [cyan]promptfix service[/cyan] to start.")


@app.command()
def once(
    text: str = typer.Argument(..., help="Text to optimize"),
    mode: str = typer.Option(None, "--mode", "-m", help="Mode: fast, short, agent, raw, explain"),
):
    """Optimize a prompt once and print the result."""
    config = load_config()
    try:
        result = rewrite(text=text, mode=mode, config=config)
        console.print(Panel(result.optimized, title=f"[green]{result.mode}[/green] | {result.provider} | {result.duration_ms}ms | {result.validation_status}"))
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def service(
    host: str = typer.Option("127.0.0.1", help="Bind address"),
    port: int = typer.Option(52849, help="Port"),
):
    """Start the local HTTP service for the browser extension."""
    from promptfix.service import run_service
    run_service(host=host, port=port)


@app.command()
def tray():
    """Start the system tray app with global hotkeys."""
    from promptfix.hotkeys import run_tray
    run_tray()


@app.command()
def chat(
    thread_id: str = typer.Option(None, "--thread", "-t", help="Load existing thread"),
    mode: str = typer.Option(None, "--mode", "-m", help="Start mode: fast, short, agent, raw, explain"),
):
    """Start an interactive chat session (Discord-like UX)."""
    from promptfix.chat_engine import process_message, VALID_MODES
    from promptfix.chat_session import create_thread, load_thread

    config = load_config()
    current_mode = mode or config.get("chat", {}).get("default_mode", "short")
    if current_mode not in VALID_MODES:
        current_mode = "short"

    # Setup provider
    try:
        provider = create_provider(config)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # Load or create thread
    if thread_id:
        import re as _re
        _UUID_RE = _re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            _re.IGNORECASE,
        )
        if not _UUID_RE.match(thread_id):
            console.print(f"[red]Invalid thread ID (must be UUID v4): {thread_id}[/red]")
            raise typer.Exit(1)
        thread = load_thread(thread_id)
        if not thread:
            console.print(f"[red]Thread not found: {thread_id}[/red]")
            raise typer.Exit(1)
        console.print(f"[dim]Loaded thread:[/dim] [cyan]{thread.title}[/cyan] ({thread.id})")
    else:
        thread = create_thread(mode=current_mode, provider=config.get("provider", "groq"))
        console.print(f"[dim]New thread:[/dim] [cyan]{thread.id}[/cyan]")

    console.print()
    console.print("[bold green]PromptFix Chat[/bold green] — type /help for commands, /quit to exit")
    console.print(f"[dim]Mode: {thread.current_mode} | Provider: {config.get('provider', 'groq')}[/dim]")
    console.print("─" * 60)

    # Streaming preference from config
    use_streaming = config.get("chat", {}).get("streaming", True)

    while True:
        try:
            user_input = console.input("[bold green]You[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue
        if user_input.strip().lower() in ("/quit", "/exit", "/q"):
            console.print("[dim]Goodbye![/dim]")
            break

        # Slash commands: use non-streaming path
        if user_input.strip().startswith("/"):
            result = process_message(thread, user_input, config=config, provider=provider)

            # Handle thread switch from commands
            if result.metadata.get("switch_to_thread"):
                thread = result.metadata["switch_to_thread"]
                console.print(f"[dim]Switched to thread:[/dim] [cyan]{thread.title}[/cyan] ({thread.id})")
                if result.content:
                    console.print(Panel(result.content, title="[blue]System[/blue]", border_style="blue"))
                continue

            if result.status == "error":
                console.print(Panel(result.content, title="[red]Error[/red]", border_style="red"))
            elif result.status == "command":
                console.print(Panel(Markdown(result.content), title="[blue]System[/blue]", border_style="blue"))
            else:
                meta = f"{result.mode}"
                if result.metadata.get("duration_ms"):
                    meta += f" | {result.metadata['duration_ms']}ms"
                if result.metadata.get("validation_status"):
                    meta += f" | {result.metadata['validation_status']}"
                console.print(Panel(
                    Markdown(result.content),
                    title=f"[green]PromptFix[/green] — {meta}",
                    border_style="green",
                ))
            console.print()
            continue

        # Streaming chat path
        if use_streaming:
            from promptfix.chat_engine import process_message_stream

            # Show typing indicator
            console.print("[dim]PromptFix is thinking...[/dim]", end="\r")
            is_first_chunk = True
            full_content = ""

            try:
                for item in process_message_stream(thread, user_input, config=config, provider=provider):
                    if item["type"] == "chunk":
                        if is_first_chunk:
                            console.print(" " * 40, end="\r")
                            is_first_chunk = False
                        full_content += item["content"]
                        console.print(item["content"], end="")
                    elif item["type"] == "error":
                        console.print(" " * 40, end="\r")
                        console.print(Panel(item["content"], title="[red]Error[/red]", border_style="red"))
                        break
                    elif item["type"] == "result":
                        console.print()  # newline after streaming
                        meta = f"{item.get('mode', thread.current_mode)}"
                        md = item.get("metadata", {})
                        if md.get("duration_ms"):
                            meta += f" | {md['duration_ms']}ms"
                        if md.get("validation_status"):
                            meta += f" | {md['validation_status']}"
                        console.print(Panel(
                            Markdown(item["content"]),
                            title=f"[green]PromptFix[/green] — {meta}",
                            border_style="green",
                        ))
                        if md.get("thread_id"):
                            thread.id = md["thread_id"]
                        break
            except Exception as e:
                console.print(" " * 40, end="\r")
                console.print(Panel(f"Error: {e}", title="[red]Error[/red]", border_style="red"))

            console.print()
        else:
            # Non-streaming fallback
            console.print("[dim]PromptFix is thinking...[/dim]", end="\r")
            result = process_message(thread, user_input, config=config, provider=provider)
            console.print(" " * 40, end="\r")

            if result.status == "error":
                console.print(Panel(result.content, title="[red]Error[/red]", border_style="red"))
            else:
                meta = f"{result.mode}"
                if result.metadata.get("duration_ms"):
                    meta += f" | {result.metadata['duration_ms']}ms"
                if result.metadata.get("validation_status"):
                    meta += f" | {result.metadata['validation_status']}"
                console.print(Panel(
                    Markdown(result.content),
                    title=f"[green]PromptFix[/green] — {meta}",
                    border_style="green",
                ))
            console.print()


@app.command()
def setup():
    """Interactive setup wizard."""
    console.print("[bold]PromptFix Setup[/bold]\n")
    config = ensure_config()

    provider = typer.prompt("Provider", default=config.get("provider", "groq"),
                           type=typer.Choice(["groq", "openai_compatible", "ollama"]))
    config["provider"] = provider

    pcfg = get_provider_config(config, provider)
    if provider in ("groq", "openai_compatible"):
        api_key_env = pcfg.get("api_key_env", "GROQ_API_KEY")
        console.print(f"\nMake sure [cyan]{api_key_env}[/cyan] is set:")
        console.print(f'  setx {api_key_env} "your_key"')
        console.print("  Then open a new terminal.\n")
    elif provider == "ollama":
        model = typer.prompt("Ollama model", default=pcfg.get("model", "qwen2.5:7b"))
        config["providers"]["ollama"]["model"] = model

    default_mode = typer.prompt("Default mode", default="short",
                                type=typer.Choice(["fast", "short", "agent", "raw"]))
    config["default_mode"] = default_mode
    save_config(config)
    console.print(f"\n[green]Config saved to {get_config_path()}[/green]")
    console.print("\nNext steps:")
    console.print("  1. promptfix service     — start local service")
    console.print("  2. Install browser extension from extension/ folder")
    console.print("  3. promptfix tray        — optional global hotkeys")


@app.command(name="provider")
def provider_cmd(
    action: str = typer.Argument(..., help="list, use, doctor"),
    name: str = typer.Argument(None, help="Provider name"),
):
    """Manage providers."""
    config = load_config()

    if action == "list":
        current = config.get("provider", "groq")
        for p in config.get("providers", {}):
            marker = " *" if p == current else ""
            console.print(f"  {p}{marker}")

    elif action == "use":
        if not name:
            console.print("[red]Specify provider name[/red]")
            raise typer.Exit(1)
        if name not in config.get("providers", {}):
            console.print(f"[red]Unknown provider: {name}[/red]")
            raise typer.Exit(1)
        config["provider"] = name
        save_config(config)
        console.print(f"[green]Switched to {name}[/green]")

    elif action == "doctor":
        target = name or config.get("provider", "groq")
        console.print(f"Checking {target}...")
        try:
            provider = create_provider(config, target)
            ok, msg = provider.health_check()
            if ok:
                console.print(f"[green]✓ {msg}[/green]")
            else:
                console.print(f"[red]✗ {msg}[/red]")
        except RuntimeError as e:
            console.print(f"[red]✗ {e}[/red]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")


@app.command()
def benchmark(
    text: str = typer.Argument(..., help="Text to benchmark"),
    mode: str = typer.Option("short", "--mode", "-m"),
    runs: int = typer.Option(3, "--runs", "-n"),
):
    """Benchmark rewrite speed."""
    config = load_config()
    try:
        provider = create_provider(config)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    times = []
    for i in range(runs):
        start = time.time()
        result = rewrite(text=text, mode=mode, config=config, provider=provider)
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
        console.print(f"  Run {i+1}: {elapsed:.0f}ms ({result.validation_status})")

    avg = sum(times) / len(times)
    console.print(f"\n[bold]Average: {avg:.0f}ms[/bold] over {runs} runs")
    console.print(f"Provider: {config.get('provider')} | Mode: {mode}")


@app.command(name="debug-intent")
def debug_intent(text: str = typer.Argument(..., help="Text to parse")):
    """Show parsed intent for debugging."""
    from promptfix.intent import parse_intent
    intent = parse_intent(text)
    console.print_json(json.dumps({
        "original": intent.original_text,
        "normalized": intent.normalized_text,
        "task_type": intent.task_type,
        "domain": intent.domain,
        "keywords": intent.keywords,
        "constraints": intent.constraints,
        "allow_refactor": intent.allow_refactor,
        "needs_context": intent.needs_context,
    }, indent=2))


@app.command(name="debug-rewrite")
def debug_rewrite(
    text: str = typer.Argument(..., help="Text to rewrite"),
    mode: str = typer.Option("short", "--mode", "-m"),
):
    """Show full rewrite pipeline debug info."""
    config = load_config()
    try:
        result = rewrite(text=text, mode=mode, config=config)
        console.print(Panel(result.optimized, title="Output"))
        console.print(f"Mode: {result.mode} | Provider: {result.provider} | {result.duration_ms}ms | Status: {result.validation_status}")
        if result.intent:
            console.print(f"Intent: type={result.intent.task_type} domain={result.intent.domain} keywords={result.intent.keywords}")
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")


@app.command(name="debug-guard")
def debug_guard(text: str = typer.Argument(..., help="Output text to validate")):
    """Test the output guard on a string."""
    from promptfix.guard import clean_output, validate_output
    from promptfix.intent import parse_intent
    intent = parse_intent("test bugfix auth")
    cleaned = clean_output(text)
    result = validate_output(cleaned, intent)
    console.print(f"Valid: {result.valid}")
    if result.reasons:
        for r in result.reasons:
            console.print(f"  - {r}")
    console.print(f"Cleaned: {cleaned[:200]}")


if __name__ == "__main__":
    app()
