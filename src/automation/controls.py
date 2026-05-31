"""Control interaction module - find, click, type, select, scroll controls.

Designed to work reliably with ALL types of Windows desktop applications:
- Modern UWP/WinUI apps (Calculator, Settings, Microsoft Store)
- Win32 legacy apps (Notepad, Paint, Explorer)
- WPF/.NET apps (Visual Studio, Blend)
- Delphi/VCL apps (custom business software)
- Electron/CEF apps (VS Code, Slack, Discord)
- Java/Swing apps (IntelliJ, Eclipse)
- Qt apps (VirtualBox, Wireshark)
- Browser-based (Chrome, Edge, Firefox)
- Office apps (Word, Excel, Outlook)
"""

import logging
import re
import time
from typing import Optional

from pywinauto.keyboard import send_keys

from src.automation.windows import get_window

logger = logging.getLogger(__name__)

# Control classes known to be rich document/content areas that need clipboard-based reading
_RICH_DOCUMENT_CLASSES = frozenset({
    "_WwG", "_WwB", "_WwF",                       # Microsoft Word
    "EXCEL7", "XLDESK",                             # Microsoft Excel
    "_WwN",                                         # Word internal
    "RichEdit20W", "RichEdit20A", "RICHEDIT50W",   # Rich Edit controls
    "Scintilla", "ScintillaW",                      # Scintilla-based editors
    "Chrome_RenderWidgetHostHWND",                  # Chrome/Electron content
    "MozillaWindowClass",                           # Firefox content
    "Internet Explorer_Server",                     # IE/WebBrowser control
    "AfxWnd",                                       # MFC document views
    "Afx:",                                         # MFC variants (prefix match handled separately)
})

# Control types that typically hold document content (not just labels)
_DOCUMENT_CONTROL_TYPES = frozenset({
    "Document", "Edit",
})


def _find_control(
    window,
    control_identifier: str,
    control_type: Optional[str] = None,
    timeout: float = 5.0,
    search_depth: int = 10,
    index: int = 0,
):
    """Locate a control using multiple strategies with robust fallbacks.

    Search order (each with configurable timeout slice):
        1. automation_id exact match (most reliable)
        2. title/name exact match
        3. title/name partial match (contains)
        4. class_name exact match
        5. Descendants walk with flexible matching (handles deep/nested UIs)

    Args:
        window: The parent window wrapper (WindowSpecification or wrapper).
        control_identifier: Identifier to search for (auto_id, name, or class).
        control_type: Optional control type filter (e.g., 'Button', 'Edit').
        timeout: Max seconds to wait for the control.
        search_depth: How deep to search in the control hierarchy.
        index: If multiple controls match, select by 0-based index.

    Returns:
        The matched control wrapper.

    Raises:
        ValueError: If the control cannot be found.
    """
    kwargs: dict = {}
    if control_type:
        kwargs["control_type"] = control_type

    # Compute per-strategy timeouts
    slice_timeout = min(timeout / 4, 2.0)

    # Strategy 1: automation_id (most reliable for modern apps)
    try:
        ctrl = window.child_window(auto_id=control_identifier, found_index=index, **kwargs)
        if ctrl.exists(timeout=slice_timeout):
            return ctrl.wrapper_object()
    except Exception:
        pass

    # Strategy 2: title exact match
    try:
        ctrl = window.child_window(title=control_identifier, found_index=index, **kwargs)
        if ctrl.exists(timeout=slice_timeout):
            return ctrl.wrapper_object()
    except Exception:
        pass

    # Strategy 3: title partial match (regex, case-insensitive)
    try:
        # Escape regex special chars in identifier to avoid regex errors
        escaped_id = re.escape(control_identifier)
        ctrl = window.child_window(title_re=f"(?i).*{escaped_id}.*", found_index=index, **kwargs)
        if ctrl.exists(timeout=slice_timeout):
            return ctrl.wrapper_object()
    except Exception:
        pass

    # Strategy 4: class_name exact match
    try:
        ctrl = window.child_window(class_name=control_identifier, found_index=index, **kwargs)
        if ctrl.exists(timeout=min(slice_timeout, 1.5)):
            return ctrl.wrapper_object()
    except Exception:
        pass

    # Strategy 5: Descendants walk - handles deeply nested UIs, custom controls
    # This is slower but catches controls that child_window misses
    try:
        wrapper = window.wrapper_object() if hasattr(window, 'wrapper_object') else window
        matches = []
        id_lower = control_identifier.lower()

        for desc in wrapper.descendants(depth=search_depth):
            try:
                d_aid = (desc.element_info.automation_id or "").lower()
                d_name = (desc.window_text() or "").lower()
                d_class = (desc.element_info.class_name or "").lower()
                d_type = (desc.element_info.control_type or "").lower()

                # Check type filter
                if control_type and d_type != control_type.lower():
                    continue

                # Match by auto_id, name, or class
                if d_aid == id_lower or d_name == id_lower or d_class == id_lower:
                    matches.append(desc)
                elif id_lower in d_aid or id_lower in d_name:
                    matches.append(desc)
            except Exception:
                continue

        if matches and index < len(matches):
            return matches[index]
    except Exception:
        pass

    raise ValueError(
        f"Control '{control_identifier}' (type={control_type}, index={index}) not found in window. "
        f"Use find_controls_tool to discover available controls."
    )


