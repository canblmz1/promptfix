// PromptFix content script
// Handles: selection reading, text replacement (textarea/input/contentEditable),
// clipboard fallback, toast notifications.

(() => {
  "use strict";

  let toast = null;
  // Stash the selection info at right-click time so it survives async round-trips
  let savedSelection = null;

  // Save selection on every mousedown (right-click) so we have it when the
  // async optimize call returns.
  document.addEventListener("mousedown", (e) => {
    if (e.button === 2) {
      // right-click
      savedSelection = captureSelection();
    }
  });

  // --- Message listener ---

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.action === "ping") {
      sendResponse({ ok: true });
      return;
    }
    if (msg.action === "showLoading") {
      showToast("⏳ Optimizing prompt...", "loading");
    } else if (msg.action === "replaceSelection") {
      const ok = replaceSelectedText(msg.text);
      if (ok) {
        showToast("✓ Prompt optimized!", "success");
      } else {
        // Clipboard fallback
        copyToClipboard(msg.text);
        showToast("✓ Optimized prompt copied. Paste manually.", "success");
      }
    } else if (msg.action === "showError") {
      showToast(msg.error, "error");
    }
  });

  // --- Capture selection context ---

  function captureSelection() {
    const el = document.activeElement;
    if (!el) return null;

    // textarea or text input
    if (isTextInput(el)) {
      return {
        type: "input",
        element: el,
        start: el.selectionStart,
        end: el.selectionEnd,
        value: el.value,
      };
    }

    // contentEditable
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
      const range = sel.getRangeAt(0);
      const editable = findEditableAncestor(range.commonAncestorContainer);
      if (editable) {
        return {
          type: "contenteditable",
          element: editable,
          range: range.cloneRange(),
        };
      }
    }

    return null;
  }

  // --- Replace selected text ---

  function replaceSelectedText(newText) {
    const ctx = savedSelection || captureSelection();
    if (!ctx) return false;

    if (ctx.type === "input") {
      return replaceInInput(ctx, newText);
    }
    if (ctx.type === "contenteditable") {
      return replaceInContentEditable(ctx, newText);
    }
    return false;
  }

  function replaceInInput(ctx, newText) {
    const el = ctx.element;
    if (!el || !document.body.contains(el)) return false;

    // Prefer execCommand for proper undo support and framework reactivity
    el.focus();
    el.setSelectionRange(ctx.start, ctx.end);

    if (document.execCommand("insertText", false, newText)) {
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }

    // Manual fallback
    el.value =
      el.value.substring(0, ctx.start) + newText + el.value.substring(ctx.end);
    el.selectionStart = ctx.start;
    el.selectionEnd = ctx.start + newText.length;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function replaceInContentEditable(ctx, newText) {
    const el = ctx.element;
    if (!el || !document.body.contains(el)) return false;

    el.focus();

    // Restore the saved range
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(ctx.range);

    // Prefer execCommand for undo support and React/framework reactivity
    if (document.execCommand("insertText", false, newText)) {
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    }

    // Manual fallback
    const range = ctx.range;
    range.deleteContents();
    range.insertNode(document.createTextNode(newText));
    range.collapse(false);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  }

  // --- Utilities ---

  function isTextInput(el) {
    if (!el || !el.tagName) return false;
    if (el.tagName === "TEXTAREA") return true;
    if (el.tagName === "INPUT") {
      const type = (el.type || "text").toLowerCase();
      return ["text", "search", "url", "tel", "password"].includes(type);
    }
    return false;
  }

  function findEditableAncestor(node) {
    let cur = node;
    while (cur) {
      if (cur.nodeType === 1 && cur.isContentEditable) return cur;
      cur = cur.parentElement || cur.parentNode;
    }
    return null;
  }

  function copyToClipboard(text) {
    // Modern API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(() => {
        fallbackCopy(text);
      });
      return;
    }
    fallbackCopy(text);
  }

  function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText =
      "position:fixed;top:-9999px;left:-9999px;opacity:0;pointer-events:none";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
    } catch {
      /* ignore */
    }
    ta.remove();
  }

  // --- Toast ---

  function showToast(message, type) {
    if (toast) {
      toast.remove();
      toast = null;
    }

    toast = document.createElement("div");
    toast.textContent = message;
    Object.assign(toast.style, {
      position: "fixed",
      bottom: "20px",
      right: "20px",
      padding: "12px 20px",
      borderRadius: "8px",
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      fontSize: "14px",
      fontWeight: "500",
      lineHeight: "1.4",
      maxWidth: "420px",
      zIndex: "2147483647",
      color: "#fff",
      boxShadow: "0 4px 16px rgba(0,0,0,0.35)",
      transition: "opacity 0.3s ease",
      opacity: "0",
    });

    const colors = {
      loading: "#333",
      success: "#1a7f37",
      error: "#cf222e",
    };
    toast.style.backgroundColor = colors[type] || "#333";

    document.body.appendChild(toast);
    // Force reflow then animate in
    requestAnimationFrame(() => {
      toast.style.opacity = "1";
    });

    if (type !== "loading") {
      setTimeout(() => {
        if (toast) {
          toast.style.opacity = "0";
          setTimeout(() => {
            if (toast) {
              toast.remove();
              toast = null;
            }
          }, 300);
        }
      }, 3500);
    }
  }
})();
