from __future__ import annotations

from autodata_agent.core.config import Settings


def test_cors_origins_accepts_comma_separated_env(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "AUTODATA_CORS_ORIGINS",
        "https://demo.netlify.app, https://example.com",
    )

    settings = Settings(
        storage_dir=tmp_path / "runtime",
        upload_dir=tmp_path / "uploads",
    )

    assert settings.cors_origins == [
        "https://demo.netlify.app",
        "https://example.com",
    ]
