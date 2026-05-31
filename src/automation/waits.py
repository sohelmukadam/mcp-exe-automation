"""Wait conditions module - wait for UI states before proceeding."""

import logging
import time
from typing import Optional

from pywinauto import Desktop

from src.automation.windows import get_window

logger = logging.getLogger(__name__)


def wait_for_control(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    timeout: float = 30.0,
    state: str = "exists",
) -> dict:
    """Wait for a control to reach a specific state.

    Args:
        window_title: Partial title of the parent window.
        control_identifier: Identifier of the control to wait for.
        control_type: Optional control type filter.
        timeout: Max seconds to wait.
        state: State to wait for - 'exists', 'visible', 'enabled', 'ready'.

    Returns:
        Dict with status.
    """
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            window = get_window(window_title, timeout=2.0)
            kwargs = {}
            if control_type:
                kwargs["control_type"] = control_type

            # Try automation_id first
            ctrl = None
            try:
                ctrl = window.child_window(auto_id=control_identifier, **kwargs)
                if not ctrl.exists(timeout=0.5):
                    ctrl = None
            except Exception:
                pass

            if ctrl is None:
                try:
                    ctrl = window.child_window(title=control_identifier, **kwargs)
                    if not ctrl.exists(timeout=0.5):
                        ctrl = None
                except Exception:
                    pass

            if ctrl is None:
                time.sleep(0.5)
                continue

            if state == "exists":
                return {"status": "success", "control": control_identifier, "state": "exists"}
            elif state == "visible":
                if ctrl.is_visible():
                    return {"status": "success", "control": control_identifier, "state": "visible"}
            elif state == "enabled":
                if ctrl.is_enabled():
                    return {"status": "success", "control": control_identifier, "state": "enabled"}
            elif state == "ready":
                if ctrl.is_visible() and ctrl.is_enabled():
                    return {"status": "success", "control": control_identifier, "state": "ready"}

        except Exception:
            pass

        time.sleep(0.5)

    return {
        "status": "timeout",
        "message": f"Control '{control_identifier}' did not reach state '{state}' within {timeout}s",
    }


def wait_for_window_close(title: str, timeout: float = 30.0) -> dict:
    """Wait for a window to close/disappear.

    Args:
        title: Partial title of the window to wait for closing.
        timeout: Max seconds to wait.

    Returns:
        Dict with status.
    """
    deadline = time.time() + timeout
    title_lower = title.lower()

    while time.time() < deadline:
        found = False
        try:
            desktop = Desktop(backend="uia")
            for win in desktop.windows():
                try:
                    if win.is_visible() and title_lower in win.window_text().lower():
                        found = True
                        break
                except Exception:
                    pass
        except Exception:
            pass

        if not found:
            return {"status": "success", "message": f"Window '{title}' has closed"}

        time.sleep(0.5)

    return {"status": "timeout", "message": f"Window '{title}' did not close within {timeout}s"}


def wait_for_idle(
    window_title: str,
    timeout: float = 30.0,
) -> dict:
    """Wait for a window/application to become idle (ready for input).

    Args:
        window_title: Partial title of the window.
        timeout: Max seconds to wait.

    Returns:
        Dict with status.
    """
    try:
        window = get_window(window_title, timeout=timeout)
        # wait_for_idle is a pywinauto method that waits for the window's process to be idle
        window.wait("ready", timeout=timeout)
        return {"status": "success", "title": window.window_text(), "state": "idle"}
    except Exception as e:
        return {"status": "timeout", "message": f"Window did not become idle: {e}"}


def wait_for_text_change(
    window_title: str,
    control_identifier: str,
    current_text: str = "",
    timeout: float = 30.0,
    control_type: Optional[str] = None,
) -> dict:
    """Wait for a control's text to change from its current value.

    Args:
        window_title: Partial window title.
        control_identifier: Identifier of the control.
        current_text: The current text to watch for changes from. If empty, captures current.
        timeout: Max seconds to wait.
        control_type: Optional control type.

    Returns:
        Dict with status and new text value.
    """
    from src.automation.controls import _find_control

    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type)

    if not current_text:
        try:
            current_text = control.window_text() or ""
        except Exception:
            current_text = ""

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            new_text = control.window_text() or ""
            if new_text != current_text:
                return {
                    "status": "success",
                    "control": control_identifier,
                    "old_text": current_text,
                    "new_text": new_text,
                }
        except Exception:
            pass
        time.sleep(0.3)

    return {
        "status": "timeout",
        "message": f"Text in '{control_identifier}' did not change within {timeout}s",
        "current_text": current_text,
    }
