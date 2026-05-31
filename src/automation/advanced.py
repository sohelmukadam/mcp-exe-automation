"""Advanced control operations - tree views, grids, property inspection, and element discovery."""

import logging
import time
from typing import Any, Optional

from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from src.automation.windows import get_window
from src.automation.controls import _find_control

logger = logging.getLogger(__name__)


def get_element_at_point(x: int, y: int, backend: str = "uia") -> dict:
    """Get the UI element at specific screen coordinates.

    This is useful for discovering what control is at a given point,
    for example after seeing a screenshot.

    Args:
        x: X screen coordinate.
        y: Y screen coordinate.
        backend: pywinauto backend ('uia' or 'win32').

    Returns:
        Dict with element info at the specified point.
    """
    try:
        from pywinauto.uia_element_info import UIAElementInfo
        import comtypes.client
        from comtypes import GUID

        # Use UI Automation to find element at point
        iuia = comtypes.client.CreateObject(
            GUID("{ff48dba4-60ef-4201-aa87-54103eef594e}"),
            interface=None,
        )
        # Get IUIAutomation interface
        from ctypes import POINTER, byref
        from comtypes.gen.UIAutomationClient import IUIAutomation, IUIAutomationElement

        uia = iuia.QueryInterface(IUIAutomation)
        from ctypes.wintypes import POINT
        pt = POINT(x, y)
        element = uia.ElementFromPoint(pt)

        if element is None:
            return {"status": "not_found", "message": f"No element at ({x}, {y})"}

        # Extract properties
        name = element.CurrentName or ""
        control_type_id = element.CurrentControlType
        class_name = element.CurrentClassName or ""
        automation_id = element.CurrentAutomationId or ""
        
        # Get bounding rectangle
        rect = element.CurrentBoundingRectangle
        
        # Map control type ID to name
        control_type_map = {
            50000: "Button", 50001: "Calendar", 50002: "CheckBox",
            50003: "ComboBox", 50004: "Edit", 50005: "Hyperlink",
            50006: "Image", 50007: "ListItem", 50008: "List",
            50009: "Menu", 50010: "MenuBar", 50011: "MenuItem",
            50012: "ProgressBar", 50013: "RadioButton", 50014: "ScrollBar",
            50015: "Slider", 50016: "Spinner", 50017: "StatusBar",
            50018: "Tab", 50019: "TabItem", 50020: "Text",
            50021: "ToolBar", 50022: "ToolTip", 50023: "Tree",
            50024: "TreeItem", 50025: "Custom", 50026: "Group",
            50027: "Thumb", 50028: "DataGrid", 50029: "DataItem",
            50030: "Document", 50031: "SplitButton", 50032: "Window",
            50033: "Pane", 50034: "Header", 50035: "HeaderItem",
            50036: "Table", 50037: "TitleBar", 50038: "Separator",
        }
        control_type_name = control_type_map.get(control_type_id, f"Unknown({control_type_id})")

        return {
            "status": "success",
            "name": name,
            "control_type": control_type_name,
            "class_name": class_name,
            "automation_id": automation_id,
            "rectangle": {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
            },
            "point": {"x": x, "y": y},
        }

    except Exception as e:
        # Fallback: use pywinauto Desktop approach
        try:
            desktop = Desktop(backend=backend)
            for win in desktop.windows():
                try:
                    rect = win.rectangle()
                    if rect.left <= x <= rect.right and rect.top <= y <= rect.bottom:
                        # Search children for most specific element
                        best = _find_deepest_at_point(win, x, y)
                        if best:
                            brect = best.rectangle()
                            return {
                                "status": "success",
                                "name": best.window_text() or "",
                                "control_type": best.element_info.control_type or "",
                                "class_name": best.element_info.class_name or "",
                                "automation_id": best.element_info.automation_id or "",
                                "rectangle": {
                                    "left": brect.left,
                                    "top": brect.top,
                                    "right": brect.right,
                                    "bottom": brect.bottom,
                                },
                                "point": {"x": x, "y": y},
                            }
                except Exception:
                    pass
        except Exception:
            pass
        return {"status": "error", "message": f"Failed to find element at ({x}, {y}): {e}"}


def _find_deepest_at_point(control, x: int, y: int, depth: int = 0, max_depth: int = 15):
    """Find the deepest (most specific) control containing the point."""
    if depth >= max_depth:
        return control

    best = control
    try:
        for child in control.children():
            try:
                rect = child.rectangle()
                if rect.left <= x <= rect.right and rect.top <= y <= rect.bottom:
                    deeper = _find_deepest_at_point(child, x, y, depth + 1, max_depth)
                    if deeper:
                        best = deeper
                        break
            except Exception:
                pass
    except Exception:
        pass
    return best