def find_controls(
    window_title: str,
    control_type: Optional[str] = None,
    name_pattern: Optional[str] = None,
    max_depth: int = 12,
    enabled_only: bool = False,
    visible_only: bool = False,
    max_results: int = 200,
) -> list[dict]:
    """Find all controls matching criteria in a window.

    When no filters are specified (no control_type, no name_pattern), returns ALL
    controls in the window up to max_results. This enables agents to discover
    available controls without needing to know types upfront.

    Args:
        window_title: Partial title of the parent window.
        control_type: Optional control type to filter by (e.g., 'Button', 'Edit').
        name_pattern: Optional name/title pattern to filter by (case-insensitive contains).
        max_depth: Maximum depth to search (default 12 for deeply nested UIs).
        enabled_only: If True, only return enabled controls.
        visible_only: If True, only return visible controls.
        max_results: Maximum number of controls to return (default 200, prevents huge responses).

    Returns:
        List of matching control info dicts with name, type, automation_id, class_name, etc.
        If truncated, includes a '_truncated' key on the last item.
    """
    window = get_window(window_title)
    results = []

    try:
        wrapper = window.wrapper_object()

        # Detect Electron/CEF apps (limited UIA accessibility)
        win_class = wrapper.element_info.class_name or ""
        _electron_classes = {"Chrome_WidgetWin_1", "Chrome_WidgetWin_0",
                            "CefBrowserWindow", "Electron"}
        is_electron = win_class in _electron_classes

        _collect_controls(wrapper, control_type, name_pattern, results,
                         depth=0, max_depth=max_depth,
                         enabled_only=enabled_only, visible_only=visible_only,
                         return_all=not control_type and not name_pattern,
                         max_results=max_results)

        # If Electron app returned very few controls, add guidance
        if is_electron and len(results) < 15 and not control_type:
            results.append({
                "name": "[HINT]",
                "control_type": "",
                "automation_id": "",
                "class_name": "",
                "_metadata": True,
                "_message": (
                    "This appears to be an Electron/CEF app with limited UIA accessibility. "
                    "Try: 1) Use control_type='TabItem' or 'MenuItem' for toolbar items, "
                    "2) Use keyboard shortcuts instead of clicking controls, "
                    "3) Search with a deeper max_depth (e.g., 20), "
                    "4) Use 'Document' type to find the main content area."
                ),
            })
    except Exception as e:
        logger.error("Error finding controls: %s", e)

    # Add truncation warning if results were capped
    if len(results) >= max_results:
        results.append({
            "name": "[TRUNCATED]",
            "control_type": "",
            "automation_id": "",
            "class_name": "",
            "_metadata": True,
            "_message": f"Results limited to {max_results}. Use control_type or name_pattern filters to narrow search, or increase max_results.",
        })

    return results


