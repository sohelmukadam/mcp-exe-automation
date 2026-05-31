"""MCP server for generalized Windows desktop automation.

Registers tools with the FastMCP server that expose:
  - Application process management (launch, attach, terminate)
  - Window discovery, manipulation, and management
  - Control interaction (click, type, select, scroll)
  - Keyboard and mouse input simulation
  - Menu navigation
  - Dialog/popup handling
  - Screenshot capture
  - Clipboard operations
  - Wait conditions for synchronization

Works with ANY Windows desktop application (.exe) using the UIA (UI Automation)
framework via pywinauto. No application-specific COM objects or APIs required.
"""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.automation.process import (
    launch_application,
    attach_to_application,
    terminate_application,
    list_running_applications,
)
from src.automation.windows import (
    list_windows,
    get_active_window,
    get_control_tree,
    focus_window,
    minimize_window,
    maximize_window,
    restore_window,
    close_window,
    resize_window,
    move_window,
    wait_for_window,
)
from src.automation.controls import (
    click_control,
    type_text,
    get_control_text,
    find_controls,
    select_combobox_item,
    check_checkbox,
    select_listbox_item,
    select_tab,
    scroll_control,
    get_all_text,
    get_control_state,
    wait_and_click,
)
from src.automation.keyboard_mouse import (
    send_keys,
    send_hotkey,
    mouse_click,
    mouse_move,
    mouse_drag,
    type_text_raw,
)
from src.automation.menu import (
    click_menu_item,
    get_menu_items,
    use_context_menu,
)
from src.automation.screenshot import (
    capture_screenshot,
    capture_control_screenshot,
)
from src.automation.dialogs import (
    handle_dialog,
    get_dialog_info,
    wait_for_dialog,
)
from src.automation.clipboard import (
    get_clipboard_text,
    set_clipboard_text,
    clear_clipboard,
    paste_from_clipboard,
    copy_to_clipboard,
)
from src.automation.waits import (
    wait_for_control,
    wait_for_window_close,
    wait_for_idle,
    wait_for_text_change,
)
from src.automation.advanced import (
    get_element_at_point,
    get_control_properties,
    expand_tree_item,
    collapse_tree_item,
    select_tree_item,
    read_datagrid,
    get_window_info,
    find_windows_by_pid,
)

logger = logging.getLogger(__name__)

mcp = FastMCP("windows-automation")


def _make_error(e: Exception, context: str = "") -> dict:
    """Create a structured error response with recovery hints for the AI agent.

    Includes:
    - error: The error message
    - retryable: Whether retrying might succeed
    - suggestion: What the agent should do to recover
    """
    msg = str(e)
    error_type = type(e).__name__

    retryable = False
    suggestion = ""

    if "not found" in msg.lower():
        if "control" in msg.lower():
            retryable = True
            suggestion = "Control not found. Use find_controls_tool() to discover available controls in the window."
        elif "window" in msg.lower():
            retryable = True
            suggestion = "Window may have changed title or closed. Use list_windows_tool() to see current windows."
        else:
            retryable = True
            suggestion = "Element not found. Use get_focused_window() to check current state."
    elif "empty" in msg.lower() or "whitespace" in msg.lower():
        suggestion = "Provide a non-empty window title or control identifier."
    elif "timeout" in msg.lower() or "timed out" in msg.lower():
        retryable = True
        suggestion = "Operation timed out. The application may be busy. Try wait_app_idle() first, then retry."
    elif "cannot type" in msg.lower():
        suggestion = "Target control is not editable. Use find_controls_tool() to find an Edit or Document control."
    elif "foreground" in msg.lower() or "focus" in msg.lower():
        retryable = True
        suggestion = "Window focus issue. Try focus_window_tool() first, then retry the operation."
    elif isinstance(e, (ConnectionError, OSError)):
        retryable = True
        suggestion = "Connection/system error. Wait briefly and retry."
    else:
        retryable = True
        suggestion = "Unexpected error. Try using get_focused_window() to check current state, then retry."

    result = {"error": msg, "error_type": error_type, "retryable": retryable}
    if suggestion:
        result["suggestion"] = suggestion
    if context:
        result["context"] = context
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION PROCESS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def launch_app(
    exe_path: str,
    args: Optional[list[str]] = None,
    work_dir: Optional[str] = None,
    backend: str = "uia",
    timeout: float = 30.0,
) -> dict:
    """Launch a Windows application and wait for it to be ready.

    Args:
        exe_path: Full path to the executable (e.g., 'C:\\Program Files\\App\\app.exe').
        args: Optional list of command-line arguments.
        work_dir: Working directory. Defaults to the exe's directory.
        backend: Automation backend - 'uia' (recommended for modern apps) or 'win32' (legacy).
        timeout: Max seconds to wait for the app to become ready.
    """
    try:
        return launch_application(exe_path, args, work_dir, backend, timeout)
    except Exception as e:
        logger.error("Failed to launch '%s': %s", exe_path, e)
        return _make_error(e, f"launch '{exe_path}'")


