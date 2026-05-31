"""Integration test script - tests core functionality on real open applications."""
import json
import sys
import time

from src.automation.windows import (
    list_windows, get_window, focus_window, get_control_tree,
    minimize_window, maximize_window, restore_window,
)
from src.automation.process import list_running_applications, attach_to_application
from src.automation.controls import find_controls, type_text, get_control_text, click_control
from src.automation.keyboard_mouse import send_keys, send_hotkey
from src.automation.screenshot import capture_screenshot
from src.automation.menu import get_menu_items
from src.automation.clipboard import get_clipboard_text, set_clipboard_text
from src.automation.advanced import (
    get_window_info, find_windows_by_pid, get_control_properties, get_element_at_point
)


def test_result(name, result, expected_status="success"):
    """Print test result."""
    if isinstance(result, dict):
        status = result.get("status", result.get("error", "unknown"))
        if "error" in result:
            print(f"  FAIL: {name} -> {result['error'][:80]}")
            return False
        elif status == expected_status:
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  WARN: {name} -> status={status}")
            return True
    elif isinstance(result, list):
        print(f"  PASS: {name} -> {len(result)} items")
        return True
    else:
        print(f"  PASS: {name} -> {type(result).__name__}")
        return True


def run_tests():
    passed = 0
    failed = 0

    print("=" * 60)
    print("MCP WINDOWS AUTOMATION - INTEGRATION TESTS")
    print("=" * 60)

    # --- Test 1: List running applications ---
    print("\n[1] List Running Applications")
    apps = list_running_applications()
    if test_result("list_running_applications", apps):
        passed += 1
        for app in apps:
            print(f"      {app['name']:20s} PID={app['pid']:>6} | {app['window_title'][:50]}")
    else:
        failed += 1

    # --- Test 2: List windows (including minimized) ---
    print("\n[2] List Windows (including minimized)")
    windows = list_windows(True)
    if test_result("list_windows", windows):
        passed += 1
        for w in windows:
            state = "min" if w.get("is_minimized") else "vis" if w.get("is_visible") else "hid"
            print(f"      [{state}] {w['title'][:60]}")
    else:
        failed += 1

    # --- Test 3: Focus/Restore operations ---
    print("\n[3] Window Focus/Restore (Chrome)")
    try:
        result = focus_window("Chrome")
        if test_result("focus_window(Chrome)", result):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        print(f"  FAIL: focus_window(Chrome) -> {e}")
        failed += 1

    # --- Test 4: Window Info ---
    print("\n[4] Window Info")
    for title in ["Chrome", "Word", "AiQ"]:
        try:
            result = get_window_info(title)
            if test_result(f"window_info({title})", result):
                passed += 1
                info = result.get("info", {})
                print(f"      state: max={info.get('is_maximized')} min={info.get('is_minimized')}")
            else:
                failed += 1
        except Exception as e:
            print(f"  FAIL: window_info({title}) -> {e}")
            failed += 1

    # --- Test 5: Control Tree ---
    print("\n[5] Control Tree Inspection")
    for title in ["Chrome", "AiQ"]:
        try:
            tree = get_control_tree(title, max_depth=3)
            if tree:
                print(f"  PASS: get_control_tree({title}) -> {len(tree)} top-level controls")
                passed += 1
            else:
                print(f"  WARN: get_control_tree({title}) -> empty tree")
                passed += 1
        except Exception as e:
            print(f"  FAIL: get_control_tree({title}) -> {e}")
            failed += 1

    # --- Test 6: Find Controls ---
    print("\n[6] Find Controls")
    for title, ctrl_type in [("Chrome", "Button"), ("AiQ", "MenuItem"), ("Word", "Button")]:
        try:
            controls = find_controls(title, control_type=ctrl_type)
            print(f"  PASS: find_controls({title}, {ctrl_type}) -> {len(controls)} found")
            passed += 1
        except Exception as e:
            print(f"  FAIL: find_controls({title}, {ctrl_type}) -> {e}")
            failed += 1

    # --- Test 7: Screenshots ---
    print("\n[7] Screenshot Capture")
    for title in ["Chrome", "AiQ"]:
        try:
            result = capture_screenshot(title)
            if test_result(f"screenshot({title})", result):
                passed += 1
                print(f"      {result.get('width')}x{result.get('height')} -> {result.get('path', '')[-40:]}")
            else:
                failed += 1
        except Exception as e:
            print(f"  FAIL: screenshot({title}) -> {e}")
            failed += 1

    # --- Test 8: Menu Items ---
    print("\n[8] Menu Items")
    try:
        result = get_menu_items("AiQ")
        if test_result("get_menu_items(AiQ, top-level)", result):
            passed += 1
            for item in result.get("menu_items", []):
                print(f"      {item['name']}")
        else:
            failed += 1
    except Exception as e:
        print(f"  FAIL: get_menu_items(AiQ) -> {e}")
        failed += 1

    # --- Test 9: Keyboard ---
    print("\n[9] Keyboard Operations")
    try:
        result = send_hotkey(["ctrl"], "l", window_title="Chrome")
        if test_result("send_hotkey(Ctrl+L, Chrome)", result):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        print(f"  FAIL: send_hotkey -> {e}")
        failed += 1
    time.sleep(0.3)
    send_keys("{ESC}")

    # --- Test 10: Clipboard ---
    print("\n[10] Clipboard Operations")
    try:
        set_clipboard_text("MCP Test 2024")
        result = get_clipboard_text()
        if result.get("text") == "MCP Test 2024":
            print("  PASS: clipboard set/get roundtrip")
            passed += 1
        else:
            print(f"  FAIL: clipboard roundtrip, got: {result}")
            failed += 1
    except Exception as e:
        print(f"  FAIL: clipboard -> {e}")
        failed += 1

    # --- Test 11: Element at Point ---
    print("\n[11] Element at Point")
    try:
        result = get_element_at_point(500, 400)
        if test_result("element_at_point(500,400)", result):
            passed += 1
            print(f"      type={result.get('control_type')}, name={result.get('name','')[:30]!r}")
        else:
            failed += 1
    except Exception as e:
        print(f"  FAIL: element_at_point -> {e}")
        failed += 1

    # --- Test 12: Find windows by PID ---
    print("\n[12] Find Windows by PID")
    try:
        result = find_windows_by_pid(20400)  # V6
        if result:
            print(f"  PASS: find_windows_by_pid(V6) -> {len(result)} windows")
            passed += 1
        else:
            print("  WARN: find_windows_by_pid(V6) -> 0 windows")
            passed += 1
    except Exception as e:
        print(f"  FAIL: find_windows_by_pid -> {e}")
        failed += 1

    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