def _collect_controls(
    control, control_type: Optional[str], name_pattern: Optional[str],
    results: list, depth: int, max_depth: int,
    enabled_only: bool = False, visible_only: bool = False,
    return_all: bool = False, max_results: int = 100,
):
    """Recursively collect controls matching criteria."""
    if depth > max_depth or len(results) >= max_results:
        return

    try:
        ctrl_type = control.element_info.control_type or ""
        ctrl_name = control.window_text() or ""
        auto_id = control.element_info.automation_id or ""
        class_name = control.element_info.class_name or ""

        matches = True
        if control_type and ctrl_type.lower() != control_type.lower():
            matches = False
        if name_pattern and name_pattern.lower() not in ctrl_name.lower():
            if name_pattern.lower() not in auto_id.lower():
                matches = False

        # When return_all is set, include any non-trivial control
        should_include = False
        if return_all:
            # Skip empty Pane/Group wrappers that add no info for the agent
            _skip_types = {"Pane", "Group", "Custom", "Separator", "Thumb", "ScrollBar"}
            if ctrl_type not in _skip_types or ctrl_name or auto_id:
                should_include = True
        elif matches and (control_type or name_pattern):
            should_include = True

        if should_include:
            # Apply additional filters
            if enabled_only:
                try:
                    if not control.is_enabled():
                        should_include = False
                except Exception:
                    pass
            if visible_only:
                try:
                    if not control.is_visible():
                        should_include = False
                except Exception:
                    pass

            if should_include and len(results) < max_results:
                try:
                    rect = control.rectangle()
                    rectangle = {"left": rect.left, "top": rect.top,
                                "right": rect.right, "bottom": rect.bottom,
                                "width": rect.width(), "height": rect.height()}
                except Exception:
                    rectangle = {}

                results.append({
                    "name": ctrl_name,
                    "control_type": ctrl_type,
                    "automation_id": auto_id,
                    "class_name": class_name,
                    "rectangle": rectangle,
                    "is_enabled": control.is_enabled() if hasattr(control, 'is_enabled') else None,
                    "depth": depth,
                })

        for child in control.children():
            _collect_controls(child, control_type, name_pattern, results,
                            depth + 1, max_depth, enabled_only, visible_only,
                            return_all, max_results)
    except Exception:
        pass


def click_control(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    click_type: str = "left",
    double_click: bool = False,
    index: int = 0,
) -> dict:
    """Click a control identified by name or automation_id.

    Uses multiple click strategies to handle different application types:
    1. UIA invoke pattern (fastest, doesn't need focus)
    2. click_input() - simulates mouse at control center
    3. Coordinate-based fallback for stubborn controls

    Args:
        window_title: Partial title of the parent window.
        control_identifier: The automation_id, name, or class of the control.
        control_type: Optional control type to narrow the search.
        click_type: 'left', 'right', or 'middle'.
        double_click: If True, perform a double-click.
        index: If multiple controls match, select by 0-based index.

    Returns:
        Dict with status and action details.
    """
    import win32gui

    logger.info("Clicking control '%s' in window '%s'", control_identifier, window_title)
    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type, index=index)

    # Bring parent window to foreground first (handles background window issues)
    try:
        from src.automation.utils import bring_window_to_front
        win_hwnd = window.wrapper_object().handle
        bring_window_to_front(win_hwnd)
        time.sleep(0.1)
    except Exception:
        try:
            win_hwnd = window.wrapper_object().handle
            win32gui.SetForegroundWindow(win_hwnd)
            time.sleep(0.1)
        except Exception:
            pass

    try:
        # Try set_focus first (works for most controls)
        try:
            control.set_focus()
        except Exception:
            pass

        if double_click:
            control.double_click_input()
        elif click_type == "right":
            control.right_click_input()
        elif click_type == "left":
            # For buttons, try invoke first (most reliable, works even if obscured)
            ctrl_type_lower = (control.element_info.control_type or "").lower()
            if ctrl_type_lower in ("button", "menuitem", "hyperlink", "splitbutton"):
                try:
                    control.invoke()
                    control_name = control.window_text() or control_identifier
                    result = {
                        "status": "success",
                        "control": control_name,
                        "control_type": control.element_info.control_type or "",
                        "action": "invoke",
                    }
                    try:
                        result["window_title"] = window.wrapper_object().window_text()
                    except Exception:
                        pass
                    return result
                except Exception:
                    pass
            control.click_input()
        else:
            control.click_input(button=click_type)

    except Exception as e:
        # Fallback: click by coordinates
        try:
            rect = control.rectangle()
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            from pywinauto.mouse import click as _mouse_click
            if double_click:
                from pywinauto.mouse import double_click as _dbl
                _dbl(coords=(cx, cy))
            elif click_type == "right":
                from pywinauto.mouse import right_click as _rclick
                _rclick(coords=(cx, cy))
            else:
                _mouse_click(coords=(cx, cy))
        except Exception as e2:
            logger.error("Failed to click control '%s': %s (fallback: %s)", control_identifier, e, e2)
            raise ValueError(f"Failed to click control '{control_identifier}': {e}") from e

    control_name = control.window_text() or control_identifier
    logger.info("Successfully clicked '%s'", control_name)

    # Post-action verification: check if anything changed (window title, new dialog, etc.)
    result = {
        "status": "success",
        "control": control_name,
        "control_type": control.element_info.control_type or "",
        "action": "double_click" if double_click else f"{click_type}_click",
    }

    # Check if the window title changed (indicates navigation/state change)
    try:
        new_title = window.wrapper_object().window_text()
        result["window_title"] = new_title
    except Exception:
        pass

    return result