@mcp.tool()
def attach_app(
    pid: Optional[int] = None,
    title: Optional[str] = None,
    exe_name: Optional[str] = None,
    backend: str = "uia",
) -> dict:
    """Attach to a running application by PID, window title, or executable name.

    Args:
        pid: Process ID to attach to.
        title: Window title (partial match supported).
        exe_name: Executable name (e.g., 'notepad.exe').
        backend: Automation backend - 'uia' or 'win32'.
    """
    try:
        return attach_to_application(pid, title, exe_name, backend)
    except Exception as e:
        logger.error("Failed to attach: %s", e)
        return _make_error(e, "attach to application")


@mcp.tool()
def terminate_app(pid: int) -> dict:
    """Terminate a running application by its process ID.

    Args:
        pid: Process ID of the application to terminate.
    """
    try:
        return terminate_application(pid)
    except Exception as e:
        logger.error("Failed to terminate PID %d: %s", pid, e)
        return _make_error(e, f"terminate PID {pid}")


@mcp.tool()
def list_apps() -> list[dict]:
    """List all running applications with visible windows."""
    try:
        return list_running_applications()
    except Exception as e:
        logger.error("Failed to list apps: %s", e)
        return [_make_error(e, "list applications")]


# ═══════════════════════════════════════════════════════════════════════════════
# WINDOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_windows_tool(visible_only: bool = True) -> list[dict]:
    """List all top-level windows with their titles, handles, process IDs, and positions.

    Args:
        visible_only: If True, only return visible windows (default True).
    """
    try:
        return list_windows(visible_only)
    except Exception as e:
        logger.error("Failed to list windows: %s", e)
        return [_make_error(e, "list windows")]


@mcp.tool()
def get_focused_window() -> dict:
    """Get information about the currently active/focused window.

    Returns the title, handle, process ID, position, and a summary of top-level
    controls in the window. Use this to:
    - Detect what dialog or window just appeared
    - Verify focus was correctly set
    - Discover what application is currently in the foreground
    """
    try:
        return get_active_window()
    except Exception as e:
        logger.error("Failed to get active window: %s", e)
        return _make_error(e, "get active window")


@mcp.tool()
def inspect_window(window_title: str, max_depth: int = 8) -> dict:
    """Get the full control tree for a window, showing all UI elements.

    Use this to discover what controls exist in a window before interacting with them.
    Returns a hierarchical tree with control names, types, and automation IDs.

    Args:
        window_title: Window title (partial match supported).
        max_depth: Maximum depth of the tree to return (default 8, increase for deeply nested UIs).
    """
    try:
        tree = get_control_tree(window_title, max_depth)
        return {"window_title": window_title, "controls": tree}
    except Exception as e:
        logger.error("Failed to inspect window '%s': %s", window_title, e)
        return _make_error(e, f"inspect window '{window_title}'")


@mcp.tool()
def focus_window_tool(window_title: str) -> dict:
    """Bring a window to the foreground and give it focus.

    Args:
        window_title: Window title (partial match supported).
    """
    try:
        return focus_window(window_title)
    except Exception as e:
        logger.error("Failed to focus window '%s': %s", window_title, e)
        return _make_error(e, f"focus window '{window_title}'")


@mcp.tool()
def manage_window(
    window_title: str,
    action: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
) -> dict:
    """Manage a window's state: minimize, maximize, restore, close, resize, or move.

    Args:
        window_title: Window title (partial match supported).
        action: One of 'minimize', 'maximize', 'restore', 'close', 'resize', 'move'.
        width: Width in pixels (required for 'resize').
        height: Height in pixels (required for 'resize').
        x: X position (required for 'move').
        y: Y position (required for 'move').
    """
    try:
        if action == "minimize":
            return minimize_window(window_title)
        elif action == "maximize":
            return maximize_window(window_title)
        elif action == "restore":
            return restore_window(window_title)
        elif action == "close":
            return close_window(window_title)
        elif action == "resize":
            if width is None or height is None:
                return {"error": "width and height are required for resize"}
            return resize_window(window_title, width, height)
        elif action == "move":
            if x is None or y is None:
                return {"error": "x and y are required for move"}
            return move_window(window_title, x, y)
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        logger.error("Failed to %s window '%s': %s", action, window_title, e)
        return _make_error(e, f"{action} window '{window_title}'")


@mcp.tool()
def wait_window(
    window_title: str,
    timeout: float = 30.0,
) -> dict:
    """Wait for a window with the given title to appear.

    Args:
        window_title: Window title to wait for (partial match supported).
        timeout: Maximum seconds to wait (default 30).
    """
    try:
        return wait_for_window(window_title, timeout)
    except Exception as e:
        logger.error("Failed waiting for window '%s': %s", window_title, e)
        return _make_error(e, f"wait for window '{window_title}'")


