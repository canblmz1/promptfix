"""Tests for chat engine and session management."""

import json
from unittest.mock import MagicMock

import pytest

from promptfix.chat_session import (
    ChatThread,
    ChatMessage,
    create_thread,
    load_thread,
    save_thread,
    delete_thread,
    list_threads,
    _thread_path,
)
from promptfix.chat_engine import process_message, process_message_stream, VALID_MODES, _handle_command, get_suggestions
from promptfix.snippets import add_snippet, get_snippet, delete_snippet, list_snippets, expand_snippets


class TestChatSession:
    def test_create_thread(self):
        thread = create_thread(mode="short", provider="groq", title="Test")
        assert thread.id
        assert thread.title == "Test"
        assert thread.current_mode == "short"
        assert thread.provider == "groq"
        assert len(thread.messages) == 0

    def test_save_and_load_thread(self):
        thread = create_thread(mode="agent", title="SaveTest")
        thread.add_message("user", "hello")
        thread.add_message("assistant", "hi there")
        save_thread(thread)

        loaded = load_thread(thread.id)
        assert loaded is not None
        assert loaded.id == thread.id
        assert loaded.title == "SaveTest"
        assert len(loaded.messages) == 2
        assert loaded.messages[0].role == "user"
        assert loaded.messages[1].role == "assistant"

        # Cleanup
        delete_thread(thread.id)

    def test_delete_thread(self):
        thread = create_thread()
        save_thread(thread)
        assert _thread_path(thread.id).exists()
        assert delete_thread(thread.id)
        assert not _thread_path(thread.id).exists()
        assert not delete_thread("nonexistent")

    def test_list_threads(self):
        t1 = create_thread(title="Alpha")
        t2 = create_thread(title="Beta")
        save_thread(t1)
        save_thread(t2)

        threads = list_threads()
        ids = [t.id for t in threads]
        assert t1.id in ids
        assert t2.id in ids

        delete_thread(t1.id)
        delete_thread(t2.id)

    def test_auto_title(self):
        thread = create_thread()
        thread.add_message("user", "fix the login bug please")
        assert "fix the login bug" in thread.title.lower()

    def test_trim_messages(self):
        thread = create_thread()
        for i in range(110):
            thread.add_message("user", f"msg {i}")
        assert len(thread.messages) == 100

    def test_get_context_messages(self):
        thread = create_thread()
        thread.add_message("user", "first")
        thread.add_message("assistant", "second")
        thread.add_message("user", "third")

        ctx = thread.get_context_messages(limit=2)
        assert len(ctx) == 2
        assert ctx[0]["content"] == "second"
        assert ctx[1]["content"] == "third"

    def test_message_to_dict(self):
        msg = ChatMessage(role="user", content="test", mode="short")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "test"
        assert d["mode"] == "short"
        assert "timestamp" in d

    def test_thread_to_dict(self):
        thread = create_thread(mode="fast", title="DictTest")
        thread.add_message("user", "hello")
        d = thread.to_dict()
        assert d["id"] == thread.id
        assert d["title"] == "DictTest"
        assert d["current_mode"] == "fast"
        assert len(d["messages"]) == 1


class TestChatEngineCommands:
    def test_mode_command(self):
        thread = create_thread(mode="short")
        result = _handle_command(thread, "/mode agent", {})
        assert result.status == "command"
        assert "agent" in result.content.lower()
        assert thread.current_mode == "agent"

    def test_mode_command_invalid(self):
        thread = create_thread(mode="short")
        result = _handle_command(thread, "/mode invalid", {})
        assert result.status == "error"
        assert thread.current_mode == "short"

    def test_clear_command(self):
        thread = create_thread()
        thread.add_message("user", "hello")
        result = _handle_command(thread, "/clear", {})
        assert result.status == "command"
        assert len(thread.messages) == 0

    def test_history_command(self):
        thread = create_thread()
        thread.add_message("user", "hello world")
        thread.add_message("assistant", "hi there")
        result = _handle_command(thread, "/history", {})
        assert result.status == "command"
        assert "hello world" in result.content or "2 messages" in result.content

    def test_help_command(self):
        thread = create_thread()
        result = _handle_command(thread, "/help", {})
        assert result.status == "command"
        assert "/mode" in result.content
        assert "/snippet" in result.content

    def test_unknown_command(self):
        thread = create_thread()
        result = _handle_command(thread, "/foobar", {})
        assert result.status == "error"
        assert "unknown command" in result.content.lower()

    def test_new_command(self):
        thread = create_thread()
        result = _handle_command(thread, "/new My Thread", {"provider": "groq"})
        assert result.status == "command"
        assert result.metadata.get("switch_to_thread") is not None
        assert result.metadata["switch_to_thread"].title == "My Thread"


