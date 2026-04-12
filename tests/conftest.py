from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
async def _setup_db(tmp_path):
    """Configure a temp database for each test."""
    import backend.database as db_mod

    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    db_mod.configure(db_url)

    async with db_mod._get_engine().begin() as conn:
        await conn.run_sync(db_mod.Base.metadata.create_all)

    yield

    await db_mod._get_engine().dispose()
    db_mod._engine = None
    db_mod._async_session = None


@pytest.fixture
def policy_dir():
    return Path(__file__).parent.parent / "policies"