def get_control_properties(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
) -> dict:
    """Get comprehensive properties of a UI control.

    Returns all available properties including state, patterns, and value information.

    Args:
        window_title: Partial title of the parent window.
        control_identifier: Identifier (automation_id, name, or class) of the control.
        control_type: Optional control type filter.

    Returns:
        Dict with all control properties.
    """
    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type)

    props = {
        "name": control.window_text() or "",
        "control_type": control.element_info.control_type or "",
        "class_name": control.element_info.class_name or "",
        "automation_id": control.element_info.automation_id or "",
    }

    # Rectangle
    try:
        rect = control.rectangle()
        props["rectangle"] = {
            "left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom,
            "width": rect.width(), "height": rect.height(),
        }
    except Exception:
        props["rectangle"] = {}

    # States
    try:
        props["is_visible"] = control.is_visible()
    except Exception:
        props["is_visible"] = None

    try:
        props["is_enabled"] = control.is_enabled()
    except Exception:
        props["is_enabled"] = None

    try:
        props["is_focused"] = control.has_focus()
    except Exception:
        props["is_focused"] = None

    # Value (for edit/slider/spinner controls)
    try:
        if hasattr(control, 'get_value'):
            props["value"] = control.get_value()
        elif hasattr(control, 'text_block'):
            props["value"] = control.text_block()
        elif hasattr(control, 'texts'):
            texts = control.texts()
            props["value"] = texts[0] if texts else ""
    except Exception:
        pass

    # Toggle state (for checkboxes, toggle buttons)
    try:
        if hasattr(control, 'get_toggle_state'):
            state = control.get_toggle_state()
            props["toggle_state"] = {0: "unchecked", 1: "checked", 2: "indeterminate"}.get(state, str(state))
    except Exception:
        pass

    # Selection state
    try:
        if hasattr(control, 'is_selected'):
            props["is_selected"] = control.is_selected()
    except Exception:
        pass

    # Children count
    try:
        props["child_count"] = len(control.children())
    except Exception:
        props["child_count"] = 0

    return {"status": "success", "properties": props}


def expand_tree_item(
    window_title: str,
    tree_identifier: str,
    item_path: str,
    control_type: Optional[str] = None,
) -> dict:
    """Expand a tree view item by path.

    Args:
        window_title: Partial title of the parent window.
        tree_identifier: Identifier of the tree control.
        item_path: Path to the item using '\\' as separator (e.g., 'Root\\Child\\Grandchild').
        control_type: Optional control type (default 'Tree').

    Returns:
        Dict with status.
    """
    window = get_window(window_title)
    ct = control_type or "Tree"
    tree = _find_control(window, tree_identifier, ct)

    parts = [p.strip() for p in item_path.split("\\")]
    current = tree

    for part in parts:
        found = False
        try:
            # Search children for matching tree item
            for child in current.children():
                try:
                    child_text = child.window_text() or ""
                    if part.lower() in child_text.lower():
                        # Expand this item
                        try:
                            child.expand()
                        except Exception:
                            try:
                                child.double_click_input()
                            except Exception:
                                pass
                        time.sleep(0.3)
                        current = child
                        found = True
                        break
                except Exception:
                    pass
        except Exception as e:
            return {"status": "error", "message": f"Error navigating tree: {e}"}

        if not found:
            return {"status": "error", "message": f"Tree item '{part}' not found in path '{item_path}'"}

    item_name = current.window_text() if hasattr(current, 'window_text') else item_path
    return {"status": "success", "item": item_name, "action": "expanded"}


def collapse_tree_item(
    window_title: str,
    tree_identifier: str,
    item_path: str,
    control_type: Optional[str] = None,
) -> dict:
    """Collapse a tree view item.

    Args:
        window_title: Parent window title.
        tree_identifier: Identifier of the tree control.
        item_path: Path to the item using '\\' separator.
        control_type: Optional control type.

    Returns:
        Dict with status.
    """
    window = get_window(window_title)
    ct = control_type or "Tree"
    tree = _find_control(window, tree_identifier, ct)

    parts = [p.strip() for p in item_path.split("\\")]
    current = tree

    for part in parts:
        found = False
        for child in current.children():
            try:
                if part.lower() in (child.window_text() or "").lower():
                    current = child
                    found = True
                    break
            except Exception:
                pass
        if not found:
            return {"status": "error", "message": f"Tree item '{part}' not found"}

    try:
        current.collapse()
    except Exception:
        try:
            current.double_click_input()
        except Exception as e:
            return {"status": "error", "message": f"Failed to collapse: {e}"}

    return {"status": "success", "item": current.window_text() or item_path, "action": "collapsed"}


