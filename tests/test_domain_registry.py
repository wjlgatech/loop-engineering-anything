"""U11 domain-registry tests (plan-004 U11 Test scenarios).

The registry supersedes the router's hard-coded branching: software targets
resolve to the same lane/factory as before (R2), a forced name overrides
classification, an unknown target lists registered domains, and registering a
new domain routes its targets without touching ``router.py`` (R11).
"""

from __future__ import annotations

import pytest

from loopeng.config import Lane
from loopeng.domains import DomainRegistry, default_registry
from loopeng.domains.software import SOFTWARE_CODEBASE, SOFTWARE_SERVICE


@pytest.fixture
def reg():
    return default_registry()


# ----- software classification parity (R2) ----------------------------------


def test_local_dir_resolves_to_codebase(reg, tmp_path):
    d = reg.resolve(str(tmp_path))
    assert d.name == "software-codebase"
    assert d.lane is Lane.CODEBASE
    assert d.factory_key == "cli-anything"


def test_plain_https_url_resolves_to_service(reg):
    d = reg.resolve("https://api.example.com")
    assert d.name == "software-service"
    assert d.factory_key == "printing-press"


def test_git_repo_url_resolves_to_codebase(reg):
    assert reg.resolve("https://github.com/owner/repo").name == "software-codebase"


def test_har_and_openapi_resolve_to_service(reg):
    assert reg.resolve("/tmp/capture.har").lane is Lane.SERVICE
    assert reg.resolve("petstore.yaml").lane is Lane.SERVICE


def test_software_domains_are_mutually_exclusive(reg):
    """Each software target matches exactly one software domain (lane partition)."""
    target = "https://github.com/owner/repo"
    matches = [n for n in reg.names() if reg.resolve(target).name == n]
    assert reg.resolve(target).classify(target) is True
    assert SOFTWARE_SERVICE.classify(target) is False
    assert SOFTWARE_CODEBASE.classify(target) is True
    assert matches == ["software-codebase"]


# ----- forced + error paths -------------------------------------------------


def test_forced_domain_overrides_classification(reg):
    # A service-looking URL forced to the codebase domain by name.
    d = reg.resolve("https://api.example.com", forced="software-codebase")
    assert d.name == "software-codebase"


def test_unknown_forced_domain_lists_registered(reg):
    with pytest.raises(ValueError) as exc:
        reg.resolve("whatever", forced="no-such-domain")
    assert "software-service" in str(exc.value)


def test_unclassifiable_target_raises_listing_domains(reg):
    with pytest.raises(ValueError) as exc:
        reg.resolve("just-some-bare-word")
    msg = str(exc.value)
    assert "software-service" in msg and "software-codebase" in msg


# ----- extensibility (R11) --------------------------------------------------


def test_registering_new_domain_resolves_without_touching_router():
    """A newly registered domain claims its targets purely via classify()."""

    class WidgetDomain:
        name = "widget"
        dependencies = frozenset()

        def classify(self, target: str) -> bool:
            return target.startswith("widget://")

        def factory(self):
            return None

        def judge(self):
            return None

    reg = DomainRegistry()
    reg.register(WidgetDomain())
    reg.register(SOFTWARE_SERVICE)
    assert reg.resolve("widget://x").name == "widget"
    # Non-widget targets still fall through to the software domain.
    assert reg.resolve("https://api.example.com").name == "software-service"


def test_duplicate_registration_rejected(reg):
    with pytest.raises(ValueError):
        reg.register(SOFTWARE_SERVICE)  # already in default_registry
