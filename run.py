"""Entry point for the MCP Windows Automation server."""

import logging
import os
import sys

# Ensure the project root is on sys.path so 'src' package is importable
# regardless of working directory or PYTHONPATH settings.
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

from src.server import mcp

if __name__ == "__main__":
    mcp.run()
