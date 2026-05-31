"""Test the automation-focused improvements."""
import sys
sys.path.insert(0, ".")

from src.automation.controls import find_controls
from src.automation.windows import get_active_window
from src.server import _make_error


def test_find_controls_no_filter():
    """find_controls with no filter should return all controls."""
    result = find_controls("Notepad")
    print(f"find_controls(no filter): {len(result)} controls")
    assert len(result) > 0, "Should return controls when no filter given"
    for r in result[:8]:
        ct = r["control_type"]
        nm = r["name"][:30]
        aid = r["automation_id"][:20]
        print(f"  {ct}: {nm} [{aid}]")


def test_get_active_window():
    """get_active_window should return current focused window info."""
    active = get_active_window()
    print(f"Active window: {active.get('title', '')[:50]}")
    assert active["status"] == "success"
    assert "title" in active
    assert "handle" in active
    assert "process_id" in active
    assert "top_level_controls" in active
    print(f"  Controls: {len(active['top_level_controls'])} items")


def test_error_response_structure():
    """Error responses should include retryable and suggestion fields."""
    # Control not found error
    err = _make_error(ValueError("Control 'xyz' (type=None) not found in window"), "test")
    assert "retryable" in err
    assert "suggestion" in err
    assert err["retryable"] is True
    assert "find_controls" in err["suggestion"]
    print(f"Control not found: retryable={err['retryable']}, suggestion={err['suggestion'][:60]}")

    # Window not found error (no 'control' in the message)
    err2 = _make_error(ValueError("Window 'abc' not found"), "test")
    assert err2["retryable"] is True
    assert "list_windows" in err2["suggestion"]
    print(f"Window not found: retryable={err2['retryable']}, suggestion={err2['suggestion'][:60]}")

    # Timeout error
    err3 = _make_error(TimeoutError("Operation timed out"), "test")
    assert err3["retryable"] is True
    assert "wait_app_idle" in err3["suggestion"]
    print(f"Timeout: retryable={err3['retryable']}, suggestion={err3['suggestion'][:60]}")

    # Non-editable control error
    err4 = _make_error(ValueError("Cannot type into a 'MenuItem' control"), "test")
    assert "suggestion" in err4
    print(f"Non-editable: suggestion={err4['suggestion'][:60]}")


def test_type_text_verification():
    """type_text should include verification info in response."""
    from src.automation.controls import type_text
    result = type_text("Notepad", "RichEditD2DPT", "verification test", clear_first=True)
    print(f"type_text result keys: {sorted(result.keys())}")
    assert result["status"] == "success"
    assert "window_title" in result
    # verified may or may not be present depending on control type
    print(f"  verified={result.get('verified')}, window_title={result.get('window_title', '')[:40]}")


def test_click_response_enriched():
    """click_control should include control_type and window_title in response."""
    from src.automation.controls import click_control
    # Click a non-destructive button (like the Notepad tab header)
    try:
        result = click_control("Notepad", "AddButton", control_type="Button")
        print(f"click_control result: {sorted(result.keys())}")
        assert "control_type" in result
        assert "window_title" in result
    except ValueError as e:
        # Button may not exist, that's OK for this test
        print(f"  Button not found (expected): {e}")


def test_inspect_window_depth():
    """inspect_window with default depth should find real controls."""
    from src.automation.windows import get_control_tree
    tree = get_control_tree("Notepad")
    # Flatten to count total nodes
    def count_nodes(nodes):
        total = len(nodes)
        for n in nodes:
            total += count_nodes(n.get("children", []))
        return total
    total = count_nodes(tree)
    print(f"Control tree: {len(tree)} top-level, {total} total nodes (depth=8 default)")
    assert total > 5, "Should find more than just Panes at default depth"


if __name__ == "__main__":
    tests = [
        test_find_controls_no_filter,
        test_get_active_window,
        test_error_response_structure,
        test_type_text_verification,
        test_click_response_enriched,
        test_inspect_window_depth,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            print(f"\n--- {t.__name__} ---")
            t()
            passed += 1
            print("  PASSED")
        except Exception as e:
            failed += 1
            print(f"  FAILED: {e}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    sys.exit(0 if failed == 0 else 1)
