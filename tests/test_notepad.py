"""Tests for Windows automation using Notepad as a sample application."""

import time
import pytest
from src.automation.process import launch_application, terminate_application
from src.automation.windows import list_windows, get_control_tree, focus_window
from src.automation.controls import click_control, type_text, get_control_text
from src.automation.keyboard_mouse import send_keys, send_hotkey
from src.automation.menu import click_menu_item
from src.automation.screenshot import capture_screenshot
from src.automation.clipboard import set_clipboard_text, get_clipboard_text, paste_from_clipboard


class TestNotepadAutomation:
    """Test suite using Notepad as a sample Windows application."""

    @pytest.fixture(autouse=True)
    def setup_notepad(self):
        """Launch Notepad before each test and terminate after."""
        result = launch_application("C:\\Windows\\System32\\notepad.exe")
        self.pid = result["pid"]
        time.sleep(1)  # Wait for Notepad to be fully ready
        yield
        terminate_application(self.pid)
        time.sleep(0.5)

    def test_launch_and_list_windows(self):
        """Test that Notepad appears in the window list after launching."""
        windows = list_windows()
        notepad_windows = [w for w in windows if "notepad" in w["title"].lower()]
        assert len(notepad_windows) > 0

    def test_type_text(self):
        """Test typing text into Notepad's editor."""
        result = type_text("Notepad", "RichEditD2DPT", "Hello World", clear_first=True)
        assert result["status"] == "success"

    def test_menu_navigation(self):
        """Test navigating Notepad's menu."""
        result = click_menu_item("Notepad", "File->New Window")
        assert result["status"] == "success"
        time.sleep(0.5)
        # Close the new window
        send_hotkey(["alt"], "{F4}", "Notepad")

    def test_keyboard_shortcuts(self):
        """Test sending keyboard shortcuts."""
        # Type some text first
        type_text("Notepad", "RichEditD2DPT", "Test text", clear_first=True)
        time.sleep(0.3)
        # Select all
        result = send_keys("^a", "Notepad")
        assert result["status"] == "success"

    def test_screenshot(self):
        """Test capturing a screenshot of Notepad."""
        result = capture_screenshot("Notepad")
        assert result["status"] == "success"
        assert result["path"].endswith(".png")

    def test_clipboard(self):
        """Test clipboard operations."""
        set_clipboard_text("Clipboard test")
        result = get_clipboard_text()
        assert result["text"] == "Clipboard test"

    def test_inspect_window(self):
        """Test inspecting Notepad's control tree."""
        tree = get_control_tree("Notepad", max_depth=3)
        assert len(tree) > 0

    def test_focus_window(self):
        """Test focusing a window."""
        result = focus_window("Notepad")
        assert result["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
