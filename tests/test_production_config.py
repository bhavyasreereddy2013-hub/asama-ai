import os
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_production_requires_deployment_configuration():
    base_environment = os.environ.copy()
    base_environment.update(
        {
            "APP_ENV": "production",
            "JWT_SECRET_KEY": "test-secret-with-more-than-thirty-two-bytes",
            "DATABASE_URL": "sqlite:////tmp/asama-test.db",
            "SEED_DEMO_DATA": "false",
        }
    )

    for missing_setting in ("JWT_SECRET_KEY", "DATABASE_URL"):
        environment = base_environment.copy()
        environment.pop(missing_setting)
        result = subprocess.run(
            [sys.executable, "-c", "import app.config"],
            cwd=BACKEND_DIR,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert f"{missing_setting} must be configured in production" in result.stderr


def test_production_cannot_enable_demo_accounts():
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "production",
            "JWT_SECRET_KEY": "test-secret-with-more-than-thirty-two-bytes",
            "DATABASE_URL": "sqlite:////tmp/asama-test.db",
            "SEED_DEMO_DATA": "true",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "SEED_DEMO_DATA cannot be enabled in production" in result.stderr


def test_production_rejects_short_jwt_secret():
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "production",
            "JWT_SECRET_KEY": "too-short",
            "DATABASE_URL": "sqlite:////tmp/asama-test.db",
            "SEED_DEMO_DATA": "false",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "JWT_SECRET_KEY must contain at least 32 bytes" in result.stderr
