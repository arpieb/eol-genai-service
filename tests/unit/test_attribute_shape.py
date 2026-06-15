"""Unit tests for the dual-slot attribute shape + mapper (EOL type-gap fix)."""

from eol_genai_service.contract import Predicate, Taxon
from eol_genai_service.shapes.attribute import build_attribute_query
from eol_genai_service.upstream.mappers import map_attribute_rows
from eol_genai_service.validator import validate

_SUBJ = Taxon(page_id=1, scientific_name="X")
_PRED = Predicate(
    uri="http://purl.obolibrary.org/obo/VT_0001259", name="body mass", type="measurement"
)


def test_query_reads_both_slots_passes_validator():
    q = build_attribute_query(328598, "PATO_0000014", 100)
    assert "t.normal_measurement AS amount" in q
    assert "object_term" in q
    assert "LIMIT 100" in q
    assert validate(q, {"PATO_0000014"}).ok


def test_numeric_slot_maps_to_quantitative():
    rows = [{"amount": 25.0, "units": "kg", "resource_name": "R"}]
    stmt = map_attribute_rows(rows, _SUBJ, _PRED)[0]
    assert stmt.value.kind == "quantitative"
    assert stmt.value.amount == 25.0


def test_term_slot_maps_to_categorical():
    rows = [{"amount": None, "term_uri": "http://x/obo/PATO_0000952", "term_name": "brown"}]
    stmt = map_attribute_rows(rows, _SUBJ, _PRED)[0]
    assert stmt.value.kind == "categorical"
    assert stmt.value.term.name == "brown"


def test_null_units_become_empty_string():
    rows = [{"amount": 1175.0, "units": None}]
    assert map_attribute_rows(rows, _SUBJ, _PRED)[0].value.units == ""


def test_rows_with_neither_slot_are_skipped():
    assert map_attribute_rows([{"amount": None, "term_uri": None}], _SUBJ, _PRED) == []