# ═══════════════════════════════════════════════════════════════════════════════
# CONTROL INTERACTION
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def click_control_tool(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    click_type: str = "left",
    double_click: bool = False,
    index: int = 0,
) -> dict:
    """Click a UI control in a window.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID, name/title, or class name of the control.
        control_type: Optional type to narrow search (e.g., 'Button', 'MenuItem', 'Edit').
        click_type: Mouse button - 'left', 'right', or 'middle'.
        double_click: If True, perform a double-click.
        index: If multiple controls match, select by 0-based index (default 0 = first match).
    """
    try:
        return click_control(window_title, control_identifier, control_type, click_type, double_click, index)
    except Exception as e:
        logger.error("Failed to click '%s' in '%s': %s", control_identifier, window_title, e)
        return _make_error(e, f"click '{control_identifier}' in '{window_title}'")


@mcp.tool()
def type_text_tool(
    window_title: str,
    control_identifier: str,
    text: str,
    control_type: Optional[str] = None,
    clear_first: bool = False,
    press_enter: bool = False,
    index: int = 0,
) -> dict:
    """Type text into a UI control.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID, name/title, or class name of the control.
        text: The text string to type.
        control_type: Optional type to narrow search (e.g., 'Edit', 'ComboBox', 'Document').
        clear_first: If True, select all and replace existing text.
        press_enter: If True, press Enter after typing.
        index: If multiple controls match, select by 0-based index (default 0).
    """
    try:
        return type_text(window_title, control_identifier, text, control_type, clear_first, press_enter, index)
    except Exception as e:
        logger.error("Failed to type in '%s' in '%s': %s", control_identifier, window_title, e)
        return _make_error(e, f"type into '{control_identifier}' in '{window_title}'")


@mcp.tool()
def read_control_text(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
) -> dict:
    """Read the text content of a UI control.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID, name/title, or class name of the control.
        control_type: Optional type to narrow search.
    """
    try:
        return get_control_text(window_title, control_identifier, control_type)
    except Exception as e:
        logger.error("Failed to read '%s' in '%s': %s", control_identifier, window_title, e)
        return _make_error(e, f"read text from '{control_identifier}' in '{window_title}'")


@mcp.tool()
def find_controls_tool(
    window_title: str,
    control_type: Optional[str] = None,
    name_pattern: Optional[str] = None,
    max_depth: int = 12,
    enabled_only: bool = False,
    visible_only: bool = False,
) -> list[dict]:
    """Find all UI controls in a window matching the given criteria.

    Args:
        window_title: Title of the target window.
        control_type: Filter by control type (e.g., 'Button', 'Edit', 'CheckBox', 'ComboBox', 'Document', 'MenuItem', 'TreeItem', 'ListItem', 'DataItem', 'Tab', 'TabItem').
        name_pattern: Filter by name/title or automation_id containing this text.
        max_depth: Maximum depth to search in the control hierarchy (default 12, use 15+ for deeply nested apps).
        enabled_only: If True, only return enabled controls.
        visible_only: If True, only return visible controls.
    """
    try:
        return find_controls(window_title, control_type, name_pattern, max_depth, enabled_only, visible_only)
    except Exception as e:
        logger.error("Failed to find controls in '%s': %s", window_title, e)
        return [_make_error(e, f"find controls in '{window_title}'")]


@mcp.tool()
def select_combo_item(
    window_title: str,
    control_identifier: str,
    item_text: str,
) -> dict:
    """Select an item from a dropdown/combobox control.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID or name of the combobox.
        item_text: The text of the item to select.
    """
    try:
        return select_combobox_item(window_title, control_identifier, item_text)
    except Exception as e:
        logger.error("Failed to select in combobox: %s", e)
        return _make_error(e, f"select '{item_text}' in combobox '{control_identifier}'")


@mcp.tool()
def toggle_checkbox(
    window_title: str,
    control_identifier: str,
    check: bool = True,
) -> dict:
    """Check or uncheck a checkbox control.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID or name of the checkbox.
        check: True to check, False to uncheck.
    """
    try:
        return check_checkbox(window_title, control_identifier, check)
    except Exception as e:
        logger.error("Failed to toggle checkbox: %s", e)
        return _make_error(e, f"toggle checkbox '{control_identifier}'")


@mcp.tool()
def select_list_item(
    window_title: str,
    control_identifier: str,
    item_text: str,
) -> dict:
    """Select an item in a list control by its text.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID or name of the list control.
        item_text: The text of the item to select.
    """
    try:
        return select_listbox_item(window_title, control_identifier, item_text)
    except Exception as e:
        logger.error("Failed to select list item: %s", e)
        return _make_error(e, f"select '{item_text}' in list '{control_identifier}'")


@mcp.tool()
def select_tab_tool(
    window_title: str,
    control_identifier: str,
    tab_name: str,
) -> dict:
    """Select a tab in a tab control.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID or name of the tab control.
        tab_name: Name/text of the tab to select.
    """
    try:
        return select_tab(window_title, control_identifier, tab_name)
    except Exception as e:
        logger.error("Failed to select tab: %s", e)
        return _make_error(e, f"select tab '{tab_name}'")


