"""Process management module - launch, attach, monitor, and terminate applications."""

import logging
import os
import subprocess
import time
from typing import Optional

import psutil
from pywinauto import Application

logger = logging.getLogger(__name__)


class ProcessManager:
    """Manages application processes - launching, attaching, monitoring, terminating."""

    _instances: dict[int, "ProcessManager"] = {}

    def __init__(self, app: Application, process: Optional[psutil.Process] = None):
        self.app = app
        self.process = process
        self._pid = app.process if hasattr(app, 'process') else (process.pid if process else None)

    @property
    def pid(self) -> Optional[int]:
        return self._pid

    @classmethod
    def launch(
        cls,
        exe_path: str,
        args: Optional[list[str]] = None,
        work_dir: Optional[str] = None,
        backend: str = "uia",
        timeout: float = 30.0,
    ) -> "ProcessManager":
        """Launch an application and wait for it to be ready.

        Args:
            exe_path: Full path to the executable.
            args: Optional command-line arguments.
            work_dir: Working directory for the process.
            backend: pywinauto backend - 'uia' (modern) or 'win32' (legacy).
            timeout: Max seconds to wait for the app to be ready.

        Returns:
            ProcessManager instance for the launched application.
        """
        if not os.path.isfile(exe_path):
            raise FileNotFoundError(f"Executable not found: {exe_path}")

        logger.info("Launching: %s %s", exe_path, args or "")

        cmd_args = [exe_path] + (args or [])
        work_dir = work_dir or os.path.dirname(exe_path)

        # Use subprocess.Popen for reliable launching, then connect via pywinauto.
        # This avoids pywinauto's Application.start() issues with modern apps
        # that use process redirection (e.g., Windows 11 Notepad).
        process = subprocess.Popen(
            cmd_args,
            cwd=work_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        initial_pid = process.pid
        logger.info("Started subprocess PID %d", initial_pid)

        # Wait for a window to appear from this process or a child process
        deadline = time.time() + timeout
        app = None
        pid = initial_pid

        while time.time() < deadline:
            time.sleep(0.5)
            # First try connecting with the original PID
            try:
                app = Application(backend=backend).connect(process=initial_pid)
                top = app.top_window()
                if top.is_visible():
                    pid = initial_pid
                    break
            except Exception:
                pass

            # If original PID died, the app may have re-launched under a new PID.
            # Look for child processes or search by exe name.
            try:
                parent = psutil.Process(initial_pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        app = Application(backend=backend).connect(process=child.pid)
                        top = app.top_window()
                        if top.is_visible():
                            pid = child.pid
                            break
                    except Exception:
                        continue
                if app and pid != initial_pid:
                    break
            except psutil.NoSuchProcess:
                pass

            # Fallback: search for a window by process name
            exe_name = os.path.basename(exe_path).lower()
            try:
                from pywinauto import Desktop
                desktop = Desktop(backend=backend)
                for win in desktop.windows():
                    try:
                        if win.is_visible():
                            win_pid = win.process_id()
                            try:
                                proc_check = psutil.Process(win_pid)
                                if proc_check.name().lower() == exe_name:
                                    app = Application(backend=backend).connect(process=win_pid)
                                    pid = win_pid
                                    break
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                    except Exception:
                        pass
                if app and pid != initial_pid:
                    break
            except Exception:
                pass

        if app is None:
            raise TimeoutError(f"Application '{exe_path}' did not produce a visible window within {timeout}s")

        # Get psutil process handle
        proc = None
        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            logger.warning("Could not get psutil.Process for PID %d", pid)

        instance = cls(app, proc)
        instance._pid = pid
        cls._instances[pid] = instance
        logger.info("Launched and connected to PID %d: %s", pid, exe_path)
        return instance

    @classmethod
    def attach(
        cls,
        pid: Optional[int] = None,
        title: Optional[str] = None,
        exe_name: Optional[str] = None,
        backend: str = "uia",
    ) -> "ProcessManager":
        """Attach to a running application.

        Args:
            pid: Process ID to attach to.
            title: Window title (partial match) to find the process.
            exe_name: Executable name (e.g. 'notepad.exe') to find.
            backend: pywinauto backend - 'uia' or 'win32'.

        Returns:
            ProcessManager instance for the attached application.
        """
        connect_kwargs = {}
        if pid:
            connect_kwargs["process"] = pid
        elif title:
            connect_kwargs["title_re"] = f".*{title}.*"
        elif exe_name:
            # Find PID by executable name
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and exe_name.lower() in proc.info['name'].lower():
                    connect_kwargs["process"] = proc.info['pid']
                    break
            if not connect_kwargs:
                raise ValueError(f"No running process found for: {exe_name}")
        else:
            raise ValueError("Must provide pid, title, or exe_name")

        app = Application(backend=backend).connect(**connect_kwargs)
        pid_val = connect_kwargs.get("process") or app.process
        proc = psutil.Process(pid_val) if pid_val else None
        instance = cls(app, proc)
        if pid_val:
            cls._instances[pid_val] = instance
        logger.info("Attached to PID %s", pid_val)
        return instance

    def is_running(self) -> bool:
        """Check if the managed process is still running."""
        if self.process:
            return self.process.is_running()
        return False

    def terminate(self, timeout: float = 10.0) -> bool:
        """Terminate the managed process gracefully, then forcefully if needed.

        Returns:
            True if the process was terminated successfully.
        """
        if not self.process:
            return False

        pid = self.process.pid
        logger.info("Terminating PID %d", pid)

        try:
            self.process.terminate()
            self.process.wait(timeout=timeout)
        except psutil.TimeoutExpired:
            logger.warning("Graceful termination timed out, killing PID %d", pid)
            self.process.kill()
        except psutil.NoSuchProcess:
            pass

        self._instances.pop(pid, None)
        return True

    def get_main_window(self):
        """Get the main/top window of the application."""
        return self.app.top_window()

    def get_windows(self) -> list:
        """Get all windows belonging to this application."""
        return self.app.windows()


def launch_application(
    exe_path: str,
    args: Optional[list[str]] = None,
    work_dir: Optional[str] = None,
    backend: str = "uia",
    timeout: float = 30.0,
) -> dict:
    """Launch an application and return connection info.

    Args:
        exe_path: Path to the executable.
        args: Command-line arguments.
        work_dir: Working directory.
        backend: 'uia' or 'win32'.
        timeout: Seconds to wait for launch.

    Returns:
        Dict with pid, exe_path, status.
    """
    pm = ProcessManager.launch(exe_path, args, work_dir, backend, timeout)
    return {
        "status": "success",
        "pid": pm.pid,
        "exe_path": exe_path,
        "is_running": pm.is_running(),
    }


def attach_to_application(
    pid: Optional[int] = None,
    title: Optional[str] = None,
    exe_name: Optional[str] = None,
    backend: str = "uia",
) -> dict:
    """Attach to a running application.

    Args:
        pid: Process ID.
        title: Window title (partial match).
        exe_name: Executable name.
        backend: 'uia' or 'win32'.

    Returns:
        Dict with pid, status.
    """
    pm = ProcessManager.attach(pid, title, exe_name, backend)
    return {
        "status": "success",
        "pid": pm.pid,
        "is_running": pm.is_running(),
    }


def terminate_application(pid: int) -> dict:
    """Terminate a managed application by PID.

    Args:
        pid: Process ID to terminate.

    Returns:
        Dict with status.
    """
    pm = ProcessManager._instances.get(pid)
    if pm:
        pm.terminate()
        return {"status": "success", "pid": pid, "action": "terminated"}

    # Try direct termination if not in managed instances
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=10)
        return {"status": "success", "pid": pid, "action": "terminated"}
    except psutil.NoSuchProcess:
        return {"status": "error", "message": f"Process {pid} not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def list_running_applications() -> list[dict]:
    """List running applications that have visible windows.

    Returns:
        List of dicts with process info for GUI applications only.
    """
    import win32gui
    import win32process

    apps = []
    seen_pids = set()

    def _enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid in seen_pids:
            return
        seen_pids.add(pid)
        try:
            proc = psutil.Process(pid)
            apps.append({
                "pid": pid,
                "name": proc.name(),
                "exe": proc.exe(),
                "window_title": title,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    win32gui.EnumWindows(_enum_callback, None)
    return apps
