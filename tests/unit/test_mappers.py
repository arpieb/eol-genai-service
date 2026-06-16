"""Unit tests for neo4j→contract mapper edge cases (provenance + value-slot handling)."""

from eol_genai_service.contract import Predicate, Taxon
from eol_genai_service.upstream.mappers import map_attribute_rows

_SUBJECT = Taxon(page_id=1, scientific_name="x")
_PRED = Predicate(uri="u", name="body mass", type="measurement")


def test_attribute_row_without_provenance_maps_to_empty_provenance():
    # A measurement row carrying no resource/citation → provenance present but empty (the all-None
    # branch of _provenance), not a crash or a fabricated source.
    stmts = map_attribute_rows([{"amount": 5.0, "units": "kg"}], _SUBJECT, _PRED)
    assert stmts[0].value.kind == "quantitative"
    assert stmts[0].value.amount == 5.0
    assert stmts[0].provenance.resource is None
    assert stmts[0].provenance.citation is None


def test_attribute_row_with_null_units_presents_empty_string():
    # Real EOL rows can carry null units; the mapper presents "" rather than the string "None".
    stmts = map_attribute_rows([{"amount": 5.0, "units": None}], _SUBJECT, _PRED)
    assert stmts[0].value.units == ""


def test_attribute_row_with_neither_value_slot_is_skipped():
    # A row with neither a measurement nor an object_term contributes no statement (it isn't an
    # answer), rather than a malformed one.
    stmts = map_attribute_rows([{"amount": None, "term_uri": None}], _SUBJECT, _PRED)
    assert stmts == []
