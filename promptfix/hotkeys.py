"""Global hotkey support and system tray (optional Windows feature).

Flow per hotkey press:
1. Backup whatever is currently on the clipboard
2. Send Ctrl+C to copy the selected text
3. Read clipboard = selected text
4. Call PromptFix core rewrite()
5. Put optimized text on the clipboard
6. Send Ctrl+V to paste it
7. If paste fails, keep optimized text on clipboard (user pastes manually)
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time

# ---------------------------------------------------------------------------
# Win32 clipboard — only initialised on Windows
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes.wintypes as _wt

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    _user32.OpenClipboard.argtypes = [_wt.HWND]
    _user32.OpenClipboard.restype = _wt.BOOL
    _user32.CloseClipboard.argtypes = []
    _user32.CloseClipboard.restype = _wt.BOOL
    _user32.EmptyClipboard.argtypes = []
    _user32.EmptyClipboard.restype = _wt.BOOL
    _user32.GetClipboardData.argtypes = [_wt.UINT]
    _user32.GetClipboardData.restype = ctypes.c_void_p
    _user32.SetClipboardData.argtypes = [_wt.UINT, ctypes.c_void_p]
    _user32.SetClipboardData.restype = ctypes.c_void_p

    _kernel32.GlobalAlloc.argtypes = [_wt.UINT, ctypes.c_size_t]
    _kernel32.GlobalAlloc.restype = ctypes.c_void_p
    _kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalLock.restype = ctypes.c_void_p
    _kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalUnlock.restype = _wt.BOOL
    _kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalSize.restype = ctypes.c_size_t

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    def _clipboard_get() -> str:
        """Read current clipboard text."""
        if not _user32.OpenClipboard(None):
            return ""
        try:
            handle = _user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = _kernel32.GlobalLock(handle)
            if not ptr:
                return ""
            try:
                size = _kernel32.GlobalSize(handle)
                if size == 0:
                    return ""
                raw = ctypes.string_at(ptr, size)
                return raw.decode("utf-16-le", errors="replace").rstrip("\x00")
            finally:
                _kernel32.GlobalUnlock(handle)
        finally:
            _user32.CloseClipboard()

    def _clipboard_set(text: str) -> bool:
        """Set clipboard text."""
        if not _user32.OpenClipboard(None):
            return False
        try:
            _user32.EmptyClipboard()
            data = text.encode("utf-16-le") + b"\x00\x00"
            handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not handle:
                return False
            ptr = _kernel32.GlobalLock(handle)
            if not ptr:
                return False
            ctypes.memmove(ptr, data, len(data))
            _kernel32.GlobalUnlock(handle)
            _user32.SetClipboardData(CF_UNICODETEXT, handle)
            return True
        finally:
            _user32.CloseClipboard()

else:
    def _clipboard_get() -> str:
        """Read current clipboard text. Returns empty string on non-Windows."""
        return ""

    def _clipboard_set(text: str) -> bool:
        """Set clipboard text. Returns False on non-Windows."""
        return False


# ---------------------------------------------------------------------------
# Windows toast notification (native, no deps)
# ---------------------------------------------------------------------------

def _show_balloon(title: str, msg: str):
    """Best-effort balloon tip via plyer or fallback print."""
    try:
        from plyer import notification
        notification.notify(title=title, message=msg, timeout=3, app_name="PromptFix")
    except Exception:
        print(f"[PromptFix] {title}: {msg}")


# ---------------------------------------------------------------------------
# Tray + hotkey runner
# ---------------------------------------------------------------------------

# Valid modes the rewriter accepts
_VALID_MODES = {"fast", "short", "agent", "raw", "explain"}


def run_tray():
    if sys.platform != "win32":
        print("The tray + hotkey feature is currently Windows-only.")
        print("On Linux/macOS, use `promptfix service` and the browser extension instead.")
        sys.exit(1)

    try:
        import keyboard
    except ImportError:
        print("Install tray dependencies: pip install promptfix[tray]")
        sys.exit(1)

    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("Install tray dependencies: pip install promptfix[tray]")
        sys.exit(1)

    from promptfix.config import load_config
    from promptfix.rewriter import create_provider, rewrite

    config = load_config()
    hotkeys_cfg = config.get("hotkeys", {})

    try:
        provider = create_provider(config)
    except RuntimeError as e:
        print(f"Provider error: {e}")
        sys.exit(1)

    def _optimize(mode: str):
        """Full hotkey flow with clipboard backup/restore."""
        # Map legacy / unknown modes to valid ones
        if mode not in _VALID_MODES:
            mode = "short"

        try:
            # 1. Backup clipboard
            original_clipboard = _clipboard_get()

            # 2. Copy selected text
            keyboard.send("ctrl+c")
            time.sleep(0.15)

            # 3. Read selected text
            selected = _clipboard_get()
            if not selected or not selected.strip():
                # Nothing selected — restore and bail
                if original_clipboard:
                    _clipboard_set(original_clipboard)
                return

            # Avoid re-optimizing what we just copied if it's the same
            selected = selected.strip()

            # 4. Rewrite
            result = rewrite(text=selected, mode=mode, config=config, provider=provider, source="tray")
            optimized = result.optimized

            # 5. Put optimized on clipboard
            _clipboard_set(optimized)
            time.sleep(0.05)

            # 6. Paste
            keyboard.send("ctrl+v")
            time.sleep(0.15)

            _show_balloon(
                "PromptFix",
                f"✓ {mode} | {result.duration_ms}ms | {result.validation_status}"
            )

        except Exception as e:
            _show_balloon("PromptFix Error", str(e)[:120])
            # Try to restore clipboard on error
            try:
                if original_clipboard:
                    _clipboard_set(original_clipboard)
            except Exception:
                pass

    # Register hotkeys — only valid modes + map explain/fast to short
    registered = {}
    for mode_name, hotkey in hotkeys_cfg.items():
        effective_mode = mode_name if mode_name in _VALID_MODES else "short"
        try:
            keyboard.add_hotkey(
                hotkey,
                lambda m=effective_mode: threading.Thread(
                    target=_optimize, args=(m,), daemon=True
                ).start(),
            )
            registered[mode_name] = hotkey
        except Exception as e:
            print(f"  Warning: Could not register {hotkey} for {mode_name}: {e}")

    # --- System tray ---

    def _create_icon():
        img = Image.new("RGB", (64, 64), color=(30, 30, 30))
        d = ImageDraw.Draw(img)
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("arial.ttf", 24)
            d.text((12, 14), "PF", fill=(74, 222, 128), font=font)
        except Exception:
            d.text((16, 16), "PF", fill=(74, 222, 128))
        return img

    def on_quit(icon, item):
        icon.stop()
        keyboard.unhook_all()

    menu_items = [
        pystray.MenuItem("PromptFix Active", lambda: None, enabled=False),
    ]
    for m, hk in registered.items():
        label = m if m in _VALID_MODES else f"{m} → short"
        menu_items.append(
            pystray.MenuItem(f"  {label}: {hk}", lambda: None, enabled=False)
        )
    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem("Quit", on_quit))

    icon = pystray.Icon("promptfix", _create_icon(), "PromptFix", pystray.Menu(*menu_items))
    print("PromptFix tray active.")
    for m, hk in registered.items():
        label = m if m in _VALID_MODES else f"{m} → short"
        print(f"  {label}: {hk}")
    print("Minimize this window. Right-click the tray icon to quit.")
    icon.run()
