"""Local HTTP service for the browser extension and chat API."""

from __future__ import annotations

import re
import time

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from promptfix.config import load_config
from promptfix.rewriter import create_provider, rewrite
from promptfix.chat_engine import process_message, process_message_stream, get_suggestions
from promptfix.chat_session import create_thread, load_thread, list_threads, delete_thread

app = Flask(__name__)

# Rate limiter — in-memory, keyed by remote IP.
# All limits are intentionally generous for a local-only service.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per minute"],
    storage_uri="memory://",
)

_provider = None
_config = None
_start_time = time.time()

# Maximum allowed input text length (characters)
MAX_TEXT_LENGTH = 32_000

# Allowed CORS origins: Chrome/Firefox extensions and localhost only
_ALLOWED_ORIGIN_PREFIXES = (
    "chrome-extension://",
    "moz-extension://",
    "http://127.0.0.1",
    "http://localhost",
)


def _is_allowed_origin(origin: str) -> bool:
    """Validate that *origin* is a true browser-extension or localhost origin.

    Uses strict hostname checking to prevent prefix-bypass attacks such as
    ``http://127.0.0.1.evil.com``.
    """
    if origin.startswith(("chrome-extension://", "moz-extension://")):
        return True
    from urllib.parse import urlparse
    parsed = urlparse(origin)
    hostname = parsed.hostname
    scheme = parsed.scheme
    return (
        scheme in ("http", "https")
        and hostname in ("localhost", "127.0.0.1")
    )

# UUID v4 pattern for thread IDs
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _get_config():
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _get_provider():
    global _provider
    if _provider is None:
        _provider = create_provider(_get_config())
    return _provider


def _check_auth():
    """Return a 401 Response if a token is configured and the request is unauthorised.
    Returns None when the request is allowed to proceed.
    """
    token = _get_config().get("service", {}).get("token", "")
    if token:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            return jsonify({"error": "Unauthorized"}), 401
    return None


@app.after_request
def add_cors(response):
    """Restrict CORS to localhost and browser-extension origins only."""
    origin = request.headers.get("Origin", "")
    if origin and _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, DELETE"
    return response


@app.route("/health", methods=["GET"])
def health():
    cfg = _get_config()
    uptime = int(time.time() - _start_time)
    return jsonify({
        "status": "ok",
        "version": "1.0.0",
        "provider": cfg.get("provider", "groq"),
        "model": cfg.get("providers", {}).get(cfg.get("provider", "groq"), {}).get("model", "?"),
        "uptime_s": uptime,
    })


@app.route("/config-safe", methods=["GET"])
def config_safe():
    cfg = _get_config()
    return jsonify({
        "provider": cfg.get("provider"),
        "default_mode": cfg.get("default_mode"),
        "model": cfg.get("providers", {}).get(cfg.get("provider", "groq"), {}).get("model"),
    })


@app.route("/optimize", methods=["POST", "OPTIONS"])
@limiter.limit("60 per minute", exempt_when=lambda: request.method == "OPTIONS")
def optimize():
    if request.method == "OPTIONS":
        return "", 204

    denied = _check_auth()
    if denied:
        return denied

    data = request.get_json(force=False, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    text = data.get("text", "").strip()
    mode = data.get("mode")
    include_diff = data.get("include_diff", False)

    if not text:
        return jsonify({"error": "No text provided"}), 400
    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"error": f"Text too long (max {MAX_TEXT_LENGTH} characters)"}), 413

    config = _get_config()
    try:
        provider = _get_provider()
        result = rewrite(text=text, mode=mode, config=config, provider=provider, source="api")
        response = result.to_dict()
        # Always include score_breakdown in API responses (already in to_dict if present)
        # Optionally include diff when requested
        if include_diff:
            from promptfix.diff import compute_diff
            diff_result = compute_diff(text, result.optimized)
            response["diff"] = diff_result.to_dict()
        return jsonify(response)
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


@app.route("/history", methods=["GET"])
@limiter.limit("30 per minute")
def history():
    """Return recent optimization history."""
    denied = _check_auth()
    if denied:
        return denied
    from promptfix.history import get_history
    limit = request.args.get("limit", 20, type=int)
    entries = get_history(min(limit, 100))
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/history", methods=["DELETE"])
@limiter.limit("10 per minute")
def clear_history_endpoint():
    denied = _check_auth()
    if denied:
        return denied
    from promptfix.history import clear_history
    count = clear_history()
    return jsonify({"cleared": count})


# --- Chat endpoints ---

@app.route("/chat", methods=["POST", "OPTIONS"])
@limiter.limit("60 per minute", exempt_when=lambda: request.method == "OPTIONS")
def chat_endpoint():
    """POST /chat — Process one message in a thread."""
    if request.method == "OPTIONS":
        return "", 204

    denied = _check_auth()
    if denied:
        return denied

    data = request.get_json(force=False, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    text = data.get("text", "").strip()
    thread_id = data.get("thread_id")
    mode = data.get("mode")

    if not text:
        return jsonify({"error": "No text provided"}), 400
    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"error": f"Text too long (max {MAX_TEXT_LENGTH} characters)"}), 413
    if thread_id is not None and not _UUID_RE.match(str(thread_id)):
        return jsonify({"error": "Invalid thread_id"}), 400

    config = _get_config()

    try:
        provider = _get_provider()
    except Exception as e:
        return jsonify({"error": "Provider unavailable"}), 500

    # Load or create thread
    thread = load_thread(thread_id) if thread_id else None
    if not thread:
        thread = create_thread(
            mode=mode or config.get("chat", {}).get("default_mode", "short"),
            provider=config.get("provider", "groq"),
        )

    # Override mode if provided
    if mode and mode in {"fast", "short", "agent", "raw", "explain"}:
        thread.current_mode = mode

    result = process_message(thread, text, config=config, provider=provider)

    response = {
        "content": result.content,
        "mode": result.mode,
        "status": result.status,
        "thread_id": thread.id,
        "metadata": result.metadata,
    }
    return jsonify(response)


