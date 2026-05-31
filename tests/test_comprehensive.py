"""Comprehensive integration test for MCP Windows Automation.

Tests the automation framework across diverse application types:
- Notepad (Win32 classic)
- Calculator (UWP/WinUI)
- File Explorer (Windows Shell)
- Chrome (Chromium/Electron-like)
- Word (COM/Office - rich document)
- V6 (Delphi/VCL custom app)
- VS Code (Electron)
- Edge (Chromium)

Run: python tests/test_comprehensive.py
"""

import json
import sys
import time
import traceback

sys.path.insert(0, ".")

from src.automation.windows import (
    list_windows, get_window, focus_window, get_control_tree,
    minimize_window, maximize_window, restore_window, move_window,
    resize_window, wait_for_window,
)
from src.automation.controls import (
    find_controls, click_control, type_text, get_control_text,
    scroll_control, get_all_text, get_control_state, wait_and_click,
)
from src.automation.keyboard_mouse import (
    send_keys, send_hotkey, mouse_click, mouse_move,
)
from src.automation.process import list_running_applications
from src.automation.clipboard import get_clipboard_text, set_clipboard_text, clear_clipboard
from src.automation.screenshot import capture_screenshot
from src.automation.advanced import (
    get_element_at_point, get_control_properties, get_window_info,
    find_windows_by_pid,
)

# Test results tracking
_passed = 0
_failed = 0
_errors = []


def _test_result(name, result, expected_status="success"):
    """Record and display a test result."""
    global _passed, _failed
    status = result.get("status") if isinstance(result, dict) else "ok"
    if isinstance(result, list):
        status = "ok" if len(result) > 0 else "empty"

    if status == expected_status or status == "ok":
        _passed += 1
        detail = ""
        if isinstance(result, dict):
            if "text" in result:
                detail = f" -> {repr(result['text'][:60])}"
            elif "title" in result:
                detail = f" -> {result['title'][:50]}"
            elif "total_text" in result:
                detail = f" -> {len(result.get('text_segments', []))} segments"
        elif isinstance(result, list):
            detail = f" -> {len(result)} items"
        print(f"  PASS: {name}{detail}")
    else:
        _failed += 1
        err_msg = result.get("error", result.get("message", str(result))) if isinstance(result, dict) else str(result)
        _errors.append((name, err_msg))
        print(f"  FAIL: {name} -> {err_msg[:80]}")


def _test_exception(name, e):
    """Record a test that threw an exception."""
    global _failed
    _failed += 1
    _errors.append((name, str(e)))
    print(f"  FAIL: {name} -> EXCEPTION: {e}")


def section(title, num):
    """Print a test section header."""
    print(f"\n[{num}] {title}")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TEST SECTIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def test_01_list_apps():
    section("List Running Applications", 1)
    apps = list_running_applications()
    _test_result("list_running_applications", apps)
    for a in apps[:8]:
        name = a.get("name", a.get("exe_name", "?"))
        title = a.get("window_title", a.get("title", "?"))[:55]
        print(f"      {name:25} PID={a['pid']:6} | {title}")
    return apps


def test_02_list_windows():
    section("List Windows (including minimized)", 2)
    windows = list_windows(visible_only=True)
    _test_result("list_windows", windows)
    for w in windows[:10]:
        state = "[min]" if w.get("is_minimized") else "[vis]"
        print(f"      {state} {w['title'][:65]}")


def test_03_focus_and_window_ops():
    section("Window Focus / Minimize / Restore", 3)
    # Test focus on Notepad
    try:
        result = focus_window("Notepad")
        _test_result("focus_window(Notepad)", result)
    except Exception as e:
        _test_exception("focus_window(Notepad)", e)

    time.sleep(0.3)

    # Test minimize/restore cycle
    try:
        result = minimize_window("Notepad")
        _test_result("minimize_window(Notepad)", result)
        time.sleep(0.5)
        result = restore_window("Notepad")
        _test_result("restore_window(Notepad)", result)
    except Exception as e:
        _test_exception("minimize/restore(Notepad)", e)


def test_04_window_info():
    section("Window Info (multiple apps)", 4)
    apps_to_test = ["Notepad", "Calculator", "Chrome", "Word"]
    for app in apps_to_test:
        try:
            result = get_window_info(app)
            _test_result(f"window_info({app})", result)
        except Exception as e:
            _test_exception(f"window_info({app})", e)


