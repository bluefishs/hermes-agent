"""Unit tests for hermes_cli.sync_soul."""
from __future__ import annotations

import io
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hermes_cli import sync_soul


@pytest.fixture
def soul_source(tmp_path: Path) -> Path:
    p = tmp_path / "SOUL.md"
    p.write_text(
        "---\ntitle: TestSoul\nversion: 1.0\n---\n\n# Test\n",
        encoding="utf-8",
    )
    return p


def _fake_run(stdout: bytes = b"", returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=b"")


def test_sync_no_drift_when_runtime_matches(monkeypatch, soul_source):
    matching = soul_source.read_text(encoding="utf-8").encode("utf-8")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "docker" and cmd[1] == "exec":
            return _fake_run(stdout=matching)
        if cmd[0] == "docker" and cmd[1] == "cp":
            pytest.fail("docker cp must not be invoked when runtime matches")
        return _fake_run()

    monkeypatch.setattr(sync_soul.subprocess, "run", fake_run)
    reports = sync_soul.sync(soul_source, ["c1"], apply=True)
    assert len(reports) == 1
    assert reports[0].differs is False
    assert reports[0].applied is False


def test_sync_drift_dry_run_does_not_call_cp(monkeypatch, soul_source):
    cp_called = {"yes": False}

    def fake_run(cmd, **kwargs):
        if cmd[0] == "docker" and cmd[1] == "exec":
            return _fake_run(stdout=b"# different content")
        if cmd[0] == "docker" and cmd[1] == "cp":
            cp_called["yes"] = True
            return _fake_run()
        return _fake_run()

    monkeypatch.setattr(sync_soul.subprocess, "run", fake_run)
    reports = sync_soul.sync(soul_source, ["c1"], apply=False)
    assert reports[0].differs is True
    assert reports[0].applied is False
    assert cp_called["yes"] is False
    assert reports[0].diff_lines, "expected unified diff output"


def test_sync_drift_apply_calls_docker_cp(monkeypatch, soul_source):
    cp_calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        if cmd[0] == "docker" and cmd[1] == "exec":
            return _fake_run(stdout=b"# old runtime")
        if cmd[0] == "docker" and cmd[1] == "cp":
            cp_calls.append(list(cmd))
            return _fake_run(returncode=0)
        return _fake_run()

    monkeypatch.setattr(sync_soul.subprocess, "run", fake_run)
    reports = sync_soul.sync(soul_source, ["ck-hermes-gateway", "ck-hermes-web"], apply=True)
    assert all(r.applied for r in reports)
    assert len(cp_calls) == 2
    assert cp_calls[0][0] == "docker"
    assert cp_calls[0][1] == "cp"
    assert cp_calls[0][3].endswith(":/opt/data/SOUL.md")


def test_sync_apply_failure_reports_error(monkeypatch, soul_source):
    def fake_run(cmd, **kwargs):
        if cmd[0] == "docker" and cmd[1] == "exec":
            return _fake_run(stdout=b"# old")
        if cmd[0] == "docker" and cmd[1] == "cp":
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout=b"", stderr=b"no such container",
            )
        return _fake_run()

    monkeypatch.setattr(sync_soul.subprocess, "run", fake_run)
    reports = sync_soul.sync(soul_source, ["missing"], apply=True)
    assert reports[0].differs is True
    assert reports[0].applied is False
    assert any("apply-error" in line for line in reports[0].diff_lines)


def test_sync_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        sync_soul.sync(tmp_path / "no-such.md", ["c1"], apply=False)


def test_main_dry_run_default(monkeypatch, soul_source, capsys):
    monkeypatch.setattr(sync_soul.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "docker" and cmd[1] == "exec":
            return _fake_run(stdout=b"# old")
        return _fake_run()

    monkeypatch.setattr(sync_soul.subprocess, "run", fake_run)
    rc = sync_soul.main(["--source", str(soul_source), "--containers", "c1"])
    out = capsys.readouterr().out
    assert rc == 0  # dry-run never errors on drift
    assert "[DRY-RUN]" in out
    assert "[DRIFT]" in out
    assert "[HINT]" in out


def test_main_apply_returns_1_when_unresolved(monkeypatch, soul_source, capsys):
    monkeypatch.setattr(sync_soul.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "docker" and cmd[1] == "exec":
            return _fake_run(stdout=b"# old")
        if cmd[0] == "docker" and cmd[1] == "cp":
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout=b"", stderr=b"err")
        return _fake_run()

    monkeypatch.setattr(sync_soul.subprocess, "run", fake_run)
    rc = sync_soul.main([
        "--source", str(soul_source), "--containers", "c1", "--apply",
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[APPLY]" in out
    assert "[FAIL]" in out


def test_main_no_docker_returns_2(monkeypatch, soul_source, capsys):
    monkeypatch.setattr(sync_soul.shutil, "which", lambda _: None)
    rc = sync_soul.main(["--source", str(soul_source)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "docker" in err.lower()
