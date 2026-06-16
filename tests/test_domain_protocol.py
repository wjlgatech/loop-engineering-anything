"""U9 Domain-protocol tests (plan-004 U9 Test scenarios).

The ``Domain`` plugin contract must be satisfiable by a concrete class
(``runtime_checkable``), and a refine-only domain that supplies no ``Factory``
(adopt-as-baseline, KTD5) must be valid -- so "no codegen" is expressible
without a controller branch.
"""

from __future__ import annotations

from loopeng.adapters.base import Factory, Judge, Verdict
from loopeng.domains import Domain


class _FakeJudge:
    def judge(self, tool_path: str) -> Verdict:
        return Verdict(grade="C", score=0.5, dims={}, safety_ok=True)


class _FakeFactory:
    def generate(self, target: str, goal: str):  # pragma: no cover - shape only
        raise NotImplementedError


class GeneratingDomain:
    name = "fake-generating"
    dependencies = frozenset({"cli-judge"})

    def classify(self, target: str) -> bool:
        return target.startswith("gen://")

    def factory(self) -> Factory | None:
        return _FakeFactory()

    def judge(self) -> Judge:
        return _FakeJudge()


class RefineOnlyDomain:
    """Adopt-as-baseline: no Factory (KTD5)."""

    name = "fake-refine-only"
    dependencies = frozenset({"cli-judge"})

    def classify(self, target: str) -> bool:
        return target.startswith("adopt://")

    def factory(self) -> Factory | None:
        return None

    def judge(self) -> Judge:
        return _FakeJudge()


def test_generating_domain_satisfies_protocol():
    d = GeneratingDomain()
    assert isinstance(d, Domain)
    assert d.classify("gen://x") is True
    assert isinstance(d.factory(), Factory)
    assert isinstance(d.judge(), Judge)


def test_refine_only_domain_is_valid_with_no_factory():
    """A Domain with an adopt-as-baseline actuator but no Factory is valid."""
    d = RefineOnlyDomain()
    assert isinstance(d, Domain)
    assert d.factory() is None  # refine-only, expressible without a controller branch
    assert isinstance(d.judge(), Judge)


def test_classify_is_target_specific():
    gen, refine = GeneratingDomain(), RefineOnlyDomain()
    assert gen.classify("gen://a") and not gen.classify("adopt://a")
    assert refine.classify("adopt://a") and not refine.classify("gen://a")
