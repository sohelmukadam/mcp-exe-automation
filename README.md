# mcp-exe-automation

A Model Context Protocol (MCP) server for automating any Windows desktop application (.exe) using Python, pywinauto, and the UI Automation framework. Provides 57 tools that let AI agents interact with windows, controls, menus, dialogs, keyboard, mouse, clipboard, and more -- without needing application-specific APIs.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [Tool Reference](#tool-reference)
- [Usage Examples](#usage-examples)
- [Project Structure](#project-structure)
- [Supported Applications](#supported-applications)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

- Works with ANY Windows desktop application (Win32, WPF, UWP, Electron, Qt, Delphi, Java)
- 57 automation tools exposed via the Model Context Protocol
- Multiple control discovery strategies (automation ID, title, class name, regex)
- Robust focus management with 4-strategy foreground window acquisition
- Unicode-safe window title matching (handles invisible characters in Edge, Office)
- Handle-based targeting for multiple windows with the same title
- DPI-aware coordinate handling
- Thread-safe clipboard operations
- Configurable timeouts and retry logic
- Structured error responses with recovery suggestions
- Verification for type and click operations

---

## Requirements

- Windows 10 or later (64-bit)
- Python 3.10 or later
- The target application must be running on the same machine

---

## Quick Start

```bash
git clone https://github.com/sohelmukadam/mcp-exe-automation.git
cd mcp-exe-automation
pip install -r requirements.txt
python run.py
```

The server starts and listens for MCP messages on stdio. Connect any MCP client (Claude Desktop, VS Code, etc.) to start automating Windows apps.

---

## Installation

### From Source

```bash
git clone https://github.com/sohelmukadam/mcp-exe-automation.git
cd mcp-exe-automation
pip install -r requirements.txt
```

### Using pip (editable install)

```bash
git clone https://github.com/sohelmukadam/mcp-exe-automation.git
cd mcp-exe-automation
pip install -e .
```

### Dependencies

| Package | Purpose |
|---------|---------|
| mcp >= 1.0.0 | Model Context Protocol SDK (FastMCP) |
| pywinauto >= 0.6.8 | Windows UI Automation bindings |
| pywin32 >= 306 | Win32 API access |
| psutil >= 5.9.0 | Process management |
| Pillow >= 10.0.0 | Screenshot capture |
| comtypes >= 1.2.0 | COM interface support |

---

## Configuration

### Claude Desktop

Add to your `claude_desktop_config.json` (typically at `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "windows-automation": {
      "command": "python",
      "args": ["run.py"],
      "cwd": "C:/path/to/mcp-exe-automation"
    }
  }
}
```

### VS Code (Copilot / Continue)

Add to your VS Code `settings.json` or `.vscode/mcp.json`:

```json
{
  "mcp": {
    "servers": {
      "windows-automation": {
        "command": "python",
        "args": ["run.py"],
        "cwd": "C:/path/to/mcp-exe-automation"
      }
    }
  }
}
```

### Generic MCP Client (stdio transport)

```bash
cd mcp-exe-automation
python run.py
```

The server communicates over stdin/stdout using the MCP JSON-RPC protocol.

---

## Running the Server

```bash
cd mcp-exe-automation
python run.py
```

That is it. The `run.py` entry point handles path setup automatically -- no need to set `PYTHONPATH` or any environment variables.

Logs are written to stderr so they do not interfere with the MCP protocol on stdout.

---

## Tool Reference

### Application Process Management (4 tools)

| Tool | Description |
|------|-------------|
| `launch_app` | Launch an application by path or command |
| `attach_app` | Connect to a running application by title or PID |
| `terminate_app` | Terminate an application |
| `list_apps` | List running applications with window info |

### Window Discovery and Management (9 tools)

| Tool | Description |
|------|-------------|
| `list_windows_tool` | List all visible top-level windows |
| `get_focused_window` | Get the currently active/foreground window |
| `focus_window_tool` | Bring a window to the foreground |
| `inspect_window` | Get the control tree of a window |
| `window_info` | Get detailed window properties |
| `windows_by_pid` | Find all windows belonging to a process |
| `manage_window` | Minimize, maximize, restore, close, resize, or move a window |
| `wait_window` | Wait for a window to appear |
| `wait_window_close` | Wait for a window to close |

### Control Interaction (18 tools)

| Tool | Description |
|------|-------------|
| `find_controls_tool` | Find controls by type, name, or automation ID |
| `find_controls_by_handle` | Find controls in a window identified by handle |
| `click_control_tool` | Click a control (left, right, double-click) |
| `type_text_tool` | Type text into a control |
| `type_text_by_handle` | Type text into a control by window handle |
| `read_control_text` | Read text from a control |
| `get_text_by_handle` | Read text from a control by window handle |
| `read_all_text` | Get all text content from a window |
| `control_state` | Get the state of a control (enabled, checked, selected) |
| `get_control_props` | Get all properties of a control |
| `select_combo_item` | Select an item in a dropdown/combobox |
| `select_list_item` | Select an item in a listbox |
| `select_tab_tool` | Select a tab in a tab control |
| `toggle_checkbox` | Check or uncheck a checkbox |
| `scroll_control_tool` | Scroll a control |
| `wait_for_control_tool` | Wait for a control to appear |
| `wait_and_click_tool` | Wait for a control and click it |
| `wait_text_change` | Wait for text content to change |

### Keyboard and Mouse (6 tools)

| Tool | Description |
|------|-------------|
| `send_keys_tool` | Send keystrokes (supports special keys) |
| `send_hotkey_tool` | Send keyboard shortcuts (e.g., Ctrl+S) |
| `type_raw_text` | Type text at the current cursor position |
| `click_at` | Click at specific screen coordinates |
| `move_mouse` | Move the mouse to coordinates |
| `drag_mouse` | Drag from one point to another |

### Menu Navigation (3 tools)

| Tool | Description |
|------|-------------|
| `click_menu` | Click a menu item by path |
| `list_menu_items` | List available menu items |
| `context_menu_click` | Open context menu and click an item |

### Screenshots (2 tools)

| Tool | Description |
|------|-------------|
| `take_screenshot` | Capture the full screen or a specific window |
| `take_control_screenshot` | Capture a specific control |

### Clipboard (4 tools)

| Tool | Description |
|------|-------------|
| `clipboard_get` | Read current clipboard text |
| `clipboard_set` | Set clipboard text |
| `clipboard_copy` | Send Ctrl+C to copy selection |
| `clipboard_paste` | Send Ctrl+V to paste |

### Dialogs (3 tools)

| Tool | Description |
|------|-------------|
| `handle_dialog_tool` | Accept or dismiss a dialog |
| `inspect_dialog` | Get information about a dialog |
| `wait_dialog` | Wait for a dialog to appear |

### Tree and Grid Controls (5 tools)

| Tool | Description |
|------|-------------|
| `tree_expand` | Expand a tree node |
| `tree_collapse` | Collapse a tree node |
| `tree_select` | Select a tree item |
| `read_grid` | Read contents of a data grid |
| `element_at_point` | Identify the UI element at screen coordinates |

### Compound Operations (2 tools)

| Tool | Description |
|------|-------------|
| `type_and_verify` | Type text and verify it was entered correctly |
| `click_and_check` | Click a control and report what changed |

### Synchronization (1 tool)

| Tool | Description |
|------|-------------|
| `wait_app_idle` | Wait for an application to become idle |

---

## Usage Examples

### List all open windows

```
Tool: list_windows_tool
```

Returns all visible windows with title, handle, PID, class name, and rectangle.

### Type text into Notepad

```
Tool: type_text_tool
Args:
  window_title: "Untitled - Notepad"
  control_identifier: "RichEditD2DPT"
  text: "Hello World"
  clear_first: true
```

### Click a button in any application

```
Tool: click_control_tool
Args:
  window_title: "My App"
  control_identifier: "btnSubmit"
  control_type: "Button"
```

### Read a document from Word

```
Tool: read_control_text
Args:
  window_title: "Document1 - Word"
  control_identifier: "_WwG"
  control_type: "Document"
```

### Find all controls in a window

```
Tool: find_controls_tool
Args:
  window_title: "Calculator"
  control_type: "Button"
```

### Handle multiple windows with the same title

```
Step 1: list_windows_tool  (get the handle for the specific window)
Step 2: find_controls_by_handle  (window_handle=68052)
Step 3: type_text_by_handle  (window_handle=68052, control_identifier="RichEditD2DPT", text="Hello")
```

### Send keyboard shortcuts

```
Tool: send_hotkey_tool
Args:
  modifiers: ["ctrl"]
  key: "s"
  window_title: "My App"
```

### Launch an application and interact with it

```
Step 1: launch_app  (exe_path="C:\\Windows\\notepad.exe")
Step 2: wait_window  (window_title="Notepad", timeout=10)
Step 3: type_text_tool  (window_title="Notepad", control_identifier="RichEditD2DPT", text="Automated text")
Step 4: send_hotkey_tool  (modifiers=["ctrl"], key="s", window_title="Notepad")
```

---

## Project Structure

```
mcp-exe-automation/
    run.py                  # Entry point - starts the MCP server
    pyproject.toml          # Python project metadata and dependencies
    requirements.txt        # Pinned dependencies for pip install
    src/
        __init__.py
        server.py           # FastMCP server with 57 tool registrations
        automation/
            __init__.py
            controls.py     # Control find, click, type, read, select, scroll
            windows.py      # Window discovery, focus, manipulation
            process.py      # Application launch, attach, terminate
            keyboard_mouse.py  # Keyboard/mouse input simulation
            menu.py         # Menu navigation
            screenshot.py   # Screen/control capture
            clipboard.py    # Clipboard operations
            dialogs.py      # Dialog handling
            waits.py        # Wait conditions
            advanced.py     # Tree views, grids, property inspection
            utils.py        # COM safety, retry, DPI, clipboard thread safety
        tools/
            __init__.py
    tests/
        test_comprehensive.py      # 20 cross-application tests
        test_automation_fixes.py   # 6 robustness regression tests
        test_stress.py             # Multi-app stress tests
```

---

## Supported Applications

Tested and verified with:

- Win32 apps (Notepad, Paint, WordPad, File Explorer)
- Microsoft Office (Word, Excel)
- Browsers (Chrome, Edge - Chromium/Electron)
- UWP/WinUI apps (Calculator, Settings)
- Electron apps (VS Code, Slack)
- Delphi/VCL apps (custom business software)
- Qt apps (VirtualBox)
- Java/Swing apps (IntelliJ, Eclipse)
- Any application with a standard Windows UI

---

## Troubleshooting

### Window not found

- Use `list_windows_tool` to see exact window titles
- Titles are matched as case-insensitive substrings
- Some apps embed invisible Unicode characters in titles (handled automatically)

### Control not found

- Use `find_controls_tool` with no filters to discover all controls
- Try increasing `max_depth` for deeply nested UIs (default 12, use 15+ for Explorer)
- Electron apps expose fewer controls; use keyboard shortcuts or `control_type="TabItem"`

### Focus/foreground issues

- The server uses 4 strategies to bring windows to foreground
- If typing goes to the wrong window, use `focus_window_tool` first
- For background automation, prefer `click_control_tool` with invoke pattern over coordinate clicks

### Timeout errors

- Default timeout is 5 seconds; pass a longer `timeout` parameter if needed
- Use `wait_app_idle` before interacting with slow applications

### Multiple windows with the same title

- Use `list_windows_tool` to get the unique handle for each window
- Then use `find_controls_by_handle`, `type_text_by_handle`, or `get_text_by_handle`

---

## License

MIT License. See [LICENSE](LICENSE) for details.