@app.route("/chat/stream", methods=["POST", "OPTIONS"])
@limiter.limit("60 per minute", exempt_when=lambda: request.method == "OPTIONS")
def chat_stream_endpoint():
    """POST /chat/stream — Stream response using SSE."""
    if request.method == "OPTIONS":
        return "", 204

    denied = _check_auth()
    if denied:
        return denied

    data = request.get_json(force=False, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    text = data.get("text", "").strip()
    thread_id = data.get("thread_id")
    mode = data.get("mode")

    if not text:
        return jsonify({"error": "No text provided"}), 400
    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"error": f"Text too long (max {MAX_TEXT_LENGTH} characters)"}), 413
    if thread_id is not None and not _UUID_RE.match(str(thread_id)):
        return jsonify({"error": "Invalid thread_id"}), 400

    config = _get_config()

    try:
        provider = _get_provider()
    except Exception as e:
        return jsonify({"error": "Provider unavailable"}), 500

    # Load or create thread
    thread = load_thread(thread_id) if thread_id else None
    if not thread:
        thread = create_thread(
            mode=mode or config.get("chat", {}).get("default_mode", "short"),
            provider=config.get("provider", "groq"),
        )

    if mode and mode in {"fast", "short", "agent", "raw", "explain"}:
        thread.current_mode = mode

    def generate():
        for item in process_message_stream(thread, text, config=config, provider=provider):
            import json
            yield f"data: {json.dumps(item)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/suggestions", methods=["GET", "OPTIONS"])
def suggestions_endpoint():
    """GET /suggestions?text=...&thread_id=... — Return autocomplete suggestions."""
    if request.method == "OPTIONS":
        return "", 204

    denied = _check_auth()
    if denied:
        return denied

    text = request.args.get("text", "")
    thread_id = request.args.get("thread_id")
    if thread_id is not None and not _UUID_RE.match(str(thread_id)):
        return jsonify({"error": "Invalid thread_id"}), 400

    thread = load_thread(thread_id) if thread_id else None
    if not thread:
        thread = create_thread()

    suggestions = get_suggestions(text, thread)
    return jsonify({"suggestions": suggestions})


@app.route("/threads", methods=["GET"])
def list_threads_endpoint():
    """GET /threads — List all saved threads."""
    denied = _check_auth()
    if denied:
        return denied
    threads = list_threads()
    return jsonify({
        "threads": [
            {
                "id": t.id,
                "title": t.title,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "message_count": len(t.messages),
                "current_mode": t.current_mode,
            }
            for t in threads[:50]
        ],
    })


@app.route("/threads/<thread_id>", methods=["GET"])
def get_thread_endpoint(thread_id: str):
    """GET /threads/<id> — Get thread details and messages."""
    denied = _check_auth()
    if denied:
        return denied
    if not _UUID_RE.match(thread_id):
        return jsonify({"error": "Invalid thread_id"}), 400
    thread = load_thread(thread_id)
    if not thread:
        return jsonify({"error": "Thread not found"}), 404
    return jsonify(thread.to_dict())


@app.route("/threads/<thread_id>", methods=["DELETE"])
def delete_thread_endpoint(thread_id: str):
    """DELETE /threads/<id> — Delete a thread."""
    denied = _check_auth()
    if denied:
        return denied
    if not _UUID_RE.match(thread_id):
        return jsonify({"error": "Invalid thread_id"}), 400
    if delete_thread(thread_id):
        return jsonify({"deleted": True})
    return jsonify({"error": "Thread not found"}), 404


@app.route("/config/reload", methods=["POST"])
def reload_config_endpoint():
    """POST /config/reload — Reload config.yaml and reset provider without restarting."""
    denied = _check_auth()
    if denied:
        return denied
    global _config, _provider
    _config = None
    _provider = None
    _config = load_config()
    return jsonify({"status": "ok", "provider": _config.get("provider")})


def run_service(host: str = "127.0.0.1", port: int = 52849):
    global _config, _provider, _start_time
    _start_time = time.time()
    _config = load_config()

    if host not in ("127.0.0.1", "localhost"):
        print(f"\n  [WARNING] Binding to {host} exposes the service on your network.")
        print("  For local-only use, keep the default host: 127.0.0.1\n")

    provider_name = _config.get("provider", "groq")
    model = _config.get("providers", {}).get(provider_name, {}).get("model", "?")

    try:
        _provider = create_provider(_config)
        print(f"  Provider: {provider_name} ({model}) ✓")
    except RuntimeError as e:
        print(f"  Provider: {provider_name} ✗ ({e})")
        print("  Service will start but requests may fail.")

    print(f"\n  PromptFix service → http://{host}:{port}")
    print(f"  POST /optimize   — rewrite a prompt")
    print(f"  POST /chat       — chat with context")
    print(f"  POST /chat/stream — chat with streaming")
    print(f"  GET  /suggestions — autocomplete suggestions")
    print(f"  GET  /threads    — list chat threads")
    print(f"  GET  /health     — check status")
    print(f"  GET  /history    — recent optimizations\n")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_service()
