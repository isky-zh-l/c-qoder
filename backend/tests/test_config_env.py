import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import BACKEND_DIR


def test_app_env_production_loads_override_file():
    production = BACKEND_DIR / ".env.production"
    if production.exists():
        pytest.skip("refusing to overwrite an existing production env file")
    production.write_text(
        "SITE_TITLE=Production Env Check\nAPP_VERSION=9.9.9\n",
        encoding="utf-8",
    )
    try:
        env = os.environ.copy()
        env["APP_ENV"] = "production"
        env.pop("SITE_TITLE", None)
        env.pop("APP_VERSION", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from app.config import get_settings; "
                "s = get_settings(); "
                "print(s.site_title); print(s.app_version)",
            ],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().splitlines() == [
            "Production Env Check",
            "9.9.9",
        ]
    finally:
        production.unlink(missing_ok=True)
