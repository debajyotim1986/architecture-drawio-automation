"""Entry point: `python -m drawio_mcp_server` or the `drawio-mcp-server` script."""

from __future__ import annotations

import asyncio
import sys

from .server import run


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
