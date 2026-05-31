"""Shared utilities for robust Windows automation.

Provides:
- COM thread safety initialization
- Retry logic with exponential backoff
- Operation timeout protection
- DPI-aware coordinate handling
- Thread-safe clipboard operations
- Safe foreground window management
- Input validation helpers
- Backend auto-detection
"""

import ctypes
import functools
import logging
import threading
import time
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ═══════════════════════════════════════════════════════════════════════════════
# COM THREAD SAFETY
# ═══════════════════════════════════════════════════════════════════════════════

_com_initialized_threads: set = set()
_com_lock = threading.Lock()


def ensure_com_initialized():
    """Initialize COM for the current thread if not already done.

    Must be called before any COM/UIA operations in new threads.
    Uses MTA (Multi-Threaded Apartment) which is compatible with pywinauto.
    """
    tid = threading.current_thread().ident
    if tid in _com_initialized_threads:
        return

    with _com_lock:
        if tid in _com_initialized_threads:
            return
        try:
            import pythoncom
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        except Exception:
            # Fallback: try without pythoncom (may already be initialized)
            try:
                ctypes.windll.ole32.CoInitializeEx(None, 0x0)  # COINIT_MULTITHREADED
            except Exception:
                pass
        _com_initialized_threads.add(tid)


# ═══════════════════════════════════════════════════════════════════════════════
# RETRY & TIMEOUT
# ═══════════════════════════════════════════════════════════════════════════════


