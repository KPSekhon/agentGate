from __future__ import annotations

import os
import pytest
import pytest_asyncio
from pathlib import Path


@pytest.fixture(autouse=True)
def _set_demo_mode(monkeypatch, tmp_path):
    """Ensure tests run in demo mode with a temp database."""
    monkeypatch.setenv("AGENTGATE_MODE", "demo")
    monkeypatch.setenv("AGENTGATE_DB_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("AGENTGATE_POLICY_DIR", str(Path(__file__).parent.parent / "policies"))


@pytest.fixture
def policy_dir():
    return Path(__file__).parent.parent / "policies"