def type_text(
    window_title: str,
    control_identifier: str,
    text: str,
    control_type: Optional[str] = None,
    clear_first: bool = False,
    press_enter: bool = False,
    index: int = 0,
) -> dict:
    """Type text into a control with multiple strategy fallbacks.

    Strategies tried in order:
    1. set_edit_text() - direct text setting via UIA ValuePattern
    2. type_keys() - simulated typing via UIA
    3. Clipboard paste (Ctrl+V) - works for rich edit controls

    Args:
        window_title: Partial title of the parent window.
        control_identifier: The automation_id, name, or class of the control.
        text: The text to type.
        control_type: Optional control type to narrow the search.
        clear_first: If True, clear existing text before typing (Ctrl+A then type).
        press_enter: If True, press Enter after typing.
        index: If multiple controls match, select by 0-based index.

    Returns:
        Dict with status and action details.

    Raises:
        ValueError: If the control is non-editable (MenuItem, Header, etc.).
    """
    import win32gui
    from src.automation.utils import safe_clipboard_set

    logger.info("Typing into control '%s' in window '%s'", control_identifier, window_title)
    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type, index=index)

    # Validate: reject typing into non-editable control types
    ctrl_type = (control.element_info.control_type or "").lower()
    _non_editable_types = frozenset({
        "menuitem", "menu", "menubar", "header", "headeritem",
        "separator", "thumb", "scrollbar", "titlebar", "image",
        "progressbar", "tooltip", "statusbar",
    })
    if ctrl_type in _non_editable_types:
        raise ValueError(
            f"Cannot type into a '{control.element_info.control_type}' control "
            f"('{control_identifier}'). Only Edit, Document, ComboBox, and similar "
            f"editable controls accept text input."
        )

    # Bring window to foreground
    try:
        from src.automation.utils import bring_window_to_front
        win_hwnd = window.wrapper_object().handle
        bring_window_to_front(win_hwnd)
        time.sleep(0.15)
    except Exception:
        try:
            win_hwnd = window.wrapper_object().handle
            win32gui.SetForegroundWindow(win_hwnd)
            time.sleep(0.15)
        except Exception:
            pass

    try:
        try:
            control.set_focus()
        except Exception:
            pass
        time.sleep(0.15)

        if clear_first:
            send_keys("^a", pause=0.05)
            time.sleep(0.1)
            send_keys("{DELETE}", pause=0.05)
            time.sleep(0.1)

        typed = False

        # Strategy 1: set_edit_text (most reliable for simple edit controls)
        # Skip for RichEdit controls where it often doesn't work
        ctrl_class = control.element_info.class_name or ""
        is_rich = _is_rich_document_control(ctrl_type, ctrl_class,
                                             control.element_info.automation_id or "")
        if hasattr(control, 'set_edit_text') and not press_enter and not is_rich:
            try:
                control.set_edit_text(text)
                typed = True
            except Exception:
                pass

        # Strategy 2: Clipboard paste (handles special chars, rich edit, Word docs)
        # Preferred over type_keys for text containing special characters
        if not typed:
            try:
                safe_clipboard_set(text)
                time.sleep(0.05)
                send_keys("^v", pause=0.05)
                time.sleep(0.1)
                typed = True
            except Exception:
                pass

        # Strategy 3: type_keys (simulated keystrokes via UIA)
        # Last resort - doesn't handle special chars well
        if not typed:
            try:
                escaped = text.replace("{", "{{").replace("}", "}}")
                control.type_keys(escaped, with_spaces=True)
                typed = True
            except Exception:
                pass

        if not typed:
            raise RuntimeError("All typing strategies failed")

        if press_enter:
            time.sleep(0.05)
            send_keys("{ENTER}", pause=0.05)

    except Exception as e:
        logger.error("Failed to type into control '%s': %s", control_identifier, e)
        raise ValueError(f"Failed to type into control '{control_identifier}': {e}") from e

    control_name = control.window_text() or control_identifier
    logger.info("Successfully typed into '%s'", control_name)

    result = {
        "status": "success",
        "control": control_name,
        "action": "type",
        "text_length": len(text),
    }

    # Verification: try to read back what was typed (best-effort)
    try:
        time.sleep(0.2)
        read_back = ""

        # For rich document controls, use clipboard-based verification
        ctrl_class_v = control.element_info.class_name or ""
        ctrl_type_v = control.element_info.control_type or ""
        auto_id_v = control.element_info.automation_id or ""
        is_rich_v = _is_rich_document_control(ctrl_type_v, ctrl_class_v, auto_id_v)

        if not is_rich_v:
            if hasattr(control, 'get_value'):
                try:
                    read_back = control.get_value() or ""
                except Exception:
                    pass
            if not read_back and hasattr(control, 'texts'):
                try:
                    texts = control.texts()
                    read_back = texts[0] if texts else ""
                except Exception:
                    pass

        # Fallback for RichEdit or when above failed: clipboard read
        if not read_back:
            try:
                from src.automation.utils import safe_clipboard_get, safe_clipboard_clear
                safe_clipboard_clear()
                send_keys("^a", pause=0.05)
                time.sleep(0.1)
                send_keys("^c", pause=0.05)
                time.sleep(0.15)
                read_back = safe_clipboard_get() or ""
                # Deselect
                send_keys("{END}", pause=0.02)
            except Exception:
                pass

        if read_back:
            # Report whether the typed text appears in the control
            if text in read_back or read_back.endswith(text):
                result["verified"] = True
            else:
                result["verified"] = False
                result["actual_text_preview"] = read_back[:100]
    except Exception:
        pass

    # Report the new window title (may have changed, e.g., * prefix for unsaved)
    try:
        result["window_title"] = window.wrapper_object().window_text()
    except Exception:
        pass

    return result


