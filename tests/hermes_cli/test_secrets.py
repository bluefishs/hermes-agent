"""Tests for hermes_cli/secrets.py."""
from __future__ import annotations

import pytest

from hermes_cli.secrets import read_secret


def test_reads_from_docker_secrets_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    (tmp_path / "MCP_SERVICE_TOKEN").write_text("from-file")
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "from-env")
    assert read_secret("MCP_SERVICE_TOKEN") == "from-file"


def test_file_wins_over_env_for_lowercase_name(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    (tmp_path / "mcp_service_token").write_text("from-file-lower")
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "from-env")
    assert read_secret("mcp_service_token") == "from-file-lower"


def test_falls_back_to_env_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "from-env")
    assert read_secret("MCP_SERVICE_TOKEN") == "from-env"


def test_required_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    monkeypatch.delenv("NONEXISTENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="not found"):
        read_secret("NONEXISTENT_SECRET")


def test_default_returned_when_not_required(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    monkeypatch.delenv("NONEXISTENT_SECRET", raising=False)
    assert read_secret("NONEXISTENT_SECRET", required=False, default="x") == "x"


def test_default_none_when_not_required(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    monkeypatch.delenv("NONEXISTENT_SECRET", raising=False)
    assert read_secret("NONEXISTENT_SECRET", required=False) is None


def test_strips_trailing_whitespace(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    (tmp_path / "MCP_SERVICE_TOKEN").write_text("with-newline\n")
    assert read_secret("MCP_SERVICE_TOKEN") == "with-newline"


def test_handles_uppercase_lookup_when_passed_lowercase(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    (tmp_path / "MCP_SERVICE_TOKEN").write_text("upper-on-disk")
    assert read_secret("mcp_service_token") == "upper-on-disk"


def test_env_var_lookup_uses_uppercase_only(tmp_path, monkeypatch):
    """Even when the caller passes a lowercase name, the env lookup is uppercase.

    Note: Windows env vars are case-insensitive at the OS level, so we test
    only the positive path here. The negative case (env-only-as-lowercase)
    can't be cleanly expressed cross-platform.
    """
    monkeypatch.setenv("HERMES_SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "env-upper")
    assert read_secret("mcp_service_token") == "env-upper"
