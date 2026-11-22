from scripts import backup_restore


def test_database_tool_target_keeps_password_out_of_url():
    target, env = backup_restore._database_tool_target(
        "postgresql+psycopg://backup_user:super-secret@db.example:5432/notes"
    )
    assert "super-secret" not in target
    assert "***" not in target
    assert "backup_user" in target
    assert "db.example" in target
    assert env["PGPASSWORD"] == "super-secret"


def test_database_tool_target_without_password():
    target, env = backup_restore._database_tool_target(
        "postgresql+psycopg://postgres@127.0.0.1:55432/c_notes"
    )
    assert "postgres@127.0.0.1:55432/c_notes" in target
    assert "PGPASSWORD" not in env
