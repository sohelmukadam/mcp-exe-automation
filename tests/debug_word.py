"""Debug text reading from Word document."""
from src.automation.windows import get_window
from src.automation.controls import _find_control

window = get_window('Document')
control = _find_control(window, 'Body', 'Edit')
print(f"window_text: {control.window_text()!r}")

try:
    val = control.get_value()
    print(f"get_value returned: {val!r} (type: {type(val).__name__})")
except Exception as e:
    print(f"get_value exception: {type(e).__name__}: {e}")

# Try the clipboard approach directly
import win32clipboard, win32con
from pywinauto.keyboard import send_keys
import time

control.set_focus()
time.sleep(0.2)
send_keys("^a", pause=0.05)
time.sleep(0.2)
send_keys("^c", pause=0.05)
time.sleep(0.3)

try:
    win32clipboard.OpenClipboard()
    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
        clip_text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        print(f"clipboard text: {clip_text!r}")
    else:
        print("No unicode text in clipboard")
    win32clipboard.CloseClipboard()
except Exception as e:
    print(f"clipboard error: {e}")
    try:
        win32clipboard.CloseClipboard()
    except:
        pass

send_keys("{END}", pause=0.02)
