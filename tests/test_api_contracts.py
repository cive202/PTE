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


def test_describe_image_task_contract(client):
    response = client.get("/describe-image/get-image")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("image_id", "image_url", "title", "difficulty", "chart_type", "timing"):
        assert required_key in payload
    assert isinstance(payload["timing"], dict)
    assert payload["timing"]["prep_seconds"] > 0
    assert payload["timing"]["response_seconds"] > 0


def test_describe_image_topics_contract(client):
    response = client.get("/speaking/describe-image/get-topics")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "images" in payload
    assert isinstance(payload["images"], list)
    assert payload["images"]
    assert "timing" in payload
    assert payload["timing"]["response_seconds"] > 0


def test_respond_to_a_situation_page(client):
    response = client.get("/speaking/respond-to-a-situation")
    assert response.status_code == 200


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
    assert "timing" in payload
    assert payload["timing"]["prep_seconds"] > 0
    assert payload["timing"]["response_seconds"] > 0
    first = payload["items"][0]
    for required_key in ("id", "title", "difficulty", "prompt_seconds_estimate", "prompt_word_count"):
        assert required_key in first


def test_retell_lecture_task_contract(client):
    response = client.get("/retell-lecture/get-lecture?difficulty=easy")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in (
        "lecture_id",
        "audio_url",
        "title",
        "difficulty",
        "timing",
        "prompt_duration_seconds",
        "prompt_word_count",
        "audio_source",
        "example_response",
        "tts",
    ):
        assert required_key in payload
    assert payload["timing"]["prep_seconds"] > 0
    assert payload["timing"]["response_seconds"] > 0
    assert payload["prompt_duration_seconds"] > 0
    assert payload["prompt_word_count"] > 0
    assert payload["audio_source"] == "edge_tts_dynamic"


def test_listening_sst_categories_contract(client):
    response = client.get("/listening/summarize-spoken-text/get-categories")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "categories" in payload
    assert isinstance(payload["categories"], list)
    assert payload["categories"]


def test_listening_sst_catalog_contract(client):
    response = client.get("/listening/summarize-spoken-text/get-catalog")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert payload["items"]


