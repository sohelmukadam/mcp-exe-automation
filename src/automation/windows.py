"""Window discovery and management module using pywinauto with UIA backend.

Handles all types of Windows applications:
- Win32, WPF, UWP, Electron, Java, Qt, Delphi/VCL
- Minimized windows, background windows, multi-process apps
- System tray applications, dialog boxes, popup windows
"""

import logging
import re
import time
import unicodedata
from typing import Any, Optional

import win32con
import win32gui
from pywinauto import Application, Desktop

logger = logging.getLogger(__name__)


def _normalize_unicode(text: str) -> str:
    """Strip zero-width characters and normalize Unicode for reliable title matching.

    Many apps (Edge, Office) embed invisible Unicode chars in titles:
    - Zero-width space (U+200B), non-breaking space, etc.
    This normalizes them so user searches work regardless.
    """
    # Remove zero-width and invisible formatting characters
    invisible_chars = "\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad\u2060\u2061\u2062\u2063\u2064"
    for ch in invisible_chars:
        text = text.replace(ch, "")
    # Normalize Unicode forms (NFC)
    text = unicodedata.normalize("NFC", text)
    return text


def list_windows(visible_only: bool = True) -> list[dict]:
    """Return all top-level windows with their properties.

    Args:
        visible_only: If True, only return visible windows (includes minimized windows
            which are technically visible but have zero-size rectangles).

    Returns:
        List of window info dictionaries with title, handle, PID, class, rectangle, state.
    """
    windows: list[dict] = []
    seen_handles = set()

    try:
        desktop = Desktop(backend="uia")
        for win in desktop.windows():
            try:
                title = win.window_text()
                if not title.strip():
                    continue

                handle = win.handle
                if handle in seen_handles:
                    continue
                seen_handles.add(handle)

                # Check visibility - include minimized windows (they have handles but 0 rect)
                is_visible = win.is_visible()
                is_minimized = False
                try:
                    is_minimized = bool(win32gui.IsIconic(handle))
                except Exception:
                    pass

                if visible_only and not is_visible and not is_minimized:
                    continue

                rect = win.rectangle()
                windows.append({
                    "title": title,
                    "handle": handle,
                    "process_id": win.process_id(),
                    "class_name": win.element_info.class_name or "",
                    "rectangle": {
                        "left": rect.left,
                        "top": rect.top,
                        "right": rect.right,
                        "bottom": rect.bottom,
                        "width": rect.width(),
                        "height": rect.height(),
                    },
                    "is_enabled": win.is_enabled(),
                    "is_visible": is_visible,
                    "is_minimized": is_minimized,
                })
            except Exception as e:
                logger.debug("Skipping window due to error: %s", e)
    except Exception as e:
        logger.error("Failed to enumerate windows: %s", e)
    return windows


def get_active_window() -> dict:
    """Get information about the currently focused/foreground window.

    Useful for detecting which window is on top (e.g., after a dialog appears,
    after launching an app, or to verify focus was set correctly).

    Returns:
        Dict with title, handle, process_id, class_name, rectangle, and control summary.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {"status": "error", "message": "No foreground window found"}

        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        pid = 0
        try:
            import ctypes
            lpdw_pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
            pid = lpdw_pid.value
        except Exception:
            pass

        rect = win32gui.GetWindowRect(hwnd)

        # Get a quick summary of immediate child controls for the agent
        control_summary = []
        try:
            app = Application(backend="uia").connect(handle=hwnd)
            win = app.window(handle=hwnd)
            wrapper = win.wrapper_object()
            for child in wrapper.children():
                try:
                    ctrl_type = child.element_info.control_type or ""
                    ctrl_name = child.window_text() or ""
                    ctrl_aid = child.element_info.automation_id or ""
                    if ctrl_type and ctrl_type not in ("Pane", "Custom"):
                        control_summary.append({
                            "type": ctrl_type,
                            "name": ctrl_name[:50],
                            "automation_id": ctrl_aid[:50],
                        })
                except Exception:
                    pass
        except Exception:
            pass

        return {
            "status": "success",
            "title": title,
            "handle": hwnd,
            "process_id": pid,
            "class_name": class_name,
            "rectangle": {
                "left": rect[0], "top": rect[1],
                "right": rect[2], "bottom": rect[3],
                "width": rect[2] - rect[0], "height": rect[3] - rect[1],
            },
            "top_level_controls": control_summary[:20],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_window(title: str, backend: str = "uia", timeout: float = 5.0) -> Any:
    """Find a window by partial title match (includes minimized windows).

    Search strategies:
    1. Visible windows with partial title match (case-insensitive)
    2. All windows (including minimized/hidden) with title match
    3. Window class name match
    4. Regex pattern match

    Args:
        title: Partial window title to search for (or regex pattern).
        backend: pywinauto backend ('uia' or 'win32').
        timeout: Max seconds to wait for the window to appear.

    Returns:
        The matching window wrapper (WindowSpecification).

    Raises:
        ValueError: If no window matching the title is found, or title is empty.
    """
    # Input validation
    if not title or not title.strip():
        raise ValueError("Window title cannot be empty or whitespace-only")
    deadline = time.time() + timeout
    title_lower = _normalize_unicode(title.lower())

    # Check if title looks like a regex pattern
    is_regex = any(c in title for c in r".*+?[](){}|^$\\")
    pattern = None
    if is_regex:
        try:
            pattern = re.compile(title, re.IGNORECASE)
        except re.error:
            pattern = None

    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break

        try:
            desktop = Desktop(backend=backend)
            # First pass: visible windows (preferred) - fastest
            for win in desktop.windows():
                try:
                    win_title = win.window_text()
                    if not win_title:
                        continue
                    if win.is_visible():
                        matched = title_lower in _normalize_unicode(win_title.lower())
                        if not matched and pattern:
                            matched = bool(pattern.search(_normalize_unicode(win_title)))
                        if matched:
                            handle = win.handle
                            app = Application(backend=backend).connect(handle=handle)
                            return app.window(handle=handle)
                except Exception:
                    pass

            # Second pass: include minimized/hidden windows
            for win in desktop.windows():
                try:
                    win_title = win.window_text()
                    if not win_title:
                        continue
                    matched = title_lower in _normalize_unicode(win_title.lower())
                    if not matched and pattern:
                        matched = bool(pattern.search(_normalize_unicode(win_title)))
                    if matched:
                        handle = win.handle
                        app = Application(backend=backend).connect(handle=handle)
                        return app.window(handle=handle)
                except Exception:
                    pass

            # Third pass: match by window class name
            for win in desktop.windows():
                try:
                    cls_name = win.element_info.class_name or ""
                    if cls_name and title_lower in cls_name.lower():
                        handle = win.handle
                        app = Application(backend=backend).connect(handle=handle)
                        return app.window(handle=handle)
                except Exception:
                    pass

        except Exception:
            pass

        # Only sleep if we have enough remaining time
        sleep_time = min(0.3, remaining - 0.05)
        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            break

    raise ValueError(f"Window with title containing '{title}' not found")


def get_window_by_handle(handle: int, backend: str = "uia") -> Any:
    """Get a window by its handle (HWND).

    Args:
        handle: The window handle.
        backend: pywinauto backend.

    Returns:
        Window wrapper.
    """
    app = Application(backend=backend).connect(handle=handle)
    return app.window(handle=handle)


def focus_window(title: str) -> dict:
    """Bring a window to the foreground by title (restores if minimized).

    Uses multiple strategies to reliably bring any window to foreground:
    1. Restore from minimized if needed
    2. win32gui.SetForegroundWindow (fastest)
    3. Alt-key trick for stubborn windows
    4. pywinauto set_focus() fallback

    Args:
        title: Partial window title.

    Returns:
        Dict with status.
    """
    import ctypes

    window = get_window(title)
    wrapper = window.wrapper_object()
    hwnd = wrapper.handle

    # Restore if minimized
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.3)
    except Exception:
        try:
            if window.is_minimized():
                window.restore()
                time.sleep(0.3)
        except Exception:
            pass

    # Strategy 1: Direct SetForegroundWindow
    focused = False
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.1)
        focused = (win32gui.GetForegroundWindow() == hwnd)
    except Exception:
        pass

    # Strategy 2: Alt-key trick (bypasses Windows' foreground lock)
    if not focused:
        try:
            # Simulate an Alt key press/release to allow SetForegroundWindow
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # Alt down
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # Alt up
            time.sleep(0.05)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)
            focused = (win32gui.GetForegroundWindow() == hwnd)
        except Exception:
            pass

    # Strategy 3: BringWindowToTop + ShowWindow
    if not focused:
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            time.sleep(0.1)
        except Exception:
            pass

    # Strategy 4: pywinauto set_focus (handles UIA-specific focus)
    try:
        window.set_focus()
    except Exception:
        pass

    time.sleep(0.1)
    return {"status": "success", "action": "focused", "title": wrapper.window_text()}


def minimize_window(title: str) -> dict:
    """Minimize a window by title."""
    window = get_window(title)
    window.minimize()
    return {"status": "success", "action": "minimized", "title": window.window_text()}


def maximize_window(title: str) -> dict:
    """Maximize a window by title."""
    window = get_window(title)
    window.maximize()
    return {"status": "success", "action": "maximized", "title": window.window_text()}


def restore_window(title: str) -> dict:
    """Restore a window from minimized/maximized state."""
    window = get_window(title)
    window.restore()
    return {"status": "success", "action": "restored", "title": window.window_text()}


def close_window(title: str) -> dict:
    """Close a window by title."""
    window = get_window(title)
    window_title = window.window_text()
    window.close()
    return {"status": "success", "action": "closed", "title": window_title}


def resize_window(title: str, width: int, height: int) -> dict:
    """Resize a window to specified dimensions.

    Args:
        title: Partial window title.
        width: Target width in pixels.
        height: Target height in pixels.

    Returns:
        Dict with status and new dimensions.
    """
    window = get_window(title)
    rect = window.rectangle()
    window.move_window(x=rect.left, y=rect.top, width=width, height=height)
    return {
        "status": "success",
        "action": "resized",
        "title": window.window_text(),
        "width": width,
        "height": height,
    }


def move_window(title: str, x: int, y: int) -> dict:
    """Move a window to specified screen coordinates.

    Args:
        title: Partial window title.
        x: Target x position.
        y: Target y position.

    Returns:
        Dict with status.
    """
    window = get_window(title)
    rect = window.rectangle()
    window.move_window(x=x, y=y, width=rect.width(), height=rect.height())
    return {
        "status": "success",
        "action": "moved",
        "title": window.window_text(),
        "x": x,
        "y": y,
    }


def wait_for_window(
    title: str,
    timeout: float = 30.0,
    backend: str = "uia",
) -> dict:
    """Wait for a window with the given title to appear.

    Args:
        title: Partial window title to wait for.
        timeout: Max seconds to wait.
        backend: pywinauto backend.

    Returns:
        Dict with status and window info when found.
    """
    try:
        window = get_window(title, backend=backend, timeout=timeout)
        return {
            "status": "success",
            "title": window.window_text(),
            "handle": window.handle,
        }
    except ValueError:
        return {
            "status": "timeout",
            "message": f"Window '{title}' did not appear within {timeout}s",
        }


def _build_control_tree(control: Any, max_depth: int = 10, current_depth: int = 0,
                        node_count: list = None) -> dict:
    """Recursively build a control tree dictionary.

    Args:
        control: The control wrapper to process.
        max_depth: Maximum recursion depth to prevent infinite loops.
        current_depth: Current depth in the recursion.
        node_count: Mutable list tracking total nodes [count, max].

    Returns:
        Dictionary representing the control and its children.
    """
    if node_count is None:
        node_count = [0, 500]  # default max 500 nodes

    if current_depth >= max_depth:
        return {"name": "...(depth limit)", "children": []}

    node_count[0] += 1
    if node_count[0] > node_count[1]:
        return {"name": "...(node limit reached)", "children": []}

    try:
        rect = control.rectangle()
        rectangle = {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
        }
    except Exception:
        rectangle = {}

    try:
        is_enabled = control.is_enabled()
    except Exception:
        is_enabled = None

    node: dict = {
        "name": control.window_text() or "",
        "control_type": control.element_info.control_type or "",
        "class_name": control.element_info.class_name or "",
        "automation_id": control.element_info.automation_id or "",
        "rectangle": rectangle,
        "is_enabled": is_enabled,
        "children": [],
    }

    try:
        for child in control.children():
            if node_count[0] > node_count[1]:
                node["children"].append({"name": "...(node limit)", "children": []})
                break
            node["children"].append(
                _build_control_tree(child, max_depth, current_depth + 1, node_count)
            )
    except Exception as e:
        logger.debug("Error enumerating children: %s", e)

    return node


def get_control_tree(title: str, max_depth: int = 8) -> list[dict]:
    """Get a structured tree of controls for the specified window.

    Args:
        title: Partial window title to search for.
        max_depth: Maximum depth of the control tree (default 8).

    Returns:
        List of control tree dictionaries for top-level children.
    """
    window = get_window(title)
    tree: list[dict] = []
    try:
        wrapper = window.wrapper_object()
        for child in wrapper.children():
            tree.append(_build_control_tree(child, max_depth=max_depth))
    except Exception as e:
        logger.error("Error building control tree for '%s': %s", title, e)
        raise ValueError(f"Failed to get control tree for '{title}': {e}") from e
    return tree
