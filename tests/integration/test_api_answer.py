"""FastAPI /v1/answer integration tests (T023), using the offline-fixture app."""

from fastapi.testclient import TestClient

from eol_genai_service.api.app import create_app

client = TestClient(create_app())


def test_post_answer_returns_quantitative_answer():
    resp = client.post("/v1/answer", json={"question": "how heavy is a sea otter?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "answer"
    assert body["statements"][0]["value"]["units"] == "kg"
    assert body["truncated"] is False


def test_post_answer_no_records():
    resp = client.post("/v1/answer", json={"question": "how heavy is a raccoon?"})
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "no_records"


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_empty_question_is_rejected_by_request_validation():
    resp = client.post("/v1/answer", json={"question": ""})
    assert resp.status_code == 422  # min_length=1 on AnswerRequest.question
