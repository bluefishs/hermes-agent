"""Happy-path tests for ck-adr-query skill (B2 Sprint A.1 acceptance)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "plans"
    / "ck-adr-query-skeleton"
    / "tools.py"
)


@pytest.fixture
def fixture_index() -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-04-28T00:00:00Z",
        "ckproject_root": "D:/CKProject",
        "total_adrs": 3,
        "total_collisions": 1,
        "adrs": [
            {
                "fqid": "CK_Missive#0006",
                "repo": "CK_Missive",
                "title": "pgvector 768D embedding",
                "status": "accepted",
                "lifecycle": "accepted",
                "date": "2026-02-25",
                "path": "D:/CKProject/CK_Missive/docs/adr/0006-pgvector.md",
            },
            {
                "fqid": "CK_AaaP#0014",
                "repo": "CK_AaaP",
                "title": "Hermes replaces OpenClaw",
                "status": "accepted",
                "lifecycle": "executing",
                "date": "2026-04-10",
                "path": "D:/CKProject/CK_AaaP/adrs/0014-hermes.md",
            },
            {
                "fqid": "CK_AaaP#0006",
                "repo": "CK_AaaP",
                "title": "Cross-repo collision sample",
                "status": "proposed",
                "lifecycle": "proposed",
                "date": "2026-04-20",
                "path": "D:/CKProject/CK_AaaP/adrs/0006-x.md",
            },
        ],
        "collisions": [
            {"number": 6, "fqids": ["CK_Missive#0006", "CK_AaaP#0006"]},
        ],
    }


@pytest.fixture
def tools_module(tmp_path, fixture_index, monkeypatch):
    index_path = tmp_path / "adr-index.json"
    index_path.write_text(json.dumps(fixture_index), encoding="utf-8")
    monkeypatch.setenv("ADR_INDEX_PATH", str(index_path))

    sys.modules.pop("ck_adr_query_tools", None)
    spec = importlib.util.spec_from_file_location("ck_adr_query_tools", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("ck_adr_query_tools", None)


def test_adr_search_finds_keyword(tools_module):
    payload = json.loads(tools_module.adr_search("pgvector"))
    assert payload["hits_count"] == 1
    assert payload["hits"][0]["fqid"] == "CK_Missive#0006"


def test_adr_search_filters_by_repo(tools_module):
    payload = json.loads(tools_module.adr_search("hermes", repo="CK_AaaP"))
    assert payload["hits_count"] == 1
    assert payload["hits"][0]["fqid"] == "CK_AaaP#0014"


def test_adr_search_no_match_returns_zero_hits(tools_module):
    payload = json.loads(tools_module.adr_search("nonexistent-xyz"))
    assert payload["hits_count"] == 0
    assert payload["hits"] == []


def test_adr_list_filters_by_lifecycle(tools_module):
    payload = json.loads(tools_module.adr_list(lifecycle="accepted"))
    assert payload["count"] == 1
    assert payload["items"][0]["fqid"] == "CK_Missive#0006"


def test_adr_list_filters_by_repo(tools_module):
    payload = json.loads(tools_module.adr_list(repo="CK_AaaP"))
    assert payload["count"] == 2


def test_adr_lifecycle_returns_status(tools_module):
    payload = json.loads(tools_module.adr_lifecycle("CK_Missive#0006"))
    assert payload["fqid"] == "CK_Missive#0006"
    assert payload["lifecycle"] == "accepted"
    assert payload["host_path"].endswith("0006-pgvector.md")


def test_adr_lifecycle_unknown_fqid_returns_error(tools_module):
    payload = json.loads(tools_module.adr_lifecycle("CK_FAKE#9999"))
    assert payload["error"] == "not_found"


def test_adr_collisions_reports_cross_repo(tools_module):
    payload = json.loads(tools_module.adr_collisions())
    assert payload["total_collisions"] == 1
    assert payload["collisions"][0]["number"] == 6
    assert "CK_Missive#0006" in payload["collisions"][0]["fqids"]


def test_adr_read_returns_host_path_with_note(tools_module):
    payload = json.loads(tools_module.adr_read("CK_AaaP#0014"))
    assert payload["fqid"] == "CK_AaaP#0014"
    assert payload["host_path"].endswith("0014-hermes.md")
    assert "container" in payload["note"].lower() or "host" in payload["note"].lower()


def test_index_missing_returns_structured_error(tmp_path, monkeypatch):
    monkeypatch.setenv("ADR_INDEX_PATH", str(tmp_path / "does-not-exist.json"))
    sys.modules.pop("ck_adr_query_tools", None)
    spec = importlib.util.spec_from_file_location("ck_adr_query_tools", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    payload = json.loads(module.adr_search("anything"))
    assert payload["error"] == "index_missing"
    sys.modules.pop("ck_adr_query_tools", None)


def test_register_all_registers_five_tools(tools_module):
    class FakeRegistry:
        def __init__(self):
            self.calls = []

        def register(self, **kwargs):
            self.calls.append(kwargs)

    reg = FakeRegistry()
    count = tools_module.register_all(reg)
    assert count == 5
    names = {c["name"] for c in reg.calls}
    assert names == {"adr_search", "adr_list", "adr_lifecycle", "adr_collisions", "adr_read"}
    for call in reg.calls:
        assert callable(call["handler"])
        assert callable(call["check_fn"])
        assert isinstance(call["description"], str) and call["description"]