def test_05_control_tree():
    section("Control Tree Inspection", 5)
    apps_to_test = ["Notepad", "Calculator", "Chrome"]
    for app in apps_to_test:
        try:
            tree = get_control_tree(app, max_depth=3)
            _test_result(f"get_control_tree({app})", tree)
        except Exception as e:
            _test_exception(f"get_control_tree({app})", e)


def test_06_find_controls():
    section("Find Controls (diverse app types)", 6)
    test_cases = [
        ("Notepad", "Document", None, 12),   # Win11 Notepad uses Document type
        ("Calculator", "Button", None, 12),
        ("Chrome", "Button", None, 12),
        ("Word", "Button", None, 12),
        ("Explorer", "TreeItem", None, 15),   # Explorer needs deeper search
    ]
    for title, ctrl_type, pattern, depth in test_cases:
        try:
            results = find_controls(title, control_type=ctrl_type, name_pattern=pattern, max_depth=depth)
            _test_result(f"find_controls({title}, {ctrl_type})", results)
        except Exception as e:
            _test_exception(f"find_controls({title}, {ctrl_type})", e)


def _get_notepad_edit_id():
    """Determine the correct control identifier for Notepad's text area.
    
    Win11 Notepad uses 'Document' type with class 'RichEditD2DPT'.
    Classic Notepad uses 'Edit' type with class 'Edit'.
    """
    try:
        edits = find_controls("Notepad", control_type="Edit")
        if edits:
            return edits[0].get("automation_id") or edits[0].get("name") or "Edit1", "Edit"
    except Exception:
        pass
    try:
        docs = find_controls("Notepad", control_type="Document")
        if docs:
            aid = docs[0].get("automation_id")
            name = docs[0].get("name")
            cls = docs[0].get("class_name", "")
            return aid or cls or name or "RichEditD2DPT", "Document"
    except Exception:
        pass
    return "Edit1", None


def test_07_notepad_type_and_read():
    """Test typing and reading in Notepad (handles both classic and Win11)."""
    section("Notepad: Type & Read Text", 7)
    test_text = "Hello from MCP automation! Testing 123..."

    try:
        # Focus Notepad
        focus_window("Notepad")
        time.sleep(0.3)

        # Determine correct control identifier
        ctrl_id, ctrl_type = _get_notepad_edit_id()
        print(f"      Using control: id={ctrl_id!r}, type={ctrl_type!r}")

        # Type text
        result = type_text("Notepad", ctrl_id, test_text, control_type=ctrl_type, clear_first=True)
        _test_result("type_text(Notepad)", result)
        time.sleep(0.3)

        # Read text back  
        result = get_control_text("Notepad", ctrl_id, control_type=ctrl_type)
        _test_result("get_control_text(Notepad)", result)
        if test_text in result.get("text", ""):
            print(f"      Text verification: MATCH")
        else:
            print(f"      Text verification: MISMATCH (got: {result.get('text', '')[:50]})")
    except Exception as e:
        _test_exception("notepad_type_and_read", e)


def test_08_calculator_buttons():
    """Test UWP Calculator button interaction."""
    section("Calculator: Button Click (UWP)", 8)
    try:
        focus_window("Calculator")
        time.sleep(0.5)

        # Clear the calculator
        try:
            click_control("Calculator", "Clear", "Button")
            time.sleep(0.2)
        except Exception:
            # Try alternative clear methods
            send_keys("{ESC}", "Calculator")
            time.sleep(0.2)

        # Press buttons: 7 + 3 =
        for btn_name in ["Seven", "Plus", "Three", "Equals"]:
            try:
                click_control("Calculator", btn_name, "Button")
                time.sleep(0.2)
                _test_result(f"click({btn_name})", {"status": "success"})
            except Exception as e:
                # Try by automation_id pattern (num7Button, plusButton, etc.)
                alt_ids = {
                    "Seven": "num7Button", "Plus": "plusButton",
                    "Three": "num3Button", "Equals": "equalButton"
                }
                try:
                    click_control("Calculator", alt_ids.get(btn_name, btn_name), "Button")
                    time.sleep(0.2)
                    _test_result(f"click({btn_name})", {"status": "success"})
                except Exception as e2:
                    _test_exception(f"click({btn_name})", e2)

        # Read the result
        time.sleep(0.3)
        try:
            # Calculator result display has various automation IDs depending on version
            result = get_control_text("Calculator", "CalculatorResults")
            _test_result("calculator_result", result)
            if "10" in result.get("text", ""):
                print(f"      Calculation verification: 7+3=10 CORRECT")
        except Exception:
            try:
                result = get_control_text("Calculator", "Display", "Text")
                _test_result("calculator_result", result)
            except Exception as e:
                _test_exception("calculator_result_read", e)

    except Exception as e:
        _test_exception("calculator_test", e)


