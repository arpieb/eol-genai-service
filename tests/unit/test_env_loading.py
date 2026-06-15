"""Tests for .env loading at the composition root (config.load_env)."""

import os

from eol_genai_service.config import Settings, load_env


def test_load_env_reads_a_local_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("EOL_ENVTEST_VAR=from_dotenv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EOL_ENVTEST_VAR", raising=False)

    load_env()
    assert os.environ["EOL_ENVTEST_VAR"] == "from_dotenv"


def test_real_env_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("EOL_ENVTEST_VAR=from_dotenv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EOL_ENVTEST_VAR", "from_real_env")

    load_env()  # override=False — must not clobber the real env var
    assert os.environ["EOL_ENVTEST_VAR"] == "from_real_env"


def test_settings_from_env_stays_pure_without_an_explicit_load(monkeypatch):
    # Settings.from_env() reads only the process env; it does not auto-load .env.
    monkeypatch.delenv("EOL_JWT", raising=False)
    assert Settings.from_env().eol_jwt is None