def retry(
    max_attempts: int = 3,
    delay: float = 0.5,
    backoff: float = 1.5,
    exceptions: tuple = (Exception,),
):
    """Decorator that retries a function on failure with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts.
        delay: Initial delay between retries (seconds).
        backoff: Multiplier for delay on each retry.
        exceptions: Tuple of exception types to catch and retry on.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        logger.debug(
                            "Retry %d/%d for %s: %s (waiting %.1fs)",
                            attempt + 1, max_attempts, func.__name__, e, current_delay
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_error  # type: ignore
        return wrapper
    return decorator


def safe_operation(func: Callable[..., T], *args, default: Any = None, **kwargs) -> Any:
    """Execute a function safely, returning default on any exception."""
    try:
        return func(*args, **kwargs)
    except Exception:
        return default


def with_timeout(func: Callable[..., T], timeout: float, *args, **kwargs) -> Optional[T]:
    """Execute a function with a timeout using threading.

    Protects against indefinitely-blocking pywinauto operations
    (e.g., set_focus() on unresponsive applications).

    Args:
        func: Function to execute.
        timeout: Maximum seconds to wait.
        *args, **kwargs: Arguments to pass to the function.

    Returns:
        Function result or None if timeout.

    Raises:
        The original exception if the function raised within the timeout.
    """
    result = [None]
    error = [None]

    def target():
        ensure_com_initialized()
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        logger.warning("Operation timed out after %.1fs: %s", timeout, func.__name__)
        return None

    if error[0]:
        raise error[0]

    return result[0]


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# DPI AWARENESS
# ═══════════════════════════════════════════════════════════════════════════════

_dpi_scale: Optional[float] = None


def get_dpi_scale() -> float:
    """Get the system DPI scale factor (1.0 = 96 DPI / 100%).

    Returns:
        Scale factor (e.g., 1.25 for 120 DPI, 1.5 for 144 DPI).
    """
    global _dpi_scale
    if _dpi_scale is not None:
        return _dpi_scale

    try:
        # Enable DPI awareness for this process
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        dpi = ctypes.windll.user32.GetDpiForSystem()
        _dpi_scale = dpi / 96.0
    except Exception:
        _dpi_scale = 1.0

    return _dpi_scale


def logical_to_physical(x: int, y: int) -> tuple[int, int]:
    """Convert logical (DPI-independent) coordinates to physical screen coordinates.

    Args:
        x: Logical X coordinate.
        y: Logical Y coordinate.

    Returns:
        Tuple of (physical_x, physical_y).
    """
    scale = get_dpi_scale()
    if scale == 1.0:
        return (x, y)
    return (int(x * scale), int(y * scale))


def physical_to_logical(x: int, y: int) -> tuple[int, int]:
    """Convert physical screen coordinates to logical (DPI-independent) coordinates.

    Args:
        x: Physical X coordinate.
        y: Physical Y coordinate.

    Returns:
        Tuple of (logical_x, logical_y).
    """
    scale = get_dpi_scale()
    if scale == 1.0:
        return (x, y)
    return (int(x / scale), int(y / scale))


# ═══════════════════════════════════════════════════════════════════════════════
# CLIPBOARD THREAD SAFETY
# ═══════════════════════════════════════════════════════════════════════════════

_clipboard_lock = threading.Lock()


def safe_clipboard_get() -> str:
    """Thread-safe clipboard text read with retry.

    Returns:
        Clipboard text content, or empty string on failure.
    """
    import win32clipboard
    import win32con

    with _clipboard_lock:
        for attempt in range(3):
            try:
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                        return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) or ""
                    return ""
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    logger.debug("Clipboard read failed after 3 attempts: %s", e)
        return ""


def safe_clipboard_set(text: str) -> bool:
    """Thread-safe clipboard text write with retry.

    Args:
        text: Text to place on clipboard.

    Returns:
        True if successful.
    """
    import win32clipboard
    import win32con

    with _clipboard_lock:
        for attempt in range(3):
            try:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
                    return True
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    logger.debug("Clipboard write failed after 3 attempts: %s", e)
        return False


def safe_clipboard_clear() -> bool:
    """Thread-safe clipboard clear."""
    import win32clipboard

    with _clipboard_lock:
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════


def validate_window_title(title: str) -> str:
    """Validate and sanitize a window title parameter.

    Args:
        title: Window title to validate.

    Returns:
        The validated title.

    Raises:
        ValueError: If the title is empty or invalid.
    """
    if not title or not title.strip():
        raise ValueError("Window title cannot be empty or whitespace-only")
    return title.strip()


def validate_control_identifier(identifier: str) -> str:
    """Validate a control identifier parameter.

    Args:
        identifier: Control identifier to validate.

    Returns:
        The validated identifier.

    Raises:
        ValueError: If the identifier is empty or invalid.
    """
    if not identifier or not identifier.strip():
        raise ValueError("Control identifier cannot be empty or whitespace-only")
    # Truncate absurdly long identifiers to prevent regex DoS
    if len(identifier) > 1000:
        raise ValueError("Control identifier is too long (max 1000 characters)")
    return identifier


# ═══════════════════════════════════════════════════════════════════════════════
# FOREGROUND WINDOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


def bring_window_to_front(hwnd: int) -> bool:
    """Reliably bring a window to the foreground using multiple strategies.

    Uses 4 progressively aggressive strategies:
    1. Direct SetForegroundWindow
    2. Alt-key trick (bypasses foreground lock)
    3. AttachThreadInput (cross-thread focus transfer)
    4. BringWindowToTop + ShowWindow

    Args:
        hwnd: Window handle (HWND).

    Returns:
        True if window is now in foreground.
    """
    import win32con
    import win32gui

    try:
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)

        # Strategy 1: Direct SetForegroundWindow
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)
            if win32gui.GetForegroundWindow() == hwnd:
                return True
        except Exception:
            pass

        # Strategy 2: Alt-key trick (simulates user interaction)
        try:
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # VK_MENU down
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # VK_MENU up
            time.sleep(0.05)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)
            if win32gui.GetForegroundWindow() == hwnd:
                return True
        except Exception:
            pass

        # Strategy 3: AttachThreadInput (transfers focus permission)
        try:
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd and foreground_hwnd != hwnd:
                foreground_tid = ctypes.windll.user32.GetWindowThreadProcessId(
                    foreground_hwnd, None
                )
                target_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
                if foreground_tid != target_tid:
                    ctypes.windll.user32.AttachThreadInput(foreground_tid, target_tid, True)
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.05)
                    finally:
                        ctypes.windll.user32.AttachThreadInput(foreground_tid, target_tid, False)
                    if win32gui.GetForegroundWindow() == hwnd:
                        return True
        except Exception:
            pass

        # Strategy 4: BringWindowToTop + ShowWindow (last resort)
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            return True
        except Exception:
            pass

    except Exception as e:
        logger.debug("bring_window_to_front failed for hwnd %d: %s", hwnd, e)

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# BACKEND AUTO-DETECTION
# ═══════════════════════════════════════════════════════════════════════════════


def get_backend_for_window(hwnd: int) -> str:
    """Determine the best pywinauto backend for a given window.

    Modern apps (UWP, WPF, Electron) work better with 'uia'.
    Legacy Win32 apps sometimes need the 'win32' backend.

    Args:
        hwnd: Window handle to analyze.

    Returns:
        'uia' or 'win32'
    """
    import win32gui

    # Classes that work better with win32 backend
    win32_prefixes = (
        "ThunderRT6",        # VB6
        "WindowsForms10.",   # .NET WinForms (older)
    )

    try:
        class_name = win32gui.GetClassName(hwnd)
        for prefix in win32_prefixes:
            if class_name.startswith(prefix):
                return "win32"
    except Exception:
        pass

    return "uia"


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN / COORDINATE UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════


def get_screen_size() -> tuple[int, int]:
    """Get the primary screen resolution in physical pixels.

    Returns:
        Tuple of (width, height).
    """
    try:
        w = ctypes.windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return (w, h)
    except Exception:
        return (1920, 1080)


def clamp_coordinates(x: int, y: int) -> tuple[int, int]:
    """Clamp coordinates to within the screen bounds.

    Prevents mouse operations from targeting off-screen positions.

    Args:
        x: X coordinate.
        y: Y coordinate.

    Returns:
        Clamped (x, y) tuple.
    """
    w, h = get_screen_size()
    return (max(0, min(x, w - 1)), max(0, min(y, h - 1)))