def test_09_chrome_url_bar():
    """Test Chrome address bar text reading (Chromium)."""
    section("Chrome: URL Bar Read (Chromium)", 9)
    try:
        focus_window("Chrome")
        time.sleep(0.3)

        # Find Edit controls in Chrome
        edits = find_controls("Chrome", control_type="Edit")
        if edits:
            # The first edit is typically the address bar
            aid = edits[0].get("automation_id", "")
            name = edits[0].get("name", "")
            identifier = aid if aid else name

            result = get_control_text("Chrome", identifier, "Edit")
            _test_result("chrome_url_read", result)
            url = result.get("text", "")
            if url.startswith("http"):
                print(f"      URL: {url[:70]}")
        else:
            _test_exception("chrome_url_read", ValueError("No Edit controls found in Chrome"))
    except Exception as e:
        _test_exception("chrome_url_read", e)


def test_10_word_document():
    """Test Word document reading (Office/Rich Document)."""
    section("Word: Document Text Read (Office)", 10)
    try:
        result = get_control_text("Document", "Body", "Edit")
        _test_result("word_body_text", result)
        text = result.get("text", "")
        if text:
            print(f"      Document content: {repr(text[:60])}")
    except Exception as e:
        _test_exception("word_body_text", e)


def test_11_file_explorer():
    """Test File Explorer interaction (Windows Shell)."""
    section("File Explorer: Navigation (Shell)", 11)
    try:
        focus_window("Explorer")
        time.sleep(0.3)

        # Read all text to understand the window
        result = get_all_text("Explorer", max_depth=6)
        _test_result("explorer_all_text", result)
        segments = result.get("text_segments", [])
        if segments:
            # Show a few items
            for seg in segments[:5]:
                print(f"      [{seg['control_type']}] {seg['text'][:50]}")
    except Exception as e:
        _test_exception("explorer_interaction", e)


def test_12_get_all_text():
    """Test reading all text from various windows."""
    section("Read All Text (multiple apps)", 12)
    apps = ["Notepad", "Calculator"]
    for app in apps:
        try:
            result = get_all_text(app, max_depth=5)
            _test_result(f"get_all_text({app})", result)
            count = len(result.get("text_segments", []))
            print(f"      Found {count} text segments")
        except Exception as e:
            _test_exception(f"get_all_text({app})", e)


def test_13_control_state():
    """Test control state reading."""
    section("Control State Verification", 13)
    try:
        ctrl_id, ctrl_type = _get_notepad_edit_id()
        result = get_control_state("Notepad", ctrl_id, ctrl_type)
        _test_result("control_state(Notepad text area)", result)
        print(f"      visible={result.get('is_visible')}, enabled={result.get('is_enabled')}")
    except Exception as e:
        _test_exception("control_state", e)


def test_14_screenshots():
    """Test screenshot capture across apps."""
    section("Screenshot Capture", 14)
    apps = ["Notepad", "Calculator"]
    for app in apps:
        try:
            result = capture_screenshot(app)
            _test_result(f"screenshot({app})", result)
        except Exception as e:
            _test_exception(f"screenshot({app})", e)


def test_15_keyboard_operations():
    """Test keyboard operations."""
    section("Keyboard Operations", 15)
    try:
        # Send hotkey to Notepad (Ctrl+End to go to end of text)
        result = send_hotkey(["ctrl"], "End", "Notepad")
        _test_result("send_hotkey(Ctrl+End, Notepad)", result)
    except Exception as e:
        _test_exception("keyboard_ops", e)


