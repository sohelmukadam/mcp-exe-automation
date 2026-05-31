"""Entry point for the MCP Windows Automation server."""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

from src.server import mcp

if __name__ == "__main__":
    mcp.run()
