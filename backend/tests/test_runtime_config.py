import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import PUBLIC_ORIGIN_ERROR, load_app_base_url


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "APP_BASE_URL must be configured in deployment",
        "app.example.invalid",
        "https:///",
        "ftp://app.example.invalid",
        "https://name@app.example.invalid",
        "https://app.example.invalid/login",
        "https://app.example.invalid?source=example",
        "https://app.example.invalid#login",
        "https://app.example.invalid:invalid",
        "https://app.example.invalid:99999",
        "https://app.example.invalid:",
        "https://invalid host.example.invalid",
        "https://app.\nexample.invalid",
        "https://app.example.invalid\\example",
        "https://[invalid",
    ],
)
def test_invalid_public_origin_is_rejected(monkeypatch, value) -> None:
    if value is None:
        monkeypatch.delenv("APP_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("APP_BASE_URL", value)

    with pytest.raises(RuntimeError, match=re.escape(PUBLIC_ORIGIN_ERROR)):
        load_app_base_url()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://app.example.invalid", "https://app.example.invalid"),
        ("https://app.example.invalid/", "https://app.example.invalid"),
        (" HTTPS://APP.EXAMPLE.INVALID:443/ ", "https://app.example.invalid"),
        ("http://127.0.0.1:5173", "http://127.0.0.1:5173"),
        ("http://localhost:80/", "http://localhost"),
        ("http://[::1]:5173/", "http://[::1]:5173"),
    ],
)
def test_valid_public_origin_is_normalized(monkeypatch, value, expected) -> None:
    monkeypatch.setenv("APP_BASE_URL", value)

    assert load_app_base_url() == expected


def test_application_uses_validated_public_origin() -> None:
    from app.main import app

    assert app.state.app_base_url == "https://app.example.invalid"


def test_backend_rejects_placeholder_public_url() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "APP_BASE_URL": "APP_BASE_URL must be configured in deployment",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "APP_BASE_URL must be an absolute HTTP(S) origin" in result.stderr
