"""Clipboard interaction module.

Thread-safe clipboard operations with retry logic for robustness
in multi-threaded and high-DPI environments.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def get_clipboard_text() -> dict:
    """Get the current text content of the clipboard (thread-safe).

    Returns:
        Dict with clipboard text content.
    """
    from src.automation.utils import safe_clipboard_get

    try:
        text = safe_clipboard_get()
        if text:
            return {"status": "success", "text": text}
        return {"status": "success", "text": "", "message": "No text in clipboard"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_clipboard_text(text: str) -> dict:
    """Set text content to the clipboard (thread-safe).

    Args:
        text: Text to place on the clipboard.

    Returns:
        Dict with status.
    """
    from src.automation.utils import safe_clipboard_set

    try:
        success = safe_clipboard_set(text)
        if success:
            return {"status": "success", "text_length": len(text)}
        return {"status": "error", "message": "Failed to set clipboard after retries"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def clear_clipboard() -> dict:
    """Clear the clipboard contents (thread-safe).

    Returns:
        Dict with status.
    """
    from src.automation.utils import safe_clipboard_clear

    try:
        success = safe_clipboard_clear()
        if success:
            return {"status": "success", "action": "cleared"}
        return {"status": "error", "message": "Failed to clear clipboard"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def paste_from_clipboard(window_title: Optional[str] = None) -> dict:
    """Paste clipboard content into the focused window (Ctrl+V).

    Args:
        window_title: Optional window to focus before pasting.

    Returns:
        Dict with status.
    """
    from pywinauto.keyboard import send_keys
    from src.automation.windows import get_window

    if window_title:
        window = get_window(window_title)
        window.set_focus()
        time.sleep(0.15)

    send_keys("^v", pause=0.05)
    return {"status": "success", "action": "pasted"}


def copy_to_clipboard(window_title: Optional[str] = None) -> dict:
    """Copy selected content to clipboard (Ctrl+C).

    Args:
        window_title: Optional window to focus before copying.

    Returns:
        Dict with status and clipboard text.
    """
    from pywinauto.keyboard import send_keys
    from src.automation.windows import get_window

    if window_title:
        window = get_window(window_title)
        window.set_focus()
        time.sleep(0.15)

    send_keys("^c", pause=0.05)
    time.sleep(0.2)  # Wait for clipboard to be populated

    return get_clipboard_text()