def test_listening_sst_task_contract(client):
    response = client.get("/listening/summarize-spoken-text/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "audio_url", "recommended_word_range"):
        assert required_key in payload


def test_listening_mcm_task_contract(client):
    response = client.get("/listening/multiple-choice-multiple/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "audio_url", "question", "options"):
        assert required_key in payload
    assert isinstance(payload["options"], list)
    assert payload["options"]


def test_listening_mcs_task_contract(client):
    response = client.get("/listening/multiple-choice-single/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "audio_url", "question", "options"):
        assert required_key in payload
    assert isinstance(payload["options"], list)
    assert payload["options"]


def test_listening_fib_task_contract(client):
    response = client.get("/listening/fill-in-the-blanks/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "audio_url", "passage_template", "blanks"):
        assert required_key in payload
    assert isinstance(payload["blanks"], list)
    assert payload["blanks"]


def test_listening_smw_task_contract(client):
    response = client.get("/listening/select-missing-word/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "audio_url", "question", "options"):
        assert required_key in payload
    assert isinstance(payload["options"], list)
    assert payload["options"]


def test_listening_sst_score_contract(client):
    task_response = client.get("/listening/summarize-spoken-text/get-task")
    assert task_response.status_code == 200
    task_payload = task_response.get_json()

    response_text = (
        "The lecture explains that sustainable farming protects ecosystems by saving water, "
        "reducing chemical use and improving biodiversity, while local food systems lower "
        "transport emissions and strengthen communities. It also says progress requires "
        "cooperation between policy makers, farmers and consumers to ensure long-term "
        "food security."
    )

    score_response = client.post(
        "/listening/summarize-spoken-text/score",
        json={
            "task_id": task_payload["id"],
            "response": response_text,
        },
    )
    assert score_response.status_code == 200

    data = score_response.get_json()
    assert data["task"] == "summarize_spoken_text"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_listening_mcm_score_contract(client):
    task_response = client.get("/listening/multiple-choice-multiple/get-task")
    assert task_response.status_code == 200
    task_payload = task_response.get_json()

    options = task_payload.get("options", [])
    selected = [options[0]["id"]] if options else []

    score_response = client.post(
        "/listening/multiple-choice-multiple/score",
        json={
            "task_id": task_payload["id"],
            "selected_options": selected,
        },
    )
    assert score_response.status_code == 200

    data = score_response.get_json()
    assert data["task"] == "multiple_choice_multiple"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_listening_mcs_score_contract(client):
    task_response = client.get("/listening/multiple-choice-single/get-task")
    assert task_response.status_code == 200
    task_payload = task_response.get_json()

    options = task_payload.get("options", [])
    selected = options[0]["id"] if options else ""

    score_response = client.post(
        "/listening/multiple-choice-single/score",
        json={
            "task_id": task_payload["id"],
            "selected_option": selected,
        },
    )
    assert score_response.status_code == 200

    data = score_response.get_json()
    assert data["task"] == "multiple_choice_single"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_listening_fib_score_contract(client):
    task_response = client.get("/listening/fill-in-the-blanks/get-task")
    assert task_response.status_code == 200
    task_payload = task_response.get_json()

    blanks = task_payload.get("blanks", [])
    responses = {str(item.get("id")): "test" for item in blanks}

    score_response = client.post(
        "/listening/fill-in-the-blanks/score",
        json={
            "task_id": task_payload["id"],
            "responses": responses,
        },
    )
    assert score_response.status_code == 200

    data = score_response.get_json()
    assert data["task"] == "fill_in_the_blanks"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_listening_smw_score_contract(client):
    task_response = client.get("/listening/select-missing-word/get-task")
    assert task_response.status_code == 200
    task_payload = task_response.get_json()

    options = task_payload.get("options", [])
    selected = options[0]["id"] if options else ""

    score_response = client.post(
        "/listening/select-missing-word/score",
        json={
            "task_id": task_payload["id"],
            "selected_option": selected,
        },
    )
    assert score_response.status_code == 200

    data = score_response.get_json()
    assert data["task"] == "select_missing_word"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_listening_smw_audio_masks_final_word(client, monkeypatch):
    captured = {}

    def fake_get_listening_task(task_type, topic=None, task_id=None, difficulty=None):
        assert task_type == "select_missing_word"
        assert task_id == "smw_test"
        return {
            "id": "smw_test",
            "transcript": "Sustainable systems improve food security.",
        }

    def fake_resolve_tts_request(feature="default"):
        assert feature == "listening"
        return {"speed": "x1.0", "voice": "en-AU-NatashaNeural", "provider": "edge", "rate": None, "pitch": None}

    def fake_synthesize_speech(text, speed, voice, provider, rate, pitch, feature):
        captured["text"] = text
        captured["feature"] = feature
        return b"FAKEAUDIO"

    monkeypatch.setattr(app_module, "get_listening_task", fake_get_listening_task)
    monkeypatch.setattr(app_module, "_resolve_tts_request", fake_resolve_tts_request)
    monkeypatch.setattr(app_module, "synthesize_speech", fake_synthesize_speech)

    response = client.get("/listening/select-missing-word/audio/smw_test")
    assert response.status_code == 200
    assert captured["feature"] == "listening"
    assert captured["text"].endswith("beep.")
    assert "security." not in captured["text"].lower()


def test_listening_smw_task_uses_present_word_distractors(client, monkeypatch):
    def fake_get_listening_task(task_type, topic=None, task_id=None, difficulty=None):
        assert task_type == "select_missing_word"
        return {
            "id": "smw_logic",
            "title": "SMW Logic",
            "topic": "General",
            "difficulty": "medium",
            "transcript": "Sustainable systems improve food security for communities.",
            "prompt_text": "Choose the missing ending word.",
            "question": "Which word is missing at the end?",
            "options": [
                {"id": "A", "text": "communities"},
                {"id": "B", "text": "weather"},
                {"id": "C", "text": "mountains"},
                {"id": "D", "text": "history"},
            ],
            "correct_option": "A",
        }

    def fake_resolve_tts_request(feature="default"):
        assert feature == "listening"
        return {"speed": "x1.0", "voice": "en-AU-NatashaNeural", "provider": "edge", "rate": None, "pitch": None}

    monkeypatch.setattr(app_module, "get_listening_task", fake_get_listening_task)
    monkeypatch.setattr(app_module, "_resolve_tts_request", fake_resolve_tts_request)

    response = client.get("/listening/select-missing-word/get-task?task_id=smw_logic")
    assert response.status_code == 200
    payload = response.get_json()

    options = payload.get("options", [])
    assert len(options) == 4

    by_id = {str(item["id"]).upper(): str(item["text"]).lower() for item in options}
    assert by_id["A"] == "communities"

    transcript_words = {
        "sustainable",
        "systems",
        "improve",
        "food",
        "security",
        "for",
        "communities",
    }
    distractors = [by_id["B"], by_id["C"], by_id["D"]]
    assert all(word in transcript_words for word in distractors)
    assert "communities" not in distractors


def test_listening_non_smw_audio_keeps_transcript(client, monkeypatch):
    captured = {}

    def fake_get_listening_task(task_type, topic=None, task_id=None, difficulty=None):
        assert task_type == "multiple_choice_single"
        assert task_id == "mcs_test"
        return {
            "id": "mcs_test",
            "transcript": "The correct answer remains unchanged.",
        }

    def fake_resolve_tts_request(feature="default"):
        assert feature == "listening"
        return {"speed": "x1.0", "voice": "en-AU-NatashaNeural", "provider": "edge", "rate": None, "pitch": None}

    def fake_synthesize_speech(text, speed, voice, provider, rate, pitch, feature):
        captured["text"] = text
        captured["feature"] = feature
        return b"FAKEAUDIO"

    monkeypatch.setattr(app_module, "get_listening_task", fake_get_listening_task)
    monkeypatch.setattr(app_module, "_resolve_tts_request", fake_resolve_tts_request)
    monkeypatch.setattr(app_module, "synthesize_speech", fake_synthesize_speech)

    response = client.get("/listening/multiple-choice-single/audio/mcs_test")
    assert response.status_code == 200
    assert captured["feature"] == "listening"
    assert captured["text"] == "The correct answer remains unchanged."


def test_reading_mcm_task_contract(client):
    response = client.get("/reading/multiple-choice-multiple/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "passage", "question", "options"):
        assert required_key in payload
    assert isinstance(payload["options"], list)
    assert payload["options"]


def test_reading_mcs_task_contract(client):
    response = client.get("/reading/multiple-choice-single/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "passage", "question", "options"):
        assert required_key in payload
    assert isinstance(payload["options"], list)
    assert payload["options"]


def test_reading_fib_dropdown_task_contract(client):
    response = client.get("/reading/fill-in-the-blanks-dropdown/get-task")
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)
    for required_key in ("id", "title", "topic", "difficulty", "passage_template", "blanks"):
        assert required_key in payload
    assert isinstance(payload["blanks"], list)
    assert payload["blanks"]


def test_reading_mcm_score_contract(client):
    task_response = client.get("/reading/multiple-choice-multiple/get-task")
    assert task_response.status_code == 200
    task_payload = task_response.get_json()

    options = task_payload.get("options", [])
    selected = [options[0]["id"]] if options else []

    score_response = client.post(
        "/reading/multiple-choice-multiple/score",
        json={
            "task_id": task_payload["id"],
            "selected_options": selected,
        },
    )
    assert score_response.status_code == 200

    data = score_response.get_json()
    assert data["task"] == "multiple_choice_multiple"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_reading_mcs_score_contract(client):
    task_response = client.get("/reading/multiple-choice-single/get-task")
    assert task_response.status_code == 200
    task_payload = task_response.get_json()

    options = task_payload.get("options", [])
    selected = options[0]["id"] if options else ""

    score_response = client.post(
        "/reading/multiple-choice-single/score",
        json={
            "task_id": task_payload["id"],
            "selected_option": selected,
        },
    )
    assert score_response.status_code == 200

    data = score_response.get_json()
    assert data["task"] == "multiple_choice_single"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


def test_reading_fib_dropdown_score_contract(client):
    task_response = client.get("/reading/fill-in-the-blanks-dropdown/get-task")
    assert task_response.status_code == 200
    task_payload = task_response.get_json()

    blanks = task_payload.get("blanks", [])
    responses = {}
    for item in blanks:
        blank_id = str(item.get("id"))
        options = item.get("options", [])
        responses[blank_id] = options[0] if options else ""

    score_response = client.post(
        "/reading/fill-in-the-blanks-dropdown/score",
        json={
            "task_id": task_payload["id"],
            "responses": responses,
        },
    )
    assert score_response.status_code == 200

    data = score_response.get_json()
    assert data["task"] == "fill_in_the_blanks_dropdown"
    assert "scores" in data
    assert "analysis" in data
    assert "feedback" in data
    assert isinstance(data["feedback"], list)


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