@mcp.tool()
def scroll_control_tool(
    window_title: str,
    control_identifier: str,
    direction: str = "down",
    amount: int = 3,
) -> dict:
    """Scroll a control in a window.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID or name of the control to scroll.
        direction: Scroll direction - 'up', 'down', 'left', or 'right'.
        amount: Number of scroll increments.
    """
    try:
        return scroll_control(window_title, control_identifier, direction, amount)
    except Exception as e:
        logger.error("Failed to scroll: %s", e)
        return _make_error(e, f"scroll '{control_identifier}'")


# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARD & MOUSE
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def send_keys_tool(
    keys: str,
    window_title: Optional[str] = None,
) -> dict:
    """Send keyboard input to the focused window or a specific window.

    Key notation examples:
        - Regular text: 'Hello World'
        - Special keys: '{ENTER}', '{TAB}', '{ESC}', '{BACKSPACE}', '{DELETE}'
        - Arrow keys: '{UP}', '{DOWN}', '{LEFT}', '{RIGHT}'
        - Function keys: '{F1}' through '{F12}'
        - Ctrl combos: '^a' (select all), '^c' (copy), '^v' (paste), '^s' (save)
        - Alt combos: '%f' (Alt+F), '%{F4}' (Alt+F4)
        - Shift combos: '+a' (Shift+A)
        - Combined: '^+s' (Ctrl+Shift+S)

    Args:
        keys: Key sequence in pywinauto notation.
        window_title: Optional window to focus before sending keys.
    """
    try:
        return send_keys(keys, window_title)
    except Exception as e:
        logger.error("Failed to send keys: %s", e)
        return _make_error(e, "send keys")


@mcp.tool()
def send_hotkey_tool(
    modifiers: list[str],
    key: str,
    window_title: Optional[str] = None,
) -> dict:
    """Send a keyboard hotkey/shortcut combination.

    Args:
        modifiers: List of modifier keys - 'ctrl', 'alt', 'shift'.
        key: The main key (e.g., 's', 'f4', 'enter', 'tab').
        window_title: Optional window to focus first.
    """
    try:
        return send_hotkey(modifiers, key, window_title)
    except Exception as e:
        logger.error("Failed to send hotkey: %s", e)
        return _make_error(e, f"send hotkey {'+'.join(modifiers)}+{key}")


@mcp.tool()
def click_at(
    x: int,
    y: int,
    button: str = "left",
    double: bool = False,
) -> dict:
    """Click at specific screen coordinates.

    Args:
        x: X screen coordinate (pixels from left).
        y: Y screen coordinate (pixels from top).
        button: Mouse button - 'left', 'right', or 'middle'.
        double: If True, perform double-click.
    """
    try:
        return mouse_click(x, y, button, double)
    except Exception as e:
        logger.error("Failed to click at (%d, %d): %s", x, y, e)
        return _make_error(e, f"click at ({x}, {y})")


@mcp.tool()
def move_mouse(x: int, y: int) -> dict:
    """Move the mouse cursor to screen coordinates.

    Args:
        x: X screen coordinate.
        y: Y screen coordinate.
    """
    try:
        return mouse_move(x, y)
    except Exception as e:
        logger.error("Failed to move mouse: %s", e)
        return _make_error(e, "move mouse")


@mcp.tool()
def drag_mouse(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    button: str = "left",
) -> dict:
    """Drag from one screen position to another.

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Ending X coordinate.
        end_y: Ending Y coordinate.
        button: Mouse button to hold during drag.
    """
    try:
        return mouse_drag(start_x, start_y, end_x, end_y, button)
    except Exception as e:
        logger.error("Failed to drag: %s", e)
        return _make_error(e, "mouse drag")


@mcp.tool()
def type_raw_text(
    text: str,
    window_title: Optional[str] = None,
) -> dict:
    """Type plain text without interpreting special characters.

    Use this when typing text that contains characters like ^, %, +, {, }
    which would otherwise be interpreted as keyboard shortcuts.

    Args:
        text: Plain text to type exactly as-is.
        window_title: Optional window to focus first.
    """
    try:
        return type_text_raw(text, window_title)
    except Exception as e:
        logger.error("Failed to type raw text: %s", e)
        return _make_error(e, "type raw text")


# ═══════════════════════════════════════════════════════════════════════════════
# MENU NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def click_menu(
    window_title: str,
    menu_path: str,
) -> dict:
    """Click a menu item by its path in the menu hierarchy.

    Args:
        window_title: Title of the target window.
        menu_path: Menu path using '->' separator (e.g., 'File->Save As', 'Edit->Find->Find Next').
    """
    try:
        return click_menu_item(window_title, menu_path)
    except Exception as e:
        logger.error("Failed to click menu '%s': %s", menu_path, e)
        return _make_error(e, f"click menu '{menu_path}'")


@mcp.tool()
def list_menu_items(
    window_title: str,
    menu_name: Optional[str] = None,
) -> dict:
    """List available menu items from a window's menu bar.

    Args:
        window_title: Title of the target window.
        menu_name: Optional top-level menu to expand (e.g., 'File', 'Edit'). Lists all top-level menus if None.
    """
    try:
        return get_menu_items(window_title, menu_name)
    except Exception as e:
        logger.error("Failed to list menu items: %s", e)
        return _make_error(e, "list menu items")


