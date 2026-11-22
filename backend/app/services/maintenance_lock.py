BACKUP_LOCK_KEY = 0x43514F444552
WRITE_LOCK_SQL = "SELECT pg_try_advisory_lock_shared(:key)"
WRITE_XACT_LOCK_SQL = "SELECT pg_try_advisory_xact_lock_shared(:key)"
WRITE_UNLOCK_SQL = "SELECT pg_advisory_unlock_shared(:key)"