def select_tree_item(
    window_title: str,
    tree_identifier: str,
    item_path: str,
    control_type: Optional[str] = None,
) -> dict:
    """Select (click) a tree view item by path.

    Args:
        window_title: Parent window title.
        tree_identifier: Identifier of the tree control.
        item_path: Path to the item using '\\' separator.
        control_type: Optional control type.

    Returns:
        Dict with status.
    """
    window = get_window(window_title)
    ct = control_type or "Tree"
    tree = _find_control(window, tree_identifier, ct)

    parts = [p.strip() for p in item_path.split("\\")]
    current = tree

    for i, part in enumerate(parts):
        found = False
        for child in current.children():
            try:
                child_text = child.window_text() or ""
                if part.lower() in child_text.lower():
                    if i < len(parts) - 1:
                        # Intermediate nodes: expand
                        try:
                            child.expand()
                        except Exception:
                            pass
                        time.sleep(0.2)
                    current = child
                    found = True
                    break
            except Exception:
                pass
        if not found:
            return {"status": "error", "message": f"Tree item '{part}' not found"}

    # Click the final item
    try:
        current.click_input()
    except Exception as e:
        return {"status": "error", "message": f"Failed to click tree item: {e}"}

    return {"status": "success", "item": current.window_text() or item_path, "action": "selected"}


def read_datagrid(
    window_title: str,
    grid_identifier: str,
    max_rows: int = 50,
    control_type: Optional[str] = None,
) -> dict:
    """Read data from a data grid/table control.

    Args:
        window_title: Partial title of the parent window.
        grid_identifier: Identifier of the grid/table control.
        max_rows: Maximum number of rows to read (default 50).
        control_type: Optional control type (e.g., 'DataGrid', 'Table', 'List').

    Returns:
        Dict with headers and row data.
    """
    window = get_window(window_title)
    ct = control_type or "DataGrid"

    try:
        grid = _find_control(window, grid_identifier, ct)
    except ValueError:
        # Try alternative control types
        for alt_type in ["Table", "List", "DataGrid"]:
            try:
                grid = _find_control(window, grid_identifier, alt_type)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Grid control '{grid_identifier}' not found")

    headers = []
    rows = []

    try:
        # Try to get column headers
        try:
            header_ctrl = grid.child_window(control_type="Header")
            if header_ctrl.exists(timeout=1):
                hw = header_ctrl.wrapper_object()
                for h_child in hw.children():
                    headers.append(h_child.window_text() or "")
        except Exception:
            pass

        # Get row data
        row_count = 0
        for child in grid.children():
            try:
                child_type = child.element_info.control_type or ""
                if child_type in ("DataItem", "ListItem", "Custom"):
                    if row_count >= max_rows:
                        break
                    row_data = []
                    for cell in child.children():
                        cell_text = cell.window_text() or ""
                        row_data.append(cell_text)
                    if row_data:
                        rows.append(row_data)
                        row_count += 1
            except Exception:
                pass

    except Exception as e:
        return {"status": "error", "message": f"Failed to read grid: {e}"}

    return {
        "status": "success",
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
    }


def get_window_info(window_title: str) -> dict:
    """Get comprehensive information about a window.

    Args:
        window_title: Partial window title.

    Returns:
        Dict with window state, position, process info, and child window count.
    """
    import psutil
    window = get_window(window_title)

    info = {
        "title": window.window_text(),
        "handle": window.handle,
        "class_name": window.element_info.class_name or "",
    }

    # Process info
    try:
        pid = window.process_id()
        info["process_id"] = pid
        try:
            proc = psutil.Process(pid)
            info["process_name"] = proc.name()
            info["exe_path"] = proc.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    except Exception:
        pass

    # Window state
    try:
        info["is_maximized"] = window.is_maximized()
    except Exception:
        info["is_maximized"] = None

    try:
        info["is_minimized"] = window.is_minimized()
    except Exception:
        info["is_minimized"] = None

    try:
        info["is_visible"] = window.is_visible()
    except Exception:
        info["is_visible"] = None

    try:
        info["is_enabled"] = window.is_enabled()
    except Exception:
        info["is_enabled"] = None

    try:
        info["has_focus"] = window.has_focus()
    except Exception:
        info["has_focus"] = None

    # Rectangle
    try:
        rect = window.rectangle()
        info["rectangle"] = {
            "left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom,
            "width": rect.width(), "height": rect.height(),
        }
    except Exception:
        info["rectangle"] = {}

    # Child windows count
    try:
        info["child_window_count"] = len(window.children())
    except Exception:
        info["child_window_count"] = 0

    return {"status": "success", "info": info}


def find_windows_by_pid(pid: int) -> list[dict]:
    """Find all windows belonging to a specific process.

    Args:
        pid: Process ID to search for.

    Returns:
        List of window info dicts.
    """
    import win32gui
    import win32process

    windows = []

    def _callback(hwnd, _):
        _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
        if win_pid == pid:
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                rect = win32gui.GetWindowRect(hwnd)
                windows.append({
                    "title": title,
                    "handle": hwnd,
                    "is_visible": bool(win32gui.IsWindowVisible(hwnd)),
                    "is_minimized": bool(win32gui.IsIconic(hwnd)),
                    "rectangle": {
                        "left": rect[0], "top": rect[1],
                        "right": rect[2], "bottom": rect[3],
                    },
                })

    win32gui.EnumWindows(_callback, None)
    return windows
