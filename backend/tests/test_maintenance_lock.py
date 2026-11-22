from sqlalchemy import text

from app.db import engine
from app.services.maintenance_lock import BACKUP_LOCK_KEY
from helpers import API, error_code


def test_backup_lock_blocks_new_writes_and_releases(alice_client):
    with engine.connect() as lock_connection:
        lock_connection.execute(
            text("SELECT pg_advisory_lock(:key)"),
            {"key": BACKUP_LOCK_KEY},
        )
        blocked = alice_client.post(
            f"{API}/documents",
            json={"kind": "note", "title": "During Backup"},
        )
        assert blocked.status_code == 503
        assert error_code(blocked) == "maintenance_in_progress"
        assert blocked.headers["retry-after"] == "5"

        locked_again = alice_client.post(
            f"{API}/chapters",
            json={"name": "Should Not Exist"},
        )
        assert locked_again.status_code == 503

        lock_connection.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": BACKUP_LOCK_KEY},
        )

    allowed = alice_client.post(
        f"{API}/documents",
        json={"kind": "note", "title": "After Backup"},
    )
    assert allowed.status_code == 201, allowed.text