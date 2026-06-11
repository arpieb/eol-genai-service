"""Unit tests for the deterministic repair rules (T016 / T031 / T034)."""

from eol_genai_service.repair.rules import (
    REPAIR_RULES,
    correct_value_slot,
    flip_direction,
    rollup_traversal,
    rule_version,
)
from eol_genai_service.shapes.registry import shape_version


def test_correct_value_slot_for_each_predicate_type():
    # "categorical queried as numeric → read object_term" (FR-005).
    assert correct_value_slot("categorical") == "object_term"
    assert correct_value_slot("measurement") == "normal_measurement"
    assert correct_value_slot("association") == "object_page"
    assert correct_value_slot("unknown") is None


def test_flip_direction_is_an_involution():
    assert flip_direction("subject_to_object") == "object_to_subject"
    assert flip_direction("object_to_subject") == "subject_to_object"
    assert flip_direction(flip_direction("subject_to_object")) == "subject_to_object"


def test_repair_rules_are_versioned():
    assert rule_version("categorical-as-numeric") == "1.0.0"
    assert rule_version("flip-association-direction") == "1.0.0"
    assert rule_version("missing-rollup") == "1.0.0"
    assert rule_version("nonexistent") is None
    assert len(REPAIR_RULES) == 3


def test_missing_rollup_supplies_the_parent_term_traversal():
    assert "parent_term|synonym_of*0.." in rollup_traversal()


def test_shape_registry_covers_all_modeled_shapes():
    for shape in (
        "single_fact",
        "categorical_attribute",
        "association",
        "aggregate_count",
        "lineage",
    ):
        assert shape_version(shape) is not None, shape
    assert shape_version("n_hop_chain") is None  # US-7, not modeled yet
