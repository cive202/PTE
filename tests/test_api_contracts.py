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
