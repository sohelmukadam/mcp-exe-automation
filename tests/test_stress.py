"""Stress-test automation against multiple app types to find weaknesses."""
import sys
sys.path.insert(0, ".")
import time
from src.automation.controls import find_controls, type_text, get_control_text, click_control
from src.automation.windows import get_window, list_windows, get_active_window


def test_chrome():
    """Test Chrome automation."""
    print("\n=== Chrome ===")
    # Find Edit controls (URL bar)
    controls = find_controls("Revolutionizing QA", control_type="Edit")
    print(f"  Edit controls: {len(controls)}")
    for c in controls[:3]:
        print(f"    {c.get('name', '')[:40]} | aid={c.get('automation_id', '')[:20]}")

    # Try to read the URL bar by automation_id found above
    if controls:
        aid = controls[0].get('automation_id', '')
        if aid:
            try:
                result = get_control_text("Revolutionizing QA", aid)
                print(f"  URL bar text: {result.get('text', '')[:60]}")
            except Exception as e:
                print(f"  URL bar read failed: {e}")

    # All controls discovery
    all_ctrls = find_controls("Revolutionizing QA")
    # Filter out metadata entries
    real_ctrls = [c for c in all_ctrls if not c.get('_metadata')]
    types = set(c.get('control_type', '') for c in real_ctrls if c.get('control_type'))
    print(f"  Total controls (no filter): {len(real_ctrls)}")
    print(f"  Control types: {sorted(types)}")


def test_edge():
    """Test Edge automation (title has invisible zero-width space)."""
    print("\n=== Edge ===")
    # Edge embeds a zero-width space in "Microsoft Edge" - our fix should handle this
    controls = find_controls("Microsoft Edge", control_type="Edit")
    print(f"  Edit controls: {len(controls)}")
    for c in controls[:3]:
        print(f"    {c.get('name', '')[:40]} | aid={c.get('automation_id', '')[:20]}")

    # All controls
    all_ctrls = find_controls("Microsoft Edge")
    print(f"  Total controls (no filter): {len(all_ctrls)}")


def test_word():
    """Test Word automation."""
    print("\n=== Word ===")
    # Document controls
    controls = find_controls("Word", control_type="Document")
    print(f"  Document controls: {len(controls)}")
    for c in controls:
        print(f"    {c['name'][:40]} | class={c['class_name'][:20]}")

    # Try to read document text
    try:
        result = get_control_text("Word", "_WwG", control_type="Document")
        text_preview = result.get("text", "")[:80]
        print(f"  Document text: {repr(text_preview)}")
    except Exception as e:
        print(f"  Document read: {e}")

    # All controls
    all_ctrls = find_controls("Word")
    print(f"  Total controls (no filter): {len(all_ctrls)}")
    types = set(c['control_type'] for c in all_ctrls)
    print(f"  Types: {sorted(types)[:10]}")


def test_vscode():
    """Test VS Code automation."""
    print("\n=== VS Code ===")
    # VS Code uses Chrome_WidgetWin_1 class (Electron)
    all_ctrls = find_controls("Visual Studio Code")
    print(f"  Total controls (no filter): {len(all_ctrls)}")
    types = set(c['control_type'] for c in all_ctrls)
    print(f"  Types: {sorted(types)}")

    # Find tabs or tree items
    tabs = find_controls("Visual Studio Code", control_type="TabItem")
    print(f"  Tab items: {len(tabs)}")
    for t in tabs[:5]:
        print(f"    {t['name'][:40]}")


def test_notepad_multi_window():
    """Test with multiple Notepad windows (same title)."""
    print("\n=== Multi-window Notepad ===")
    # There are 3+ Notepad windows with 'Untitled' title
    windows = list_windows()
    notepad_wins = [w for w in windows if "Notepad" in w["title"]]
    print(f"  Notepad windows: {len(notepad_wins)}")
    for w in notepad_wins:
        print(f"    {w['title'][:50]} | handle={w['handle']}")

    # Can we target a specific one by more unique title?
    try:
        w = get_window("V6Connector.exe - Notepad")
        print(f"  Specific notepad found: {w.wrapper_object().window_text()}")
    except Exception as e:
        print(f"  Specific notepad failed: {e}")