def _is_rich_document_control(ctrl_type: str, ctrl_class: str, auto_id: str) -> bool:
    """Determine if a control is a rich document that needs clipboard-based reading."""
    # Direct class match
    if ctrl_class in _RICH_DOCUMENT_CLASSES:
        return True
    # Prefix match for MFC classes (Afx:...)
    if ctrl_class.startswith("Afx:"):
        return True
    # Document control type
    if ctrl_type == "Document":
        return True
    # Edit controls with empty class (Word's body control)
    if ctrl_type == "Edit" and not ctrl_class:
        return True
    # Controls with known document-area automation IDs
    if auto_id.lower() in ("body", "content", "editor", "document"):
        return True
    return False


def get_control_text(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    index: int = 0,
    use_clipboard: Optional[bool] = None,
) -> dict:
    """Read text from a control using multiple strategies.

    Strategies (in priority order for standard controls):
    1. get_value() - UIA Value pattern (edit boxes, combo boxes)
    2. texts() - pywinauto's text collection
    3. text_block() - rich text controls
    4. Clipboard approach (Ctrl+A, Ctrl+C) - rich documents, embedded content
    5. window_text() - fallback to control name/title

    For rich document controls (Word, Excel, Browsers), clipboard is used first.

    Args:
        window_title: Partial title of the parent window.
        control_identifier: The automation_id, name, or class of the control.
        control_type: Optional control type filter.
        index: If multiple controls match, select by 0-based index.
        use_clipboard: Force clipboard strategy (True) or skip it (False). Auto-detect if None.

    Returns:
        Dict with the control's text content.
    """
    import win32gui

    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type, index=index)

    text = ""
    control_name = control.window_text() or ""
    ctrl_class = control.element_info.class_name or ""
    ctrl_type = control.element_info.control_type or ""
    auto_id = control.element_info.automation_id or ""

    is_rich_document = _is_rich_document_control(ctrl_type, ctrl_class, auto_id)
    if use_clipboard is not None:
        is_rich_document = use_clipboard

    try:
        if not is_rich_document:
            # Strategy 1: get_value() - UIA Value pattern (most reliable for edits)
            if hasattr(control, 'get_value'):
                try:
                    val = control.get_value()
                    if val:
                        text = val
                except Exception:
                    pass

            # Strategy 2: texts() method - returns list of text values
            if not text and hasattr(control, 'texts'):
                try:
                    texts = control.texts()
                    if texts:
                        # Filter out the control name which is often duplicated
                        content = [t for t in texts if t and t != control_name]
                        text = content[0] if content else (texts[0] if texts[0] else "")
                except Exception:
                    pass

            # Strategy 3: text_block() for rich edit controls
            if not text and hasattr(control, 'text_block'):
                try:
                    text = control.text_block() or ""
                except Exception:
                    pass

            # Strategy 4: Legacy win32 WM_GETTEXT for win32 controls
            if not text:
                try:
                    import ctypes
                    hwnd = control.handle if hasattr(control, 'handle') else None
                    if hwnd:
                        length = ctypes.windll.user32.SendMessageW(hwnd, 0x000E, 0, 0)  # WM_GETTEXTLENGTH
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            ctypes.windll.user32.SendMessageW(hwnd, 0x000D, length + 1, buf)  # WM_GETTEXT
                            if buf.value and buf.value != control_name:
                                text = buf.value
                except Exception:
                    pass

        # Strategy 5: Use clipboard to get text (select all + copy)
        # Used as primary for document controls, fallback for others
        if not text or is_rich_document:
            try:
                from src.automation.utils import safe_clipboard_get, safe_clipboard_set, safe_clipboard_clear, bring_window_to_front

                # Save existing clipboard content
                old_clip = safe_clipboard_get()

                # Clear clipboard to detect if copy works
                safe_clipboard_clear()

                # Bring parent window to foreground robustly
                try:
                    win_hwnd = window.wrapper_object().handle
                    bring_window_to_front(win_hwnd)
                except Exception:
                    try:
                        win32gui.SetForegroundWindow(window.wrapper_object().handle)
                    except Exception:
                        pass
                time.sleep(0.25)

                # Now focus the specific control within the window
                try:
                    control.set_focus()
                except Exception:
                    pass
                time.sleep(0.15)

                send_keys("^a", pause=0.05)
                time.sleep(0.15)
                send_keys("^c", pause=0.05)
                time.sleep(0.3)

                clip_text = safe_clipboard_get()
                if clip_text:
                    text = clip_text

                # Deselect to leave control in clean state
                try:
                    send_keys("{END}", pause=0.02)
                except Exception:
                    pass

                # Restore original clipboard (best effort)
                if old_clip and old_clip != text:
                    safe_clipboard_set(old_clip)

            except Exception:
                pass

        # Strategy 6: window_text() fallback
        if not text:
            text = control_name

    except Exception as e:
        logger.error("Failed to get text from '%s': %s", control_identifier, e)
        raise ValueError(f"Failed to get text from '{control_identifier}': {e}") from e

    return {"status": "success", "control": control_identifier, "text": text}