@mcp.tool()
def context_menu_click(
    window_title: str,
    control_identifier: str,
    menu_item_text: str,
    control_type: Optional[str] = None,
) -> dict:
    """Right-click a control and select an item from the context menu.

    Args:
        window_title: Title of the target window.
        control_identifier: Control to right-click on.
        menu_item_text: Text of the context menu item to click.
        control_type: Optional control type to narrow the search.
    """
    try:
        return use_context_menu(window_title, control_identifier, menu_item_text, control_type)
    except Exception as e:
        logger.error("Failed context menu action: %s", e)
        return _make_error(e, f"context menu '{menu_item_text}'")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREENSHOTS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def take_screenshot(
    window_title: Optional[str] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Capture a screenshot of a specific window or the full desktop.

    Args:
        window_title: Window to capture. Captures full desktop if None.
        output_path: File path to save. Auto-generates if None.
    """
    try:
        return capture_screenshot(window_title, output_path)
    except Exception as e:
        logger.error("Failed to take screenshot: %s", e)
        return _make_error(e, "take screenshot")


@mcp.tool()
def take_control_screenshot(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Capture a screenshot of a specific UI control.

    Args:
        window_title: Title of the parent window.
        control_identifier: The automation ID or name of the control.
        control_type: Optional control type filter.
        output_path: File path to save. Auto-generates if None.
    """
    try:
        return capture_control_screenshot(window_title, control_identifier, control_type, output_path)
    except Exception as e:
        logger.error("Failed to capture control screenshot: %s", e)
        return _make_error(e, "capture control screenshot")


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOGS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def handle_dialog_tool(
    title: Optional[str] = None,
    button_text: Optional[str] = None,
    action: str = "accept",
    timeout: float = 5.0,
) -> dict:
    """Handle a dialog box or popup window.

    Args:
        title: Dialog title (partial match). Handles topmost if None.
        button_text: Specific button to click (for action='click_button').
        action: How to handle - 'accept' (OK/Yes/Enter), 'dismiss' (Cancel/No/Escape), 'click_button'.
        timeout: Max seconds to wait for the dialog.
    """
    try:
        return handle_dialog(title, button_text, action, timeout)
    except Exception as e:
        logger.error("Failed to handle dialog: %s", e)
        return _make_error(e, "handle dialog")


@mcp.tool()
def inspect_dialog(title: Optional[str] = None) -> dict:
    """Get information about an open dialog (title, buttons, text content).

    Args:
        title: Dialog title (partial match). Inspects topmost if None.
    """
    try:
        return get_dialog_info(title)
    except Exception as e:
        logger.error("Failed to inspect dialog: %s", e)
        return _make_error(e, "inspect dialog")


@mcp.tool()
def wait_dialog(
    title: str,
    timeout: float = 30.0,
    action: Optional[str] = None,
    button_text: Optional[str] = None,
) -> dict:
    """Wait for a dialog to appear and optionally handle it automatically.

    Args:
        title: Expected dialog title (partial match).
        timeout: Max seconds to wait.
        action: Optional action when found - 'accept', 'dismiss', 'click_button'.
        button_text: Button to click if action is 'click_button'.
    """
    try:
        return wait_for_dialog(title, timeout, action, button_text)
    except Exception as e:
        logger.error("Failed waiting for dialog '%s': %s", title, e)
        return _make_error(e, f"wait for dialog '{title}'")


# ═══════════════════════════════════════════════════════════════════════════════
# CLIPBOARD
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def clipboard_get() -> dict:
    """Get the current text content of the Windows clipboard."""
    try:
        return get_clipboard_text()
    except Exception as e:
        logger.error("Failed to get clipboard: %s", e)
        return _make_error(e, "get clipboard")


@mcp.tool()
def clipboard_set(text: str) -> dict:
    """Set text content to the Windows clipboard.

    Args:
        text: Text to place on the clipboard.
    """
    try:
        return set_clipboard_text(text)
    except Exception as e:
        logger.error("Failed to set clipboard: %s", e)
        return _make_error(e, "set clipboard")


@mcp.tool()
def clipboard_paste(window_title: Optional[str] = None) -> dict:
    """Paste clipboard content into the focused or specified window (Ctrl+V).

    Args:
        window_title: Optional window to focus before pasting.
    """
    try:
        return paste_from_clipboard(window_title)
    except Exception as e:
        logger.error("Failed to paste: %s", e)
        return _make_error(e, "paste from clipboard")


@mcp.tool()
def clipboard_copy(window_title: Optional[str] = None) -> dict:
    """Copy selected content to clipboard (Ctrl+C) and return the text.

    Args:
        window_title: Optional window to focus before copying.
    """
    try:
        return copy_to_clipboard(window_title)
    except Exception as e:
        logger.error("Failed to copy: %s", e)
        return _make_error(e, "copy to clipboard")


# ═══════════════════════════════════════════════════════════════════════════════
# WAIT / SYNCHRONIZATION
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def wait_for_control_tool(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    timeout: float = 30.0,
    state: str = "exists",
) -> dict:
    """Wait for a UI control to reach a specific state.

    Args:
        window_title: Title of the parent window.
        control_identifier: The automation ID or name of the control.
        control_type: Optional control type filter.
        timeout: Max seconds to wait (default 30).
        state: Target state - 'exists', 'visible', 'enabled', or 'ready' (visible+enabled).
    """
    try:
        return wait_for_control(window_title, control_identifier, control_type, timeout, state)
    except Exception as e:
        logger.error("Failed waiting for control: %s", e)
        return _make_error(e, f"wait for control '{control_identifier}'")


@mcp.tool()
def wait_window_close(title: str, timeout: float = 30.0) -> dict:
    """Wait for a window to close/disappear.

    Args:
        title: Title of the window to watch (partial match).
        timeout: Max seconds to wait.
    """
    try:
        return wait_for_window_close(title, timeout)
    except Exception as e:
        logger.error("Failed waiting for window close: %s", e)
        return _make_error(e, f"wait for window close '{title}'")


@mcp.tool()
def wait_app_idle(window_title: str, timeout: float = 30.0) -> dict:
    """Wait for an application window to become idle and ready for input.

    Args:
        window_title: Title of the window (partial match).
        timeout: Max seconds to wait.
    """
    try:
        return wait_for_idle(window_title, timeout)
    except Exception as e:
        logger.error("Failed waiting for idle: %s", e)
        return _make_error(e, f"wait for idle '{window_title}'")


@mcp.tool()
def wait_text_change(
    window_title: str,
    control_identifier: str,
    current_text: str = "",
    timeout: float = 30.0,
    control_type: Optional[str] = None,
) -> dict:
    """Wait for a control's text content to change.

    Args:
        window_title: Title of the parent window.
        control_identifier: The automation ID or name of the control.
        current_text: Expected current text (captures current if empty).
        timeout: Max seconds to wait.
        control_type: Optional control type filter.
    """
    try:
        return wait_for_text_change(window_title, control_identifier, current_text, timeout, control_type)
    except Exception as e:
        logger.error("Failed waiting for text change: %s", e)
        return _make_error(e, f"wait for text change in '{control_identifier}'")


# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED TOOLS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def element_at_point(x: int, y: int) -> dict:
    """Identify the UI element at specific screen coordinates.

    Useful for discovering what control is at a given point (e.g., after viewing a screenshot).

    Args:
        x: X screen coordinate (pixels from left edge).
        y: Y screen coordinate (pixels from top edge).
    """
    try:
        return get_element_at_point(x, y)
    except Exception as e:
        logger.error("Failed to get element at (%d, %d): %s", x, y, e)
        return _make_error(e, f"get element at ({x}, {y})")


@mcp.tool()
def get_control_props(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
) -> dict:
    """Get all properties of a specific UI control.

    Returns comprehensive info including state, value, toggle state, selection, and bounds.

    Args:
        window_title: Title of the parent window.
        control_identifier: The automation ID, name, or class of the control.
        control_type: Optional control type filter.
    """
    try:
        return get_control_properties(window_title, control_identifier, control_type)
    except Exception as e:
        logger.error("Failed to get properties: %s", e)
        return _make_error(e, f"get properties of '{control_identifier}'")


@mcp.tool()
def tree_expand(
    window_title: str,
    tree_identifier: str,
    item_path: str,
    control_type: Optional[str] = None,
) -> dict:
    """Expand a tree view item by navigating a path.

    Args:
        window_title: Title of the parent window.
        tree_identifier: Identifier of the tree control.
        item_path: Path to item using backslash separator (e.g., 'Root\\Child\\Grandchild').
        control_type: Optional control type (default 'Tree').
    """
    try:
        return expand_tree_item(window_title, tree_identifier, item_path, control_type)
    except Exception as e:
        logger.error("Failed to expand tree item: %s", e)
        return _make_error(e, f"expand tree item '{item_path}'")


@mcp.tool()
def tree_collapse(
    window_title: str,
    tree_identifier: str,
    item_path: str,
    control_type: Optional[str] = None,
) -> dict:
    """Collapse a tree view item.

    Args:
        window_title: Title of the parent window.
        tree_identifier: Identifier of the tree control.
        item_path: Path to item using backslash separator.
        control_type: Optional control type.
    """
    try:
        return collapse_tree_item(window_title, tree_identifier, item_path, control_type)
    except Exception as e:
        logger.error("Failed to collapse tree item: %s", e)
        return _make_error(e, f"collapse tree item '{item_path}'")


@mcp.tool()
def tree_select(
    window_title: str,
    tree_identifier: str,
    item_path: str,
    control_type: Optional[str] = None,
) -> dict:
    """Select (click) a tree view item by navigating a path.

    Args:
        window_title: Title of the parent window.
        tree_identifier: Identifier of the tree control.
        item_path: Path to item using backslash separator.
        control_type: Optional control type.
    """
    try:
        return select_tree_item(window_title, tree_identifier, item_path, control_type)
    except Exception as e:
        logger.error("Failed to select tree item: %s", e)
        return _make_error(e, f"select tree item '{item_path}'")


@mcp.tool()
def read_grid(
    window_title: str,
    grid_identifier: str,
    max_rows: int = 50,
    control_type: Optional[str] = None,
) -> dict:
    """Read data from a data grid or table control.

    Args:
        window_title: Title of the parent window.
        grid_identifier: Identifier of the grid/table control.
        max_rows: Maximum rows to read (default 50).
        control_type: Control type - 'DataGrid', 'Table', or 'List'.
    """
    try:
        return read_datagrid(window_title, grid_identifier, max_rows, control_type)
    except Exception as e:
        logger.error("Failed to read grid: %s", e)
        return _make_error(e, f"read grid '{grid_identifier}'")


@mcp.tool()
def window_info(window_title: str) -> dict:
    """Get comprehensive information about a window.

    Returns state (maximized/minimized), position, process info, and child count.

    Args:
        window_title: Title of the window (partial match).
    """
    try:
        return get_window_info(window_title)
    except Exception as e:
        logger.error("Failed to get window info: %s", e)
        return _make_error(e, f"get window info '{window_title}'")


@mcp.tool()
def windows_by_pid(pid: int) -> list[dict]:
    """Find all windows belonging to a specific process ID.

    Args:
        pid: Process ID to search for.
    """
    try:
        return find_windows_by_pid(pid)
    except Exception as e:
        logger.error("Failed to find windows for PID %d: %s", pid, e)
        return [_make_error(e, f"find windows for PID {pid}")]


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT & STATE READING
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def read_all_text(
    window_title: str,
    max_depth: int = 10,
) -> dict:
    """Read ALL visible text from a window (walks the entire control tree).

    Use this when you want to understand the full content of a window without
    knowing specific control identifiers. Returns all text from labels, edits,
    list items, tree items, etc.

    Args:
        window_title: Title of the target window (partial match).
        max_depth: How deep to search in the control hierarchy (default 10).
    """
    try:
        return get_all_text(window_title, max_depth)
    except Exception as e:
        logger.error("Failed to read all text from '%s': %s", window_title, e)
        return _make_error(e, f"read all text from '{window_title}'")


@mcp.tool()
def control_state(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
) -> dict:
    """Get the current state of a control (enabled, visible, focused, checked, value).

    Use this to verify UI state before or after performing actions.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID, name, or class of the control.
        control_type: Optional control type filter.
    """
    try:
        return get_control_state(window_title, control_identifier, control_type)
    except Exception as e:
        logger.error("Failed to get control state: %s", e)
        return _make_error(e, f"get state of '{control_identifier}'")


@mcp.tool()
def wait_and_click_tool(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    timeout: float = 10.0,
    click_type: str = "left",
) -> dict:
    """Wait for a control to become ready (visible + enabled) then click it.

    Combines waiting and clicking into one reliable operation. Useful for
    buttons that appear after loading, dynamic UI elements, dialog buttons.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID, name, or class of the control.
        control_type: Optional control type filter.
        timeout: Max seconds to wait for the control to be ready (default 10).
        click_type: Mouse button - 'left' or 'right'.
    """
    try:
        return wait_and_click(window_title, control_identifier, control_type, timeout, click_type)
    except Exception as e:
        logger.error("Failed wait_and_click: %s", e)
        return _make_error(e, f"wait and click '{control_identifier}'")


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOUND AUTOMATION OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def type_and_verify(
    window_title: str,
    control_identifier: str,
    text: str,
    control_type: Optional[str] = None,
    clear_first: bool = True,
    timeout: float = 5.0,
) -> dict:
    """Type text into a control and verify it was entered correctly.

    This compound operation:
    1. Focuses the window
    2. Finds and focuses the control
    3. Types the text (with optional clear)
    4. Reads back the control's text
    5. Reports whether verification succeeded

    Use this instead of separate type_text + read_control_text calls.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID, name, or class of the control.
        text: The text to type.
        control_type: Optional type to narrow search (e.g., 'Edit', 'Document').
        clear_first: If True (default), clear existing text before typing.
        timeout: Max seconds for the overall operation.
    """
    try:
        # Type the text
        type_result = type_text(window_title, control_identifier, text, control_type, clear_first, False)

        # Read back and verify
        import time
        time.sleep(0.2)
        read_result = get_control_text(window_title, control_identifier, control_type)
        actual = read_result.get("text", "")

        verified = text in actual or actual.strip() == text.strip()

        return {
            "status": "success",
            "verified": verified,
            "typed_text": text,
            "actual_text": actual[:200],
            "control": type_result.get("control", control_identifier),
            "window_title": type_result.get("window_title", window_title),
        }
    except Exception as e:
        logger.error("type_and_verify failed: %s", e)
        return _make_error(e, f"type_and_verify '{control_identifier}' in '{window_title}'")


@mcp.tool()
def click_and_check(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    expect_dialog: Optional[str] = None,
    expect_window_title_change: bool = False,
) -> dict:
    """Click a control and check what happened (new dialog, title change, etc.).

    This compound operation:
    1. Records current state (window title, focused window)
    2. Clicks the control
    3. Waits briefly for UI to settle
    4. Reports what changed (new dialogs, title changes, new windows)

    Use this for menu clicks, button clicks that trigger navigation, etc.

    Args:
        window_title: Title of the target window.
        control_identifier: The automation ID, name, or class of the control.
        control_type: Optional control type filter.
        expect_dialog: If set, waits for a dialog with this title to appear.
        expect_window_title_change: If True, reports the new window title.
    """
    import time
    from src.automation.windows import get_active_window as _get_active

    try:
        # Record pre-state
        pre_title = ""
        try:
            from src.automation.windows import get_window as _gw
            pre_win = _gw(window_title)
            pre_title = pre_win.wrapper_object().window_text()
        except Exception:
            pass

        # Perform the click
        click_result = click_control(window_title, control_identifier, control_type)

        # Wait for UI to settle
        time.sleep(0.5)

        result = {
            "status": "success",
            "click_result": click_result,
        }

        # Check what changed
        post_active = _get_active()
        if post_active.get("status") == "success":
            result["active_window_after"] = post_active.get("title", "")
            if post_active.get("title", "") != pre_title:
                result["window_changed"] = True
                result["new_window_title"] = post_active.get("title", "")
            else:
                result["window_changed"] = False

        # If expecting a dialog, check for it
        if expect_dialog:
            time.sleep(0.5)
            try:
                from src.automation.windows import get_window as _gw2
                dlg = _gw2(expect_dialog, timeout=3.0)
                result["dialog_appeared"] = True
                result["dialog_title"] = dlg.wrapper_object().window_text()
            except Exception:
                result["dialog_appeared"] = False

        return result
    except Exception as e:
        logger.error("click_and_check failed: %s", e)
        return _make_error(e, f"click_and_check '{control_identifier}' in '{window_title}'")


@mcp.tool()
def find_controls_by_handle(
    window_handle: int,
    control_type: Optional[str] = None,
    name_pattern: Optional[str] = None,
    max_depth: int = 12,
) -> list[dict]:
    """Find controls in a window identified by its handle (HWND).

    Use this when multiple windows share the same title (e.g., multiple 'Untitled - Notepad'
    windows). Get handles from list_windows_tool() output.

    Args:
        window_handle: The window handle (integer) from list_windows_tool.
        control_type: Optional control type filter.
        name_pattern: Optional name/title filter.
        max_depth: Maximum search depth.
    """
    try:
        from src.automation.windows import get_window_by_handle
        from src.automation.controls import _collect_controls
        window = get_window_by_handle(window_handle)
        wrapper = window.wrapper_object()
        results = []
        _collect_controls(wrapper, control_type, name_pattern, results,
                         depth=0, max_depth=max_depth,
                         return_all=not control_type and not name_pattern,
                         max_results=200)
        if len(results) >= 200:
            results.append({
                "name": "[TRUNCATED]",
                "control_type": "",
                "automation_id": "",
                "class_name": "",
                "_metadata": True,
                "_message": "Results limited to 200. Use filters to narrow search.",
            })
        return results
    except Exception as e:
        logger.error("find_controls_by_handle failed: %s", e)
        return [_make_error(e, f"find controls by handle {window_handle}")]


@mcp.tool()
def type_text_by_handle(
    window_handle: int,
    control_identifier: str,
    text: str,
    control_type: Optional[str] = None,
    clear_first: bool = False,
    press_enter: bool = False,
) -> dict:
    """Type text into a control in a window identified by handle.

    Use when multiple windows share the same title.

    Args:
        window_handle: The window handle from list_windows_tool.
        control_identifier: The automation ID, name, or class of the control.
        text: The text to type.
        control_type: Optional control type filter.
        clear_first: Clear existing text first.
        press_enter: Press Enter after typing.
    """
    try:
        from src.automation.windows import get_window_by_handle
        import win32gui
        window = get_window_by_handle(window_handle)
        # Bring window to foreground by handle directly
        from src.automation.utils import bring_window_to_front
        bring_window_to_front(window_handle)
        # Get the title from the handle to pass to type_text
        title = win32gui.GetWindowText(window_handle)
        return type_text(title, control_identifier, text,
                        control_type=control_type, clear_first=clear_first,
                        press_enter=press_enter)
    except Exception as e:
        logger.error("type_text_by_handle failed: %s", e)
        return _make_error(e, f"type text by handle {window_handle}")


@mcp.tool()
def get_text_by_handle(
    window_handle: int,
    control_identifier: str,
    control_type: Optional[str] = None,
) -> dict:
    """Read text from a control in a window identified by handle.

    Use when multiple windows share the same title.

    Args:
        window_handle: The window handle from list_windows_tool.
        control_identifier: The automation ID, name, or class of the control.
        control_type: Optional control type filter.
    """
    try:
        import win32gui
        from src.automation.utils import bring_window_to_front
        bring_window_to_front(window_handle)
        title = win32gui.GetWindowText(window_handle)
        return get_control_text(title, control_identifier, control_type=control_type)
    except Exception as e:
        logger.error("get_text_by_handle failed: %s", e)
        return _make_error(e, f"get text by handle {window_handle}")

