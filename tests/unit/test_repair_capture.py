"""Repair-loop miss capture (T049 — research.md R8)."""

from eol_genai_service.repair.capture import MissCapture, RepairMiss


def test_records_misses_and_summarizes_by_shape():
    capture = MissCapture()
    capture.record(RepairMiss(question="q1", shape="association", detail="inverted"))
    capture.record(RepairMiss(question="q2", shape="association", detail="empty"))
    capture.record(RepairMiss(question="q3", shape="aggregate_count", detail="no rollup"))

    assert len(capture) == 3
    summary = capture.summary()
    assert summary["association"] == 2  # most common gap → prioritize a rule here
    assert summary["aggregate_count"] == 1


def test_empty_capture_has_empty_summary():
    capture = MissCapture()
    assert len(capture) == 0
    assert capture.summary() == {}