def test_stale_window_handling():
    """Test what happens when window state changes between calls."""
    print("\n=== Stale State Handling ===")
    # Get a window reference, then try to read after potential state change
    try:
        result1 = get_control_text("*He - Notepad", "RichEditD2DPT")
        print(f"  Read from *He Notepad: {repr(result1.get('text', '')[:40])}")
    except Exception as e:
        print(f"  Read failed: {e}")

    # Try to type into a closed/non-existent window
    try:
        result = type_text("ThisWindowDoesNotExist12345", "edit1", "test")
        print(f"  Non-existent window: {result}")
    except Exception as e:
        err_msg = str(e)[:80]
        print(f"  Non-existent window error: {err_msg}")


def test_timeout_behavior():
    """Test timeout handling for slow operations."""
    print("\n=== Timeout Behavior ===")
    import time
    start = time.time()
    try:
        # Try to find a window that doesn't exist with short timeout
        w = get_window("NonExistentApp_XYZ_123", timeout=2.0)
        print(f"  UNEXPECTED: found {w}")
    except ValueError as e:
        elapsed = time.time() - start
        print(f"  Non-existent window timeout: {elapsed:.1f}s (expected ~2s)")
        if elapsed > 3.0:
            print(f"  WARNING: Took too long ({elapsed:.1f}s)! Timeout not respected")
        else:
            print(f"  OK: Timeout respected")


def test_special_characters():
    """Test handling of special/unicode characters."""
    print("\n=== Special Characters ===")
    # Type special chars into notepad (V6Connector has stable title)
    special_text = "Test: <html> & 'quotes' \"double\" @#$% end"
    try:
        result = type_text("V6Connector.exe - Notepad", "RichEditD2DPT", special_text, clear_first=True)
        print(f"  Type special chars: {result.get('status')}")
        print(f"  Verified: {result.get('verified', 'N/A')}")
        if result.get('verified') == False:
            print(f"  Actual: {result.get('actual_text_preview', 'N/A')}")
        time.sleep(0.3)
        read_back = get_control_text("V6Connector.exe - Notepad", "RichEditD2DPT")
        actual = read_back.get("text", "")
        if special_text in actual:
            print(f"  Read-back verify: EXACT MATCH")
        else:
            print(f"  Read-back verify: MISMATCH")
            print(f"    Expected: {repr(special_text[:50])}")
            print(f"    Got:      {repr(actual[:50])}")
    except Exception as e:
        print(f"  Special chars failed: {e}")


def test_rapid_operations():
    """Test rapid sequential operations (race conditions)."""
    print("\n=== Rapid Operations ===")
    errors = 0
    for i in range(5):
        try:
            type_text("V6Connector.exe - Notepad", "RichEditD2DPT", f"Line {i}", clear_first=True)
        except Exception as ex:
            errors += 1
            if i == 0:
                print(f"  First error: {ex}")
    print(f"  5 rapid type operations: {5-errors}/5 succeeded")

    # Rapid reads
    read_errors = 0
    for i in range(5):
        try:
            get_control_text("V6Connector.exe - Notepad", "RichEditD2DPT")
        except Exception:
            read_errors += 1
    print(f"  5 rapid read operations: {5-read_errors}/5 succeeded")


if __name__ == "__main__":
    tests = [
        test_chrome,
        test_edge,
        test_word,
        test_vscode,
        test_notepad_multi_window,
        test_stale_window_handling,
        test_timeout_behavior,
        test_special_characters,
        test_rapid_operations,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  CRASH: {type(e).__name__}: {e}")

    print("\n" + "=" * 50)
    print("Stress test complete")
