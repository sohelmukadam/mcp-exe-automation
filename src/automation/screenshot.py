"""Screenshot capture module for windows and full desktop."""

import base64
import io
import logging
import os
from datetime import datetime
from typing import Optional

from PIL import ImageGrab

from src.automation.windows import get_window

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "screenshots")


def capture_screenshot(
    window_title: Optional[str] = None,
    output_path: Optional[str] = None,
    return_base64: bool = False,
) -> dict:
    """Capture a screenshot of a specific window or the full desktop.

    Args:
        window_title: Partial title of the window to capture. If None, captures
            the full desktop.
        output_path: File path to save the screenshot. If None, generates a
            timestamped path in the screenshots directory.
        return_base64: If True, also return the image as base64-encoded PNG.

    Returns:
        Dict with path to saved screenshot and optionally base64 data.
    """
    if output_path is None:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "window" if window_title else "desktop"
        filename = f"{prefix}_{timestamp}.png"
        output_path = os.path.join(SCREENSHOTS_DIR, filename)

    # Ensure parent directory exists
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent_dir, exist_ok=True)

    if window_title:
        logger.info("Capturing screenshot of window '%s'", window_title)
        try:
            window = get_window(window_title)
            image = window.capture_as_image()
        except Exception as e:
            logger.error("Failed to capture window '%s': %s", window_title, e)
            raise ValueError(
                f"Failed to capture screenshot of window '{window_title}': {e}"
            ) from e
    else:
        logger.info("Capturing full desktop screenshot")
        try:
            image = ImageGrab.grab()
        except Exception as e:
            logger.error("Failed to capture desktop screenshot: %s", e)
            raise ValueError(f"Failed to capture desktop screenshot: {e}") from e

    image.save(output_path)
    abs_path = os.path.abspath(output_path)
    logger.info("Screenshot saved to %s", abs_path)

    result = {
        "status": "success",
        "path": abs_path,
        "width": image.width,
        "height": image.height,
    }

    if return_base64:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        result["base64"] = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return result


def capture_control_screenshot(
    window_title: str,
    control_identifier: str,
    control_type: Optional[str] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Capture a screenshot of a specific control.

    Args:
        window_title: Partial title of the parent window.
        control_identifier: Identifier of the control.
        control_type: Optional control type.
        output_path: File path to save.

    Returns:
        Dict with path to saved screenshot.
    """
    from src.automation.controls import _find_control

    if output_path is None:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"control_{timestamp}.png"
        output_path = os.path.join(SCREENSHOTS_DIR, filename)

    window = get_window(window_title)
    control = _find_control(window, control_identifier, control_type)

    try:
        image = control.capture_as_image()
    except Exception as e:
        raise ValueError(f"Failed to capture control screenshot: {e}") from e

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    image.save(output_path)
    abs_path = os.path.abspath(output_path)

    return {
        "status": "success",
        "path": abs_path,
        "width": image.width,
        "height": image.height,
    }
