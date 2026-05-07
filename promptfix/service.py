"""Local HTTP service for the browser extension and chat API."""

from __future__ import annotations

import time

from flask import Flask, Response, jsonify, request, stream_with_context

from promptfix.config import load_config
from promptfix.rewriter import create_provider, rewrite
from promptfix.chat_engine import process_message, process_message_stream, get_suggestions
from promptfix.chat_session import create_thread, load_thread, list_threads, delete_thread

app = Flask(__name__)

_provider = None
_config = None
_start_time = time.time()


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


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
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
def optimize():
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    mode = data.get("mode")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    config = _get_config()
    token = config.get("service", {}).get("token", "")
    if token:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            return jsonify({"error": "Unauthorized"}), 401

    try:
        provider = _get_provider()
        result = rewrite(text=text, mode=mode, config=config, provider=provider, source="api")
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/history", methods=["GET"])
def history():
    """Return recent optimization history."""
    from promptfix.history import get_history
    limit = request.args.get("limit", 20, type=int)
    entries = get_history(min(limit, 100))
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/history", methods=["DELETE"])
def clear_history_endpoint():
    from promptfix.history import clear_history
    count = clear_history()
    return jsonify({"cleared": count})


# --- Chat endpoints ---

@app.route("/chat", methods=["POST", "OPTIONS"])
def chat_endpoint():
    """POST /chat — Process one message in a thread."""
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    thread_id = data.get("thread_id")
    mode = data.get("mode")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    config = _get_config()

    # Auth check
    token = config.get("service", {}).get("token", "")
    if token:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            return jsonify({"error": "Unauthorized"}), 401

    try:
        provider = _get_provider()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
def chat_stream_endpoint():
    """POST /chat/stream — Stream response using SSE."""
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    thread_id = data.get("thread_id")
    mode = data.get("mode")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    config = _get_config()

    # Auth check
    token = config.get("service", {}).get("token", "")
    if token:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            return jsonify({"error": "Unauthorized"}), 401

    try:
        provider = _get_provider()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

    text = request.args.get("text", "")
    thread_id = request.args.get("thread_id")

    thread = load_thread(thread_id) if thread_id else None
    if not thread:
        thread = create_thread()

    suggestions = get_suggestions(text, thread)
    return jsonify({"suggestions": suggestions})


@app.route("/threads", methods=["GET"])
def list_threads_endpoint():
    """GET /threads — List all saved threads."""
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
    thread = load_thread(thread_id)
    if not thread:
        return jsonify({"error": "Thread not found"}), 404
    return jsonify(thread.to_dict())


@app.route("/threads/<thread_id>", methods=["DELETE"])
def delete_thread_endpoint(thread_id: str):
    """DELETE /threads/<id> — Delete a thread."""
    if delete_thread(thread_id):
        return jsonify({"deleted": True})
    return jsonify({"error": "Thread not found"}), 404


def run_service(host: str = "127.0.0.1", port: int = 52849):
    global _config, _provider, _start_time
    _start_time = time.time()
    _config = load_config()

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