def select_combobox_item(
    window_title: str,
    control_identifier: str,
    item_text: str,
    control_type: Optional[str] = None,
) -> dict:
    """Select an item in a combobox/dropdown by text.

    Args:
        window_title: Partial title of the parent window.
        control_identifier: Identifier of the combobox control.
        item_text: The text of the item to select.
        control_type: Optional control type (defaults to 'ComboBox').

    Returns:
        Dict with status.
    """
    window = get_window(window_title)
    ct = control_type or "ComboBox"
    control = _find_control(window, control_identifier, ct)

    try:
        control.select(item_text)
    except Exception:
        # Fallback: try expanding and clicking the item
        try:
            control.click_input()
            time.sleep(0.3)
            send_keys(item_text, with_spaces=True)
            send_keys("{ENTER}")
        except Exception as e:
            raise ValueError(f"Failed to select '{item_text}' in combobox: {e}") from e

    return {"status": "success", "control": control_identifier, "selected": item_text}


def check_checkbox(
    window_title: str,
    control_identifier: str,
    check: bool = True,
    control_type: Optional[str] = None,
) -> dict:
    """Check or uncheck a checkbox control.

    Args:
        window_title: Partial title of the parent window.
        control_identifier: Identifier of the checkbox.
        check: True to check, False to uncheck.
        control_type: Optional control type.

    Returns:
        Dict with status.
    """
    window = get_window(window_title)
    ct = control_type or "CheckBox"
    control = _find_control(window, control_identifier, ct)

    try:
        if check:
            control.check()
        else:
            control.uncheck()
    except Exception:
        # Fallback: click if check/uncheck not available
        try:
            current_state = control.get_toggle_state()
            should_click = (check and current_state == 0) or (not check and current_state == 1)
            if should_click:
                control.click_input()
        except Exception as e:
            raise ValueError(f"Failed to {'check' if check else 'uncheck'} control: {e}") from e

    return {"status": "success", "control": control_identifier, "checked": check}


def select_listbox_item(
    window_title: str,
    control_identifier: str,
    item_text: str,
    control_type: Optional[str] = None,
) -> dict:
    """Select an item in a listbox by text.

    Args:
        window_title: Parent window title.
        control_identifier: Identifier of the listbox.
        item_text: Text of the item to select.
        control_type: Optional control type.

    Returns:
        Dict with status.
    """
    window = get_window(window_title)
    ct = control_type or "List"
    control = _find_control(window, control_identifier, ct)

    try:
        control.select(item_text)
    except Exception as e:
        raise ValueError(f"Failed to select '{item_text}' in listbox: {e}") from e

    return {"status": "success", "control": control_identifier, "selected": item_text}


