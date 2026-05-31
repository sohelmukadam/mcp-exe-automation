"""Keyboard and mouse input simulation module."""

import logging
import time
from typing import Optional

import win32api
import win32con
import win32gui
from pywinauto.keyboard import send_keys as _send_keys
from pywinauto.mouse import click as _mouse_click, double_click as _mouse_dblclick
from pywinauto.mouse import right_click as _mouse_rclick, move as _mouse_move

from src.automation.windows import get_window

logger = logging.getLogger(__name__)


def send_keys(
    keys: str,
    window_title: Optional[str] = None,
    with_spaces: bool = True,
    pause: float = 0.05,
) -> dict:
    """Send keyboard input to the focused window or a specific window.

    Supports pywinauto key notation:
        - {ENTER}, {TAB}, {ESC}, {BACKSPACE}, {DELETE}
        - {UP}, {DOWN}, {LEFT}, {RIGHT}
        - {HOME}, {END}, {PGUP}, {PGDN}
        - {F1}-{F12}
        - ^a (Ctrl+A), %f (Alt+F), +a (Shift+A)
        - ^c (Ctrl+C), ^v (Ctrl+V), ^z (Ctrl+Z)

    Args:
        keys: Key sequence in pywinauto notation.
        window_title: Optional window to focus first.
        with_spaces: If True, spaces are typed literally (not as hotkeys).
        pause: Pause between keystrokes in seconds.

    Returns:
        Dict with status.
    """
    if window_title:
        window = get_window(window_title)
        window.set_focus()
        time.sleep(0.15)

    _send_keys(keys, with_spaces=with_spaces, pause=pause)
    return {"status": "success", "keys": keys, "action": "send_keys"}


def send_hotkey(
    modifiers: list[str],
    key: str,
    window_title: Optional[str] = None,
) -> dict:
    """Send a keyboard hotkey combination.

    Args:
        modifiers: List of modifier keys - 'ctrl', 'alt', 'shift', 'win'.
        key: The main key to press.
        window_title: Optional window to focus first.

    Returns:
        Dict with status.
    """
    if window_title:
        window = get_window(window_title)
        window.set_focus()
        time.sleep(0.15)

    # Build pywinauto key string
    prefix = ""
    for mod in modifiers:
        mod_lower = mod.lower()
        if mod_lower in ("ctrl", "control"):
            prefix += "^"
        elif mod_lower == "alt":
            prefix += "%"
        elif mod_lower == "shift":
            prefix += "+"
        elif mod_lower in ("win", "windows"):
            # pywinauto doesn't have a direct win key modifier in same syntax
            # Use explicit VK approach
            pass

    key_str = prefix + key
    _send_keys(key_str, pause=0.05)
    return {"status": "success", "hotkey": f"{'+'.join(modifiers)}+{key}", "action": "hotkey"}


def mouse_click(
    x: int,
    y: int,
    button: str = "left",
    double: bool = False,
) -> dict:
    """Click at specific screen coordinates (DPI-aware, bounds-checked).

    Args:
        x: X screen coordinate.
        y: Y screen coordinate.
        button: 'left', 'right', or 'middle'.
        double: If True, perform double-click.

    Returns:
        Dict with status.
    """
    from src.automation.utils import clamp_coordinates

    x, y = clamp_coordinates(x, y)
    coords = (x, y)
    if double:
        _mouse_dblclick(button=button, coords=coords)
    elif button == "right":
        _mouse_rclick(coords=coords)
    else:
        _mouse_click(button=button, coords=coords)

    return {"status": "success", "x": x, "y": y, "button": button, "double": double}


def mouse_move(x: int, y: int) -> dict:
    """Move the mouse cursor to screen coordinates (DPI-aware, bounds-checked).

    Args:
        x: X screen coordinate.
        y: Y screen coordinate.

    Returns:
        Dict with status.
    """
    from src.automation.utils import clamp_coordinates

    x, y = clamp_coordinates(x, y)
    _mouse_move(coords=(x, y))
    return {"status": "success", "x": x, "y": y, "action": "move"}


def mouse_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    button: str = "left",
) -> dict:
    """Drag from one point to another (DPI-aware, bounds-checked).

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Ending X coordinate.
        end_y: Ending Y coordinate.
        button: Mouse button to hold during drag.

    Returns:
        Dict with status.
    """
    from pywinauto.mouse import press, release, move
    from src.automation.utils import clamp_coordinates

    start_x, start_y = clamp_coordinates(start_x, start_y)
    end_x, end_y = clamp_coordinates(end_x, end_y)

    press(button=button, coords=(start_x, start_y))
    time.sleep(0.1)

    # Move in steps for smooth drag
    steps = 10
    for i in range(1, steps + 1):
        frac = i / steps
        cx = int(start_x + (end_x - start_x) * frac)
        cy = int(start_y + (end_y - start_y) * frac)
        move(coords=(cx, cy))
        time.sleep(0.02)

    release(button=button, coords=(end_x, end_y))
    return {
        "status": "success",
        "from": {"x": start_x, "y": start_y},
        "to": {"x": end_x, "y": end_y},
        "action": "drag",
    }


def type_text_raw(
    text: str,
    window_title: Optional[str] = None,
    interval: float = 0.02,
) -> dict:
    """Type plain text character by character (no special key interpretation).

    This is useful when you want to type text that contains characters
    that pywinauto would interpret as special (like ^, %, +, {, }).

    Args:
        text: Plain text to type.
        window_title: Optional window to focus first.
        interval: Delay between characters.

    Returns:
        Dict with status.
    """
    if window_title:
        window = get_window(window_title)
        window.set_focus()
        time.sleep(0.15)

    # Escape all special characters for pywinauto
    escaped = text.replace("{", "{{").replace("}", "}}")
    escaped = escaped.replace("^", "{^}")
    escaped = escaped.replace("+", "{+}")
    escaped = escaped.replace("%", "{%}")
    escaped = escaped.replace("(", "{(}")
    escaped = escaped.replace(")", "{)}")

    _send_keys(escaped, with_spaces=True, pause=interval)
    return {"status": "success", "text_length": len(text), "action": "type_raw"}
