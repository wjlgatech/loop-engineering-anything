"""U3 router tests (plan U3 Test scenarios)."""

from __future__ import annotations

import pytest

from loopeng.config import Lane
from loopeng.router import route


def test_local_dir_is_codebase(tmp_path):
    d = route(str(tmp_path))
    assert d.lane is Lane.CODEBASE
    assert d.factory == "cli-anything"


def test_http_url_is_service():
    d = route("https://api.example.com")
    assert d.lane is Lane.SERVICE
    assert d.factory == "printing-press"


def test_har_file_is_service():
    d = route("/tmp/capture.har")
    assert d.lane is Lane.SERVICE
    assert d.reason == "HAR capture file"


def test_openapi_yaml_is_service():
    d = route("petstore.yaml")
    assert d.lane is Lane.SERVICE
    assert d.reason == "OpenAPI spec file"


def test_github_repo_url_is_codebase():
    d = route("https://github.com/owner/repo")
    assert d.lane is Lane.CODEBASE
    assert d.reason == "git repository URL"


def test_lane_override_wins_over_classification():
    d = route("https://github.com/owner/repo", forced_lane=Lane.SERVICE)
    assert d.lane is Lane.SERVICE
    assert "forced" in d.reason


def test_empty_target_raises():
    with pytest.raises(ValueError):
        route("   ")


def test_unclassifiable_target_raises_with_guidance():
    with pytest.raises(ValueError) as exc:
        route("just-some-bare-word")
    assert "--lane" in str(exc.value)


def test_existing_openapi_file_classified_as_service(tmp_path):
    spec = tmp_path / "openapi.json"
    spec.write_text("{}")
    d = route(str(spec))
    assert d.lane is Lane.SERVICE