def test_16_clipboard():
    """Test clipboard operations."""
    section("Clipboard Operations", 16)
    try:
        test_text = "MCP clipboard test 12345"
        set_clipboard_text(test_text)
        time.sleep(0.1)
        result = get_clipboard_text()
        _test_result("clipboard_roundtrip", result)
        if result.get("text") == test_text:
            print(f"      Clipboard verification: MATCH")
        else:
            print(f"      Clipboard verification: MISMATCH")
    except Exception as e:
        _test_exception("clipboard", e)


def test_17_element_at_point():
    """Test element discovery at coordinates."""
    section("Element At Point", 17)
    try:
        result = get_element_at_point(500, 400)
        _test_result("element_at_point(500,400)", result)
        if result.get("status") == "success":
            print(f"      type={result.get('control_type')}, name={result.get('name', '')[:40]}")
    except Exception as e:
        _test_exception("element_at_point", e)


def test_18_find_windows_by_pid():
    """Test finding windows by PID."""
    section("Find Windows By PID", 18)
    try:
        apps = list_running_applications()
        # Pick a multi-window app (Chrome or Edge typically have multiple)
        target = None
        for a in apps:
            if "chrome" in a.get("name", "").lower():
                target = a
                break
        if not target:
            target = apps[0] if apps else None

        if target:
            result = find_windows_by_pid(target["pid"])
            _test_result(f"find_windows_by_pid({target['name']})", result)
    except Exception as e:
        _test_exception("find_windows_by_pid", e)


def test_19_scroll():
    """Test scroll operations."""
    section("Scroll Operations", 19)
    try:
        # Scroll in Notepad (add some text first)
        focus_window("Notepad")
        time.sleep(0.2)
        ctrl_id, ctrl_type = _get_notepad_edit_id()
        # Add multiline text
        long_text = "\n".join(f"Line {i+1}: Testing scroll in notepad" for i in range(30))
        type_text("Notepad", ctrl_id, long_text, control_type=ctrl_type, clear_first=True)
        time.sleep(0.3)

        result = scroll_control("Notepad", ctrl_id, "down", 2, control_type=ctrl_type)
        _test_result("scroll(Notepad, down)", result)
        time.sleep(0.2)
        result = scroll_control("Notepad", ctrl_id, "up", 2, control_type=ctrl_type)
        _test_result("scroll(Notepad, up)", result)
    except Exception as e:
        _test_exception("scroll_operations", e)


def test_20_delphi_v6():
    """Test Delphi V6 application (custom VCL controls)."""
    section("V6/Delphi: Custom App Controls", 20)
    try:
        result = get_window_info("AiQ")
        _test_result("window_info(V6)", result)
    except Exception as e:
        _test_exception("v6_window_info", e)

    try:
        # Find menu items in the Delphi app
        results = find_controls("AiQ", control_type="MenuItem")
        _test_result("find_controls(V6, MenuItem)", results)
    except Exception as e:
        _test_exception("v6_menu_items", e)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MAIN
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def main():
    print("=" * 70)
    print("MCP WINDOWS AUTOMATION - COMPREHENSIVE INTEGRATION TESTS")
    print("=" * 70)
    print(f"Testing across: Notepad, Calculator, Explorer, Chrome, Word, V6, Edge")
    print()

    # Run all tests
    test_01_list_apps()
    test_02_list_windows()
    test_03_focus_and_window_ops()
    test_04_window_info()
    test_05_control_tree()
    test_06_find_controls()
    test_07_notepad_type_and_read()
    test_08_calculator_buttons()
    test_09_chrome_url_bar()
    test_10_word_document()
    test_11_file_explorer()
    test_12_get_all_text()
    test_13_control_state()
    test_14_screenshots()
    test_15_keyboard_operations()
    test_16_clipboard()
    test_17_element_at_point()
    test_18_find_windows_by_pid()
    test_19_scroll()
    test_20_delphi_v6()

    # Summary
    total = _passed + _failed
    print()
    print("=" * 70)
    print(f"RESULTS: {_passed} passed, {_failed} failed, {total} total")
    print("=" * 70)

    if _errors:
        print(f"\nFailed tests:")
        for name, err in _errors:
            print(f"  - {name}: {err[:80]}")

    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
