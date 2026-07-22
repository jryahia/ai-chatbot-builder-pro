"""Entry point: launches FastAPI server + Flet desktop UI together."""

import asyncio
import os
import sys
import threading
import time
from pathlib import Path

import structlog

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import settings

logger = structlog.get_logger(__name__)

_server_ready = threading.Event()


def _configure_logging() -> None:
    import logging
    import structlog

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def _run_server() -> None:
    """Run the FastAPI server in a background thread."""
    import asyncio
    import uvicorn
    from src.api_server import app

    config = uvicorn.Config(
        app=app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level,
    )
    server = uvicorn.Server(config)

    async def _serve():
        await server.serve()

    _server_ready.set()
    asyncio.run(_serve())


def _wait_for_server(timeout: float = 30.0) -> bool:
    """Poll until the API server responds."""
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://localhost:{settings.api_port}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main() -> None:
    _configure_logging()

    # Start API server in background thread
    server_thread = threading.Thread(target=_run_server, daemon=True, name="api-server")
    server_thread.start()
    _server_ready.wait(timeout=5)

    logger.info("waiting_for_api_server", port=settings.api_port)
    if not _wait_for_server(30):
        logger.warning("api_server_not_ready_continuing_anyway")

    # Launch Flet desktop app
    import flet as ft
    from src.ui.app import main as flet_main

    ft.app(
        target=flet_main,
        view=ft.AppView.FLET_APP,
        port=settings.flet_port,
    )


if __name__ == "__main__":
    main()
