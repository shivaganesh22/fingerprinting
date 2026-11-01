"""Pytest fixtures: local HTTP test servers, configurations, and isolated databases."""

from __future__ import annotations

import http.server
import os
import socketserver
import tempfile
import threading
import sys
from collections.abc import Generator
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
django.setup()

from fpstudy.config import StudyConfig, load_study_config
from fpstudy.storage.store import DataStore



class SilentHandler(http.server.SimpleHTTPRequestHandler):
    """Quiet HTTP request handler that does not spam stderr during tests."""

    def log_message(self, format: str, *args: object) -> None:
        pass


class DisallowRobotsHandler(SilentHandler):
    """Handler that disallows all robots on /robots.txt."""

    def do_GET(self) -> None:
        if self.path == "/robots.txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"User-agent: *\nDisallow: /\n")
        else:
            super().do_GET()


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


@pytest.fixture(scope="session")
def fixture_server() -> Generator[str, None, None]:
    """Start primary local HTTP fixture server serving tests/fixtures on an ephemeral port."""
    fixtures_dir = str(Path(__file__).parent / "fixtures")

    def handler_factory(*args: object, **kwargs: object) -> SilentHandler:
        return SilentHandler(*args, directory=fixtures_dir, **kwargs)  # type: ignore

    server = ThreadedTCPServer(("127.0.0.1", 0), handler_factory)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def secondary_server() -> Generator[str, None, None]:
    """Start secondary local HTTP fixture server to simulate third-party origins."""
    fixtures_dir = str(Path(__file__).parent / "fixtures")

    def handler_factory(*args: object, **kwargs: object) -> SilentHandler:
        return SilentHandler(*args, directory=fixtures_dir, **kwargs)  # type: ignore

    server = ThreadedTCPServer(("127.0.0.1", 0), handler_factory)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def robots_disallow_server() -> Generator[str, None, None]:
    """Start HTTP server with a disallowing robots.txt."""
    fixtures_dir = str(Path(__file__).parent / "fixtures")

    def handler_factory(*args: object, **kwargs: object) -> DisallowRobotsHandler:
        return DisallowRobotsHandler(*args, directory=fixtures_dir, **kwargs)  # type: ignore

    server = ThreadedTCPServer(("127.0.0.1", 0), handler_factory)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def tmp_datastore() -> Generator[DataStore, None, None]:
    """Create a temporary SQLite database store for testing."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        db_path = tf.name
    store = DataStore(db_path)
    yield store
    Path(db_path).unlink(missing_ok=True)
    Path(f"{db_path}-wal").unlink(missing_ok=True)
    Path(f"{db_path}-shm").unlink(missing_ok=True)


@pytest.fixture
def test_config() -> StudyConfig:
    """Load default configuration with fast timeouts suitable for testing."""
    cfg = load_study_config("config/default.yaml")
    cfg.crawler.concurrency = 2
    cfg.crawler.dwell_time_seconds = 1.0
    cfg.crawler.navigation_timeout_seconds = 5.0
    cfg.crawler.min_domain_delay_seconds = 0.0
    cfg.crawler.contact_email = "test-researcher@university.ac.uk"
    return cfg
