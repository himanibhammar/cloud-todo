"""
Pytest configuration and shared fixtures.

A temporary SQLite database is created for every test session and removed
afterwards. The developer's real database is never touched.
"""

import os
import tempfile
import pytest

from app import create_app


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    """Return a path to a temporary database file."""
    db_dir = tmp_path_factory.mktemp("testdb")
    return str(db_dir / "test_tasks.db")


@pytest.fixture(scope="session")
def app(tmp_db_path):
    """Create an application configured for testing."""
    test_app = create_app(
        test_config={
            "TESTING": True,
            "DATABASE_PATH": tmp_db_path,
        }
    )
    return test_app


@pytest.fixture(scope="session")
def client(app):
    """Return a test client for the application."""
    return app.test_client()
