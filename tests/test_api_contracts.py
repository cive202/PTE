import io
import json

import api.app as app_module
import api.validator as validator_module


def test_dashboard_route(client):
    response = client.get("/")
    assert response.status_code == 200


def test_read_aloud_topics_contract(client):
    response = client.get("/speaking/read-aloud/get-topics")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "topics" in payload
    assert isinstance(payload["topics"], list)
    assert payload["topics"]


def test_repeat_sentence_task_contract(client):
    response = client.get("/speaking/repeat-sentence/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("text", "id", "topic", "audio_url"):
        assert required_key in payload


def test_grammar_proxy_contract(client, monkeypatch):
    class DummyResponse:
        status_code = 200
        text = json.dumps({"matches": ["ok"]})
        headers = {"Content-Type": "application/json"}

    def fake_post(url, json, timeout):  # noqa: A002 - mirror requests.post signature
        assert url == "http://localhost:8000/grammar"
        assert json == {"text": "hello world"}
        assert timeout == 10
        return DummyResponse()

    monkeypatch.setattr(app_module.requests, "post", fake_post)

    response = client.post("/api/grammar", json={"text": "hello world"})
    assert response.status_code == 200
    assert response.get_json() == {"matches": ["ok"]}


def test_check_stream_ndjson_contract(client, monkeypatch):
    def fake_convert_to_wav(_input_path, _output_path):
        return True

    def fake_align_and_validate_gen(_audio_path, _text_path, accents=None):
        yield {"type": "progress", "percent": 25, "message": "mock-progress"}
        yield {
            "type": "result",
            "data": {
                "words": [],
                "summary": {"total": 0, "correct": 0, "pause_penalty": 0, "pause_count": 0},
            },
        }

    monkeypatch.setattr(app_module, "convert_to_wav", fake_convert_to_wav)
    monkeypatch.setattr(validator_module, "align_and_validate_gen", fake_align_and_validate_gen)

    data = {
        "audio": (io.BytesIO(b"RIFFFAKEAUDIO"), "check.wav"),
        "text": "sample reference",
        "feature": "read_aloud",
    }
    response = client.post("/check_stream", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.mimetype == "application/x-ndjson"

    lines = [line for line in response.data.decode("utf-8").splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]
    assert events[0]["type"] == "progress"
    assert events[-1]["type"] == "result"
    assert "summary" in events[-1]["data"]


def test_swt_task_contract(client):
    response = client.get("/writing/summarize-written-text/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "passage", "recommended_word_range"):
        assert required_key in payload


def test_swt_categories_contract(client):
    response = client.get("/writing/summarize-written-text/get-categories")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "categories" in payload
    assert isinstance(payload["categories"], list)
    assert payload["categories"]


def test_swt_catalog_contract(client):
    response = client.get("/writing/summarize-written-text/get-catalog")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert payload["items"]


def test_write_essay_task_contract(client):
    response = client.get("/writing/write-essay/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "prompt", "recommended_word_range"):
        assert required_key in payload


def test_write_essay_categories_contract(client):
    response = client.get("/writing/write-essay/get-categories")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "categories" in payload
    assert isinstance(payload["categories"], list)
    assert payload["categories"]


def test_write_email_task_contract(client):
    response = client.get("/writing/write-email/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in (
        "id",
        "title",
        "topic",
        "difficulty",
        "prompt",
        "recipient",
        "tone",
        "recommended_word_range",
    ):
        assert required_key in payload


def test_write_email_categories_contract(client):
    response = client.get("/writing/write-email/get-categories")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "categories" in payload
    assert isinstance(payload["categories"], list)
    assert payload["categories"]


def test_write_essay_catalog_contract(client):
    response = client.get("/writing/write-essay/get-catalog")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert payload["items"]


def test_write_email_catalog_contract(client):
    response = client.get("/writing/write-email/get-catalog")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert payload["items"]


def test_retell_lecture_categories_contract(client):
    response = client.get("/retell-lecture/get-categories")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "categories" in payload
    assert isinstance(payload["categories"], list)
    assert payload["categories"]


def test_retell_lecture_catalog_contract(client):
    response = client.get("/retell-lecture/get-catalog")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert payload["items"]


def test_retell_lecture_task_contract(client):
    response = client.get("/retell-lecture/get-lecture?difficulty=easy")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("lecture_id", "audio_url", "title", "difficulty"):
        assert required_key in payload


def test_swt_score_contract(client):
    payload = {
        "prompt_id": "swt_001",
        "passage": (
            "Urban areas are warmer due to heat-absorbing surfaces and low tree cover, "
            "while reflective roofs and more trees help reduce peak temperatures and electricity demand."
        ),
        "response": (
            "Urban heat islands make cities hotter because dark surfaces absorb radiation, "
            "but adding trees and reflective materials can reduce heat and energy use."
        ),
    }
    response = client.post("/writing/summarize-written-text/score", json=payload)
    assert response.status_code == 200

    data = response.get_json()
    assert data["task"] == "summarize_written_text"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_write_essay_score_contract(client):
    essay_text = (
        "Remote work can increase flexibility and lower commuting stress for employees. "
        "However, full remote settings may reduce spontaneous collaboration and weaken team culture. "
        "A balanced hybrid model often captures benefits from both approaches. "
        "For example, focused tasks can be completed from home while strategic meetings happen in person. "
        "Therefore, organizations should choose role-specific policies instead of one rigid rule for all teams."
    )
    payload = {
        "prompt_id": "essay_001",
        "prompt": (
            "Some organizations believe remote work should remain the default model, while others "
            "argue employees should return to office-based work for collaboration and productivity."
        ),
        "response": essay_text,
    }

    response = client.post("/writing/write-essay/score", json=payload)
    assert response.status_code == 200

    data = response.get_json()
    assert data["task"] == "write_essay"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_write_email_score_contract(client):
    email_text = (
        "Dear Support Team,\n"
        "I am writing to request a replacement student ID card because mine was lost yesterday on campus. "
        "Could you please guide me on the required documents and fee? "
        "Thank you for your assistance.\n"
        "Kind regards,\n"
        "Sam"
    )
    payload = {
        "prompt_id": "email_001",
        "prompt": (
            "You lost your student ID card and need a replacement urgently. "
            "Write an email to support requesting the process and required documents."
        ),
        "response": email_text,
    }

    response = client.post("/writing/write-email/score", json=payload)
    assert response.status_code == 200

    data = response.get_json()
    assert data["task"] == "write_email"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)