def select_tab(
    window_title: str,
    control_identifier: str,
    tab_name: str,
    control_type: Optional[str] = None,
) -> dict:
    """Select a tab in a tab control.

    Args:
        window_title: Parent window title.
        control_identifier: Identifier of the tab control.
        tab_name: Name/text of the tab to select.
        control_type: Optional control type.

    Returns:
        Dict with status.
    """
    window = get_window(window_title)
    ct = control_type or "Tab"
    control = _find_control(window, control_identifier, ct)

    try:
        control.select(tab_name)
    except Exception as e:
        raise ValueError(f"Failed to select tab '{tab_name}': {e}") from e

    return {"status": "success", "control": control_identifier, "selected_tab": tab_name}


def scroll_control(
    window_title: str,
    control_identifier: str,
    direction: str = "down",
    amount: int = 3,
    control_type: Optional[str] = None,
) -> dict:
    """Scroll a control using multiple strategies.

    Strategies:
    1. UIA ScrollPattern (most reliable for grids, lists, panels)
    2. Mouse wheel simulation (works for most scrollable areas)
    3. Keyboard-based scrolling (Page Up/Down, arrow keys)

    Args:
        window_title: Parent window title.
        control_identifier: Identifier of the control to scroll.
        direction: 'up', 'down', 'left', or 'right'.
        amount: Number of scroll units (e.g., mouse wheel clicks or page scrolls).
        control_type: Optional control type.

    Returns:
        Dict with status.
    """
    import win32gui

    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type)

    # Bring window to foreground
    try:
        win_hwnd = window.wrapper_object().handle
        win32gui.SetForegroundWindow(win_hwnd)
        time.sleep(0.1)
    except Exception:
        pass

    scrolled = False

    # Strategy 1: UIA ScrollPattern
    try:
        if direction == "down":
            control.scroll("down", "page", amount)
        elif direction == "up":
            control.scroll("up", "page", amount)
        elif direction == "left":
            control.scroll("left", "page", amount)
        elif direction == "right":
            control.scroll("right", "page", amount)
        scrolled = True
    except Exception:
        pass

    # Strategy 2: Mouse wheel at control center
    if not scrolled:
        try:
            try:
                control.set_focus()
            except Exception:
                pass
            rect = control.rectangle()
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            from pywinauto.mouse import scroll as _mouse_scroll, move as _mouse_move
            _mouse_move(coords=(cx, cy))
            time.sleep(0.05)
            if direction in ("down", "up"):
                clicks = -amount if direction == "down" else amount
                _mouse_scroll(coords=(cx, cy), wheel_dist=clicks)
            elif direction in ("left", "right"):
                # Horizontal scroll via Shift+wheel
                import ctypes
                ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)  # Shift down
                clicks = -amount if direction == "right" else amount
                _mouse_scroll(coords=(cx, cy), wheel_dist=clicks)
                ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)  # Shift up
            scrolled = True
        except Exception:
            pass

    # Strategy 3: Keyboard-based scrolling
    if not scrolled:
        try:
            try:
                control.set_focus()
            except Exception:
                pass
            time.sleep(0.1)
            key_map = {"down": "{PGDN}", "up": "{PGUP}", "left": "{LEFT}", "right": "{RIGHT}"}
            key = key_map.get(direction, "{PGDN}")
            for _ in range(amount):
                send_keys(key, pause=0.05)
                time.sleep(0.05)
            scrolled = True
        except Exception as e:
            raise ValueError(f"Failed to scroll: {e}") from e

    return {"status": "success", "control": control_identifier, "direction": direction, "amount": amount}


def get_all_text(
    window_title: str,
    max_depth: int = 10,
    include_invisible: bool = False,
) -> dict:
    """Read ALL visible text from a window by walking its control tree.

    This is useful for understanding the full content of a window without
    knowing specific control identifiers. Collects text from all Text,
    Edit, Document, and other readable controls.

    Args:
        window_title: Partial title of the parent window.
        max_depth: Maximum depth to search (default 10).
        include_invisible: If True, include text from invisible controls.

    Returns:
        Dict with collected text segments and control info.
    """
    window = get_window(window_title)
    texts = []

    try:
        wrapper = window.wrapper_object()
        _collect_text(wrapper, texts, depth=0, max_depth=max_depth,
                     include_invisible=include_invisible)
    except Exception as e:
        logger.error("Error collecting text from '%s': %s", window_title, e)

    return {
        "status": "success",
        "window_title": window_title,
        "text_segments": texts,
        "total_text": "\n".join(t["text"] for t in texts if t["text"]),
    }


