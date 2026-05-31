"""Menu navigation module - interact with application menus."""

import logging
import time
from typing import Optional

from pywinauto.keyboard import send_keys

from src.automation.windows import get_window

logger = logging.getLogger(__name__)


def click_menu_item(
    window_title: str,
    menu_path: str,
) -> dict:
    """Click a menu item by path (e.g., 'File->Save As' or 'Edit->Find->Find Next').

    Args:
        window_title: Partial title of the parent window.
        menu_path: Menu path using '->' as separator (e.g., 'File->Open').

    Returns:
        Dict with status.
    """
    window = get_window(window_title)

    try:
        # pywinauto menu_select expects the path with -> separators
        window.menu_select(menu_path)
        return {"status": "success", "menu_path": menu_path, "action": "menu_click"}
    except Exception as e:
        logger.warning("menu_select failed for '%s': %s, trying UIA approach", menu_path, e)

    # Fallback: try clicking menu items one by one via UIA
    parts = [p.strip() for p in menu_path.split("->")]
    try:
        for i, part in enumerate(parts):
            if i == 0:
                # Click the top-level menu bar item
                menu_bar = window.child_window(control_type="MenuBar")
                item = menu_bar.child_window(title=part, control_type="MenuItem")
                item.click_input()
            else:
                time.sleep(0.3)
                # Find menu item in the popup
                item = window.child_window(title=part, control_type="MenuItem")
                item.click_input()
            time.sleep(0.2)

        return {"status": "success", "menu_path": menu_path, "action": "menu_click"}
    except Exception as e2:
        raise ValueError(f"Failed to click menu '{menu_path}': {e2}") from e2


def get_menu_items(
    window_title: str,
    menu_name: Optional[str] = None,
) -> dict:
    """Get available menu items from a window's menu bar.

    Args:
        window_title: Partial title of the parent window.
        menu_name: Optional top-level menu to expand and list items from.

    Returns:
        Dict with menu items.
    """
    window = get_window(window_title)
    items = []

    try:
        if menu_name:
            # For custom menu systems (Delphi, etc.), items are descendants even without clicking
            # Strategy 1: Use descendants to find all sub-menu items
            try:
                # Get top-level menu names to exclude them from results
                top_level_names = set()
                try:
                    menu_bar = window.child_window(control_type="MenuBar")
                    for child in menu_bar.wrapper_object().children():
                        if child.element_info.control_type == "MenuItem":
                            top_level_names.add(child.window_text() or "")
                except Exception:
                    pass

                all_menu_items = window.descendants(control_type="MenuItem")
                for mi in all_menu_items:
                    try:
                        name = mi.window_text() or ""
                        if name and name != "-" and name not in top_level_names:
                            items.append({
                                "name": name,
                                "enabled": mi.is_enabled(),
                            })
                    except Exception:
                        pass
            except Exception:
                pass

            # Strategy 2: Click menu and look for popup windows (standard Win32/WPF menus)
            if not items:
                try:
                    menu_bar = window.child_window(control_type="MenuBar")
                    menu_item = menu_bar.child_window(title=menu_name, control_type="MenuItem")
                    menu_item.click_input()
                    time.sleep(0.5)

                    from pywinauto import Desktop
                    desktop = Desktop(backend="uia")
                    for win in desktop.windows():
                        try:
                            ctrl_type = win.element_info.control_type or ""
                            cls_name = win.element_info.class_name or ""
                            if ctrl_type == "Menu" or "menu" in cls_name.lower() or "popup" in cls_name.lower():
                                for child in win.children():
                                    try:
                                        child_type = child.element_info.control_type or ""
                                        if child_type == "MenuItem":
                                            name = child.window_text() or ""
                                            if name and name != "-":
                                                items.append({
                                                    "name": name,
                                                    "enabled": child.is_enabled(),
                                                })
                                    except Exception:
                                        pass
                                if items:
                                    break
                        except Exception:
                            pass

                    send_keys("{ESC}")
                except Exception:
                    send_keys("{ESC}")
        else:
            # List top-level menu items
            try:
                menu_bar = window.child_window(control_type="MenuBar")
                for child in menu_bar.children():
                    if child.element_info.control_type == "MenuItem":
                        items.append({
                            "name": child.window_text(),
                            "enabled": child.is_enabled(),
                        })
            except Exception:
                # Fallback: try accessing menu via pywinauto's menu() method
                try:
                    menu = window.menu()
                    for item in menu.items():
                        items.append({"name": item.text(), "enabled": True})
                except Exception:
                    pass

    except Exception as e:
        send_keys("{ESC}")  # Close any open menu on error
        raise ValueError(f"Failed to get menu items: {e}") from e

    return {"status": "success", "window_title": window_title, "menu_items": items}


def use_context_menu(
    window_title: str,
    control_identifier: str,
    menu_item_text: str,
    control_type: Optional[str] = None,
) -> dict:
    """Right-click a control and select an item from the context menu.

    Args:
        window_title: Parent window title.
        control_identifier: Control to right-click.
        menu_item_text: Text of the context menu item to click.
        control_type: Optional control type.

    Returns:
        Dict with status.
    """
    from src.automation.controls import _find_control

    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type)

    try:
        control.right_click_input()
        time.sleep(0.4)

        # Find and click the context menu item
        # Context menus often appear as top-level popup windows
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for win in desktop.windows():
            try:
                if win.element_info.control_type == "Menu":
                    item = win.child_window(title=menu_item_text, control_type="MenuItem")
                    if item.exists(timeout=2):
                        item.click_input()
                        return {
                            "status": "success",
                            "control": control_identifier,
                            "menu_item": menu_item_text,
                            "action": "context_menu_click",
                        }
            except Exception:
                pass

        # Fallback: try finding it as child of main window
        item = window.child_window(title=menu_item_text, control_type="MenuItem")
        if item.exists(timeout=2):
            item.click_input()
            return {
                "status": "success",
                "control": control_identifier,
                "menu_item": menu_item_text,
                "action": "context_menu_click",
            }

        raise ValueError(f"Context menu item '{menu_item_text}' not found")

    except ValueError:
        raise
    except Exception as e:
        send_keys("{ESC}")  # Close any open menu
        raise ValueError(f"Failed to use context menu: {e}") from e
