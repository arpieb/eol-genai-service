"""Unit tests for the deterministic repair rules (T016 / T031 / T034)."""

from eol_genai_service.repair.rules import (
    REPAIR_RULES,
    rollup_traversal,
    rule_version,
)
from eol_genai_service.shapes.registry import shape_version


def test_repair_rules_are_versioned():
    # categorical-as-numeric and flip-association-direction are obviated at build time (dual-slot
    # attribute shape / computed association_direction), so missing-rollup is the lone live rule.
    assert rule_version("missing-rollup") == "1.0.0"
    assert rule_version("categorical-as-numeric") is None
    assert rule_version("flip-association-direction") is None
    assert rule_version("nonexistent") is None
    assert len(REPAIR_RULES) == 1


def test_missing_rollup_supplies_the_parent_term_traversal():
    assert "parent_term|synonym_of*0.." in rollup_traversal()


def test_shape_registry_covers_all_modeled_shapes():
    for shape in (
        "attribute",
        "association",
        "aggregate_count",
        "lineage",
        "n_hop_chain",
    ):
        assert shape_version(shape) is not None, shape
    assert shape_version("not_a_real_shape") is None
