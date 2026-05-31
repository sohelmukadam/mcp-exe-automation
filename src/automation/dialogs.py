"""Dialog handling module - detect and interact with dialog boxes and popups."""

import logging
import time
from typing import Optional

import win32con
import win32gui
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from src.automation.windows import get_window

logger = logging.getLogger(__name__)


def handle_dialog(
    title: Optional[str] = None,
    button_text: Optional[str] = None,
    action: str = "accept",
    timeout: float = 5.0,
) -> dict:
    """Handle a dialog box/popup window.

    Args:
        title: Partial title of the dialog. If None, handles the foreground dialog.
        button_text: Specific button text to click (e.g., 'OK', 'Yes', 'Save').
        action: Action to take - 'accept' (Enter/OK), 'dismiss' (Escape/Cancel),
                'click_button' (use button_text).
        timeout: Max seconds to wait for the dialog.

    Returns:
        Dict with status and dialog info.
    """
    dialog = None

    if title:
        try:
            dialog = get_window(title, timeout=timeout)
        except ValueError:
            return {"status": "not_found", "message": f"Dialog '{title}' not found"}
    else:
        # Find the topmost dialog/modal window
        try:
            desktop = Desktop(backend="uia")
            for win in desktop.windows():
                try:
                    if win.is_visible():
                        ctrl_type = win.element_info.control_type
                        if ctrl_type in ("Window", "Dialog", "Pane"):
                            dialog = win
                            break
                except Exception:
                    pass
        except Exception:
            pass

    if dialog is None:
        return {"status": "not_found", "message": "No dialog found"}

    dialog_title = dialog.window_text() if hasattr(dialog, 'window_text') else str(title)

    if action == "click_button" and button_text:
        try:
            btn = dialog.child_window(title=button_text, control_type="Button")
            if btn.exists(timeout=2):
                btn.click_input()
                return {
                    "status": "success",
                    "dialog": dialog_title,
                    "button_clicked": button_text,
                }
        except Exception:
            pass

        # Try by automation_id
        try:
            btn = dialog.child_window(auto_id=button_text, control_type="Button")
            if btn.exists(timeout=1):
                btn.click_input()
                return {
                    "status": "success",
                    "dialog": dialog_title,
                    "button_clicked": button_text,
                }
        except Exception:
            pass

        return {"status": "error", "message": f"Button '{button_text}' not found in dialog"}

    elif action == "accept":
        # Try clicking OK/Yes button first, then send Enter
        for btn_name in ["OK", "Yes", "&OK", "&Yes", "Accept", "Continue"]:
            try:
                btn = dialog.child_window(title=btn_name, control_type="Button")
                if btn.exists(timeout=1):
                    btn.click_input()
                    return {"status": "success", "dialog": dialog_title, "action": "accepted", "button": btn_name}
            except Exception:
                pass

        # Fallback to Enter key
        try:
            dialog.set_focus()
        except Exception:
            pass
        send_keys("{ENTER}")
        return {"status": "success", "dialog": dialog_title, "action": "accepted", "method": "enter_key"}

    elif action == "dismiss":
        # Try clicking Cancel/No button first, then send Escape
        for btn_name in ["Cancel", "No", "&Cancel", "&No", "Close"]:
            try:
                btn = dialog.child_window(title=btn_name, control_type="Button")
                if btn.exists(timeout=1):
                    btn.click_input()
                    return {"status": "success", "dialog": dialog_title, "action": "dismissed", "button": btn_name}
            except Exception:
                pass

        # Fallback to Escape key
        try:
            dialog.set_focus()
        except Exception:
            pass
        send_keys("{ESC}")
        return {"status": "success", "dialog": dialog_title, "action": "dismissed", "method": "escape_key"}

    return {"status": "error", "message": f"Unknown action: {action}"}


def get_dialog_info(title: Optional[str] = None) -> dict:
    """Get information about an open dialog.

    Args:
        title: Partial title of the dialog. If None, inspects the topmost dialog.

    Returns:
        Dict with dialog title, text, and button info.
    """
    if title:
        try:
            dialog = get_window(title)
        except ValueError:
            return {"status": "not_found", "message": f"Dialog '{title}' not found"}
    else:
        dialog = None
        desktop = Desktop(backend="uia")
        for win in desktop.windows():
            try:
                if win.is_visible():
                    dialog = win
                    break
            except Exception:
                pass
        if dialog is None:
            return {"status": "not_found", "message": "No dialog found"}

    info = {
        "status": "success",
        "title": dialog.window_text(),
        "buttons": [],
        "text_content": [],
    }

    # Find all buttons
    try:
        for child in dialog.descendants(control_type="Button"):
            try:
                info["buttons"].append({
                    "name": child.window_text(),
                    "enabled": child.is_enabled(),
                })
            except Exception:
                pass
    except Exception:
        pass

    # Find text/static controls
    try:
        for child in dialog.descendants(control_type="Text"):
            try:
                text = child.window_text()
                if text.strip():
                    info["text_content"].append(text)
            except Exception:
                pass
    except Exception:
        pass

    return info


def wait_for_dialog(
    title: str,
    timeout: float = 30.0,
    action: Optional[str] = None,
    button_text: Optional[str] = None,
) -> dict:
    """Wait for a dialog to appear and optionally handle it.

    Args:
        title: Partial title of the expected dialog.
        timeout: Max seconds to wait.
        action: Optional action to take when found ('accept', 'dismiss', 'click_button').
        button_text: Button to click if action is 'click_button'.

    Returns:
        Dict with status.
    """
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            dialog = get_window(title, timeout=1.0)
            if dialog:
                if action:
                    return handle_dialog(title=title, button_text=button_text, action=action)
                return {
                    "status": "found",
                    "title": dialog.window_text(),
                }
        except ValueError:
            pass
        time.sleep(0.5)

    return {"status": "timeout", "message": f"Dialog '{title}' did not appear within {timeout}s"}