def _collect_text(
    control, texts: list, depth: int, max_depth: int, include_invisible: bool
):
    """Recursively collect text from all readable controls."""
    if depth > max_depth:
        return

    try:
        # Skip invisible controls unless requested
        if not include_invisible:
            try:
                if not control.is_visible():
                    return
            except Exception:
                pass

        ctrl_type = control.element_info.control_type or ""
        ctrl_name = control.window_text() or ""

        # Collect text from readable control types
        readable_types = {"Text", "Edit", "Document", "Hyperlink", "StatusBar",
                         "ListItem", "TreeItem", "DataItem", "MenuItem", "TabItem",
                         "Header", "HeaderItem"}

        if ctrl_type in readable_types and ctrl_name.strip():
            texts.append({
                "text": ctrl_name.strip(),
                "control_type": ctrl_type,
                "automation_id": control.element_info.automation_id or "",
                "depth": depth,
            })

        # Recurse into children
        for child in control.children():
            _collect_text(child, texts, depth + 1, max_depth, include_invisible)
    except Exception:
        pass


def get_control_state(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    index: int = 0,
) -> dict:
    """Get the current state of a control (enabled, visible, focused, checked, etc.).

    Useful for verifying UI state before/after actions.

    Args:
        window_title: Partial title of the parent window.
        control_identifier: The automation_id, name, or class of the control.
        control_type: Optional control type filter.
        index: If multiple controls match, select by 0-based index.

    Returns:
        Dict with comprehensive control state information.
    """
    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type, index=index)

    state = {
        "name": control.window_text() or "",
        "control_type": control.element_info.control_type or "",
        "automation_id": control.element_info.automation_id or "",
        "class_name": control.element_info.class_name or "",
    }

    # Visibility & enabled
    try:
        state["is_visible"] = control.is_visible()
    except Exception:
        state["is_visible"] = None
    try:
        state["is_enabled"] = control.is_enabled()
    except Exception:
        state["is_enabled"] = None
    try:
        state["has_focus"] = control.has_focus()
    except Exception:
        state["has_focus"] = None

    # Toggle/check state
    try:
        if hasattr(control, 'get_toggle_state'):
            ts = control.get_toggle_state()
            state["toggle_state"] = {0: "unchecked", 1: "checked", 2: "indeterminate"}.get(ts, str(ts))
    except Exception:
        pass

    # Selection state
    try:
        if hasattr(control, 'is_selected'):
            state["is_selected"] = control.is_selected()
    except Exception:
        pass

    # Value (for sliders, progress bars, etc.)
    try:
        if hasattr(control, 'get_value'):
            state["value"] = control.get_value()
    except Exception:
        pass

    # Bounding rectangle
    try:
        rect = control.rectangle()
        state["rectangle"] = {
            "left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom,
            "width": rect.width(), "height": rect.height(),
        }
    except Exception:
        pass

    return {"status": "success", **state}


def wait_and_click(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    timeout: float = 10.0,
    click_type: str = "left",
    index: int = 0,
) -> dict:
    """Wait for a control to become ready (visible + enabled) then click it.

    Combines wait_for_control and click_control into one reliable operation.
    Useful for buttons that appear after loading, dialog buttons, etc.

    Args:
        window_title: Partial title of the parent window.
        control_identifier: The automation_id, name, or class of the control.
        control_type: Optional control type filter.
        timeout: Max seconds to wait for the control to be ready.
        click_type: 'left', 'right', or 'middle'.
        index: If multiple controls match, select by 0-based index.

    Returns:
        Dict with status.
    """
    import win32gui

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            window = get_window(window_title, timeout=2.0)
            control = _find_control(window, control_identifier, control_type,
                                   timeout=1.0, index=index)
            # Check if ready
            if control.is_visible() and control.is_enabled():
                # Bring to foreground and click
                try:
                    win_hwnd = window.wrapper_object().handle
                    win32gui.SetForegroundWindow(win_hwnd)
                    time.sleep(0.1)
                except Exception:
                    pass

                try:
                    control.set_focus()
                except Exception:
                    pass

                if click_type == "right":
                    control.right_click_input()
                else:
                    # Try invoke first for buttons
                    ctrl_t = (control.element_info.control_type or "").lower()
                    if ctrl_t in ("button", "menuitem", "hyperlink"):
                        try:
                            control.invoke()
                            return {"status": "success", "control": control_identifier, "action": "invoke"}
                        except Exception:
                            pass
                    control.click_input()
                return {"status": "success", "control": control_identifier, "action": f"{click_type}_click"}
        except Exception:
            pass
        time.sleep(0.5)

    raise ValueError(
        f"Control '{control_identifier}' did not become ready within {timeout}s"
    )
