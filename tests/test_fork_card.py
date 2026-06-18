"""U1 ForkCard type tests (plan 2026-06-17)."""

from __future__ import annotations

import pytest

from loopeng.loop.fork_card import (
    UNRESOLVED,
    ForkCard,
    ForkCardParseError,
    ForkOption,
)


def _card(**over):
    base = dict(
        id="fork-1",
        options=[ForkOption("a", "Option A"), ForkOption("b", "Option B")],
        spec_clause="north-star §2: silent on storage backend",
        chosen_default="a",
    )
    base.update(over)
    return ForkCard(**base)


def test_round_trip_preserves_all_fields():
    card = _card(chosen_default=None, basis=UNRESOLVED, reversibility="irreversible", blast_radius="module")
    again = ForkCard.from_dict(card.to_dict())
    assert again == card
    assert again.chosen_default is None
    assert again.basis == UNRESOLVED


def test_round_trip_with_citation_basis():
    card = _card(basis=["kernel.yaml:12", "person-map:decision-7"])
    again = ForkCard.from_dict(card.to_dict())
    assert again.basis == ["kernel.yaml:12", "person-map:decision-7"]
    assert not again.is_unresolved


def test_rejects_unknown_reversibility():
    with pytest.raises(ForkCardParseError):
        _card(reversibility="sorta")


def test_rejects_unknown_blast_radius():
    with pytest.raises(ForkCardParseError):
        _card(blast_radius="galaxy")


def test_chosen_default_must_be_an_option_id():
    with pytest.raises(ForkCardParseError):
        _card(chosen_default="zzz")


def test_regime_defaults_to_headless():
    assert _card().regime == "headless"


def test_is_unresolved_sentinel():
    assert _card(chosen_default=None, basis=UNRESOLVED).is_unresolved
    assert _card(basis=[]).is_unresolved
    assert not _card(basis=["cite"]).is_unresolved


def test_from_dict_on_non_dict_raises_parse_error():
    with pytest.raises(ForkCardParseError):
        ForkCard.from_dict(["not", "a", "dict"])


def test_from_dict_missing_required_key_raises_parse_error():
    with pytest.raises(ForkCardParseError):
        ForkCard.from_dict({"options": [{"id": "a"}]})  # no 'id'


def test_from_dict_empty_options_raises_parse_error():
    with pytest.raises(ForkCardParseError):
        ForkCard.from_dict({"id": "x", "options": []})


def test_from_dict_bad_option_shape_raises_parse_error():
    with pytest.raises(ForkCardParseError):
        ForkCard.from_dict({"id": "x", "options": ["a", "b"]})


def test_from_dict_tolerates_missing_optional_fields():
    card = ForkCard.from_dict({"id": "x", "options": [{"id": "a"}]})
    assert card.chosen_default is None
    assert card.basis == UNRESOLVED
    assert card.options[0].label == "a"  # falls back to id