class TestChatEngineMessages:
    def test_process_empty_message(self):
        thread = create_thread()
        result = process_message(thread, "   ")
        assert result.status == "error"

    def test_process_chat_message(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "Investigate and fix the login bug with minimal changes."

        thread = create_thread(mode="short")
        result = process_message(
            thread, "login bug bozuldu", config={"provider": "groq", "validation": {"enabled": False}}, provider=mock_provider
        )

        assert result.status == "ok"
        assert result.content
        assert len(thread.messages) == 2  # user + assistant
        assert thread.messages[0].role == "user"
        assert thread.messages[1].role == "assistant"

    def test_process_with_context(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "Follow-up answer."

        thread = create_thread(mode="short")
        thread.add_message("user", "previous question")
        thread.add_message("assistant", "previous answer")

        result = process_message(
            thread, "follow up", config={"provider": "groq", "validation": {"enabled": False}}, provider=mock_provider
        )

        assert result.status == "ok"
        # Provider should have received context messages
        call_args = mock_provider.complete.call_args
        messages = call_args[0][0]
        assert any(m["role"] == "system" for m in messages)
        assert any("previous question" in m.get("content", "") for m in messages)

    def test_valid_modes_set(self):
        assert "fast" in VALID_MODES
        assert "short" in VALID_MODES
        assert "agent" in VALID_MODES
        assert "raw" in VALID_MODES
        assert "explain" in VALID_MODES


class TestChatEngineStreaming:
    def test_process_message_stream(self):
        mock_provider = MagicMock()
        mock_provider.stream_complete.return_value = iter(["Hello ", "world", "!"])

        thread = create_thread(mode="short")
        chunks = []
        for item in process_message_stream(
            thread, "test message", config={"provider": "groq", "validation": {"enabled": False}}, provider=mock_provider
        ):
            chunks.append(item)

        # Should get chunks + result
        chunk_items = [c for c in chunks if c["type"] == "chunk"]
        result_items = [c for c in chunks if c["type"] == "result"]

        assert len(chunk_items) == 3
        assert len(result_items) == 1
        assert chunk_items[0]["content"] == "Hello "
        assert chunk_items[1]["content"] == "world"
        assert chunk_items[2]["content"] == "!"
        assert result_items[0]["status"] == "ok"

    def test_process_message_stream_empty(self):
        thread = create_thread()
        chunks = list(process_message_stream(thread, "   "))
        assert len(chunks) == 1
        assert chunks[0]["type"] == "error"

    def test_process_message_stream_command(self):
        thread = create_thread()
        chunks = list(process_message_stream(thread, "/help"))
        assert len(chunks) == 1
        assert chunks[0]["type"] == "result"
        assert chunks[0]["status"] == "command"


class TestSnippets:
    def test_add_and_get_snippet(self):
        add_snippet("reactbug", "React component bug, minimal changes")
        content = get_snippet("reactbug")
        assert content == "React component bug, minimal changes"
        delete_snippet("reactbug")

    def test_list_snippets(self):
        add_snippet("alpha", "first snippet content")
        add_snippet("beta", "second snippet content")
        snippets = list_snippets()
        names = [s[0] for s in snippets]
        assert "alpha" in names
        assert "beta" in names
        delete_snippet("alpha")
        delete_snippet("beta")

    def test_delete_snippet(self):
        add_snippet("temp", "temporary")
        assert get_snippet("temp") == "temporary"
        assert delete_snippet("temp")
        assert get_snippet("temp") is None
        assert not delete_snippet("nonexistent")

    def test_expand_snippets(self):
        add_snippet("reactbug", "React component bug, minimal changes")
        result = expand_snippets("Fix :reactbug: in login page")
        assert "React component bug, minimal changes" in result
        assert ":reactbug:" not in result
        delete_snippet("reactbug")

    def test_snippet_command_add(self):
        thread = create_thread()
        result = _handle_command(thread, "/snippet add testbug test content here", {})
        assert result.status == "command"
        assert "testbug" in result.content
        assert get_snippet("testbug") == "test content here"
        delete_snippet("testbug")

    def test_snippet_command_list(self):
        add_snippet("s1", "content one")
        thread = create_thread()
        result = _handle_command(thread, "/snippet list", {})
        assert result.status == "command"
        assert "s1" in result.content
        delete_snippet("s1")

    def test_snippet_command_use(self):
        add_snippet("mybug", "bug description")
        thread = create_thread()
        result = _handle_command(thread, "/snippet use mybug", {})
        assert result.status == "command"
        assert "bug description" in result.content
        delete_snippet("mybug")

    def test_snippet_command_delete(self):
        add_snippet("deleteme", "to be deleted")
        thread = create_thread()
        result = _handle_command(thread, "/snippet delete deleteme", {})
        assert result.status == "command"
        assert get_snippet("deleteme") is None


class TestSuggestions:
    def test_suggestions_slash_commands(self):
        thread = create_thread()
        suggestions = get_suggestions("/mode", thread)
        assert any(s["type"] == "command" for s in suggestions)

    def test_suggestions_snippets(self):
        add_snippet("reactbug", "React bug fix")
        thread = create_thread()
        suggestions = get_suggestions(":react", thread)
        assert any(s["type"] == "snippet" for s in suggestions)
        delete_snippet("reactbug")

    def test_suggestions_history(self):
        thread = create_thread()
        thread.add_message("user", "fix login bug")
        suggestions = get_suggestions("fix", thread)
        assert any(s["type"] == "history" for s in suggestions)
