from pathlib import Path

import api.validator as validator_module


def _write_minimal_files(base_dir: Path):
    audio_path = base_dir / "input.wav"
    text_path = base_dir / "input.txt"
    audio_path.write_bytes(b"RIFFFAKEAUDIO")
    text_path.write_text("hello world", encoding="utf-8")
    return str(audio_path), str(text_path)


def _write_input_files(base_dir: Path, text: str):
    audio_path = base_dir / "input.wav"
    text_path = base_dir / "input.txt"
    audio_path.write_bytes(b"RIFFFAKEAUDIO")
    text_path.write_text(text, encoding="utf-8")
    return str(audio_path), str(text_path)


def _mock_asr_result():
    return {
        "text": "hello world",
        "word_timestamps": [
            {"value": "hello", "start": 0.0, "end": 0.4},
            {"value": "world", "start": 0.5, "end": 0.9},
        ],
    }


def _mock_diff():
    return [
        {"word": "hello", "status": "correct", "ref_index": 0, "trans_index": 0},
        {"word": "world", "status": "correct", "ref_index": 1, "trans_index": 1},
    ], "hello world"


def _mock_diff_with_comma():
    return [
        {"word": "hello", "status": "correct", "ref_index": 0, "trans_index": 0},
        {"word": ",", "status": "omitted", "ref_index": 1, "trans_index": None},
        {"word": "world", "status": "correct", "ref_index": 2, "trans_index": 1},
    ], "hello world"


def test_align_and_validate_falls_back_to_asr_only(tmp_path, monkeypatch):
    mfa_base_dir = tmp_path / "mfa"
    mfa_runtime_dir = tmp_path / "mfa_runtime"
    (mfa_base_dir / "data").mkdir(parents=True)
    mfa_runtime_dir.mkdir(parents=True)
    audio_path, text_path = _write_minimal_files(tmp_path)

    monkeypatch.setattr(validator_module, "MFA_BASE_DIR", mfa_base_dir)
    monkeypatch.setattr(validator_module, "MFA_RUNTIME_DIR", mfa_runtime_dir)
    monkeypatch.setattr(validator_module, "transcribe_audio_with_details", lambda _path: _mock_asr_result())
    monkeypatch.setattr(validator_module, "compare_text", lambda _ref, _hyp: _mock_diff())

    def fake_run_single_alignment_gen(accent, _conf, _run_id, _docker_input_dir):
        yield {"type": "result", "data": (accent, None)}

    monkeypatch.setattr(validator_module, "run_single_alignment_gen", fake_run_single_alignment_gen)

    updates = list(validator_module.align_and_validate_gen(audio_path, text_path, accents=["US_ARPA"]))
    result = [event for event in updates if event["type"] == "result"][-1]["data"]

    assert result["summary"]["asr_only"] is True
    assert result["summary"]["total"] == 2
    assert result["summary"]["correct"] == 2
    assert result["mfa_word_gaps"] == []


def test_align_and_validate_uses_textgrid_when_available(tmp_path, monkeypatch):
    mfa_base_dir = tmp_path / "mfa"
    mfa_runtime_dir = tmp_path / "mfa_runtime"
    (mfa_base_dir / "data").mkdir(parents=True)
    mfa_runtime_dir.mkdir(parents=True)
    audio_path, text_path = _write_minimal_files(tmp_path)

    tg_path = tmp_path / "input.TextGrid"
    tg_path.write_text(
        'File type = "ooTextFile"\nObject class = "TextGrid"\nname = "words"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(validator_module, "MFA_BASE_DIR", mfa_base_dir)
    monkeypatch.setattr(validator_module, "MFA_RUNTIME_DIR", mfa_runtime_dir)
    monkeypatch.setattr(validator_module, "transcribe_audio_with_details", lambda _path: _mock_asr_result())
    monkeypatch.setattr(validator_module, "compare_text", lambda _ref, _hyp: _mock_diff())

    def fake_run_single_alignment_gen(accent, _conf, _run_id, _docker_input_dir):
        yield {"type": "result", "data": (accent, tg_path)}

    def fake_analyze_word_pronunciation(item, *_args, **_kwargs):
        analyzed = item.copy()
        trans_index = analyzed.get("trans_index")
        if trans_index is not None:
            analyzed["start"] = round(trans_index * 0.5, 3)
            analyzed["end"] = round((trans_index * 0.5) + 0.4, 3)
        analyzed["status"] = "correct"
        return analyzed

    monkeypatch.setattr(validator_module, "run_single_alignment_gen", fake_run_single_alignment_gen)
    monkeypatch.setattr(validator_module, "analyze_word_pronunciation", fake_analyze_word_pronunciation)

    updates = list(validator_module.align_and_validate_gen(audio_path, text_path, accents=["US_ARPA"]))
    result = [event for event in updates if event["type"] == "result"][-1]["data"]

    assert result["summary"]["total"] == 2
    assert result["summary"]["correct"] == 2
    assert "asr_only" not in result["summary"]
    assert "TextGrid" in result.get("textgrid_content", "")


def test_align_and_validate_reuses_cached_result(tmp_path, monkeypatch):
    mfa_base_dir = tmp_path / "mfa"
    mfa_runtime_dir = tmp_path / "mfa_runtime"
    mfa_base_dir.mkdir(parents=True)
    mfa_runtime_dir.mkdir(parents=True)
    audio_path, text_path = _write_minimal_files(tmp_path)

    tg_path = tmp_path / "input.TextGrid"
    tg_path.write_text(
        'File type = "ooTextFile"\nObject class = "TextGrid"\nname = "words"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(validator_module, "MFA_BASE_DIR", mfa_base_dir)
    monkeypatch.setattr(validator_module, "MFA_RUNTIME_DIR", mfa_runtime_dir)
    monkeypatch.setattr(validator_module, "transcribe_audio_with_details", lambda _path: _mock_asr_result())
    monkeypatch.setattr(validator_module, "compare_text", lambda _ref, _hyp: _mock_diff())

    def fake_run_single_alignment_gen(accent, _conf, _run_id, _docker_input_dir):
        yield {"type": "result", "data": (accent, tg_path)}

    def fake_analyze_word_pronunciation(item, *_args, **_kwargs):
        analyzed = item.copy()
        analyzed["status"] = "correct"
        return analyzed

    monkeypatch.setattr(validator_module, "run_single_alignment_gen", fake_run_single_alignment_gen)
    monkeypatch.setattr(validator_module, "analyze_word_pronunciation", fake_analyze_word_pronunciation)

    first_updates = list(validator_module.align_and_validate_gen(audio_path, text_path, accents=["US_ARPA"]))
    first_result = [event for event in first_updates if event["type"] == "result"][-1]["data"]
    assert first_result["summary"]["cached"] is False

    def fail_if_called(_path):
        raise AssertionError("ASR should not run when cache is hit")

    monkeypatch.setattr(validator_module, "transcribe_audio_with_details", fail_if_called)

    second_updates = list(validator_module.align_and_validate_gen(audio_path, text_path, accents=["US_ARPA"]))
    second_result = [event for event in second_updates if event["type"] == "result"][-1]["data"]
    assert second_result["summary"]["cached"] is True
    assert second_result["meta"]["cache"]["hit"] is True


def test_align_and_validate_prefers_mfa_for_pause_timing(tmp_path, monkeypatch):
    mfa_base_dir = tmp_path / "mfa"
    mfa_runtime_dir = tmp_path / "mfa_runtime"
    (mfa_base_dir / "data").mkdir(parents=True)
    mfa_runtime_dir.mkdir(parents=True)
    audio_path, text_path = _write_input_files(tmp_path, "hello, world")

    tg_path = tmp_path / "input.TextGrid"
    tg_path.write_text(
        'File type = "ooTextFile"\nObject class = "TextGrid"\nname = "words"\n',
        encoding="utf-8",
    )

    asr_result = {
        "text": "hello world",
        "word_timestamps": [
            {"value": "hello", "start": 0.0, "end": 0.3},
            {"value": "world", "start": 1.1, "end": 1.4},
        ],
    }
    base_words = [
        {"word": "hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.7, "end": 1.0},
    ]

    monkeypatch.setattr(validator_module, "MFA_BASE_DIR", mfa_base_dir)
    monkeypatch.setattr(validator_module, "MFA_RUNTIME_DIR", mfa_runtime_dir)
    monkeypatch.setattr(validator_module, "transcribe_audio_with_details", lambda _path: asr_result)
    monkeypatch.setattr(validator_module, "compare_text", lambda _ref, _hyp: _mock_diff_with_comma())
    monkeypatch.setattr(validator_module, "read_textgrid_words", lambda _path: base_words)
    monkeypatch.setattr(validator_module, "read_textgrid_phones", lambda _path: [])

    def fake_run_single_alignment_gen(accent, _conf, _run_id, _docker_input_dir):
        yield {"type": "result", "data": (accent, tg_path)}

    def fake_analyze_word_pronunciation(item, *_args, **_kwargs):
        analyzed = item.copy()
        analyzed["status"] = item["status"]
        return analyzed

    monkeypatch.setattr(validator_module, "run_single_alignment_gen", fake_run_single_alignment_gen)
    monkeypatch.setattr(validator_module, "analyze_word_pronunciation", fake_analyze_word_pronunciation)

    updates = list(validator_module.align_and_validate_gen(audio_path, text_path, accents=["US_ARPA"]))
    result = [event for event in updates if event["type"] == "result"][-1]["data"]

    assert result["mfa_word_gaps"] == [
        {
            "after_word": "hello",
            "before_word": "world",
            "start": 0.5,
            "end": 0.7,
            "duration": 0.2,
            "source": "mfa",
        }
    ]
    assert result["pauses"][0]["timing_source"] == "mfa"
    assert result["pauses"][0]["duration"] == 0.2
    assert result["pauses"][0]["status"] == "correct_pause"
    assert result["speech_rate_scale"] == 0.8


def test_run_single_alignment_uses_configurable_num_jobs(tmp_path, monkeypatch):
    mfa_runtime_dir = tmp_path / "mfa_runtime"
    mfa_runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(validator_module, "MFA_RUNTIME_DIR", mfa_runtime_dir)
    monkeypatch.setenv("PTE_MFA_NUM_JOBS", "3")

    run_id = "testrun1"
    accent = "US_ARPA"
    tg_dir = mfa_runtime_dir / run_id / "output" / accent
    tg_dir.mkdir(parents=True, exist_ok=True)
    (tg_dir / "input.TextGrid").write_text(
        'File type = "ooTextFile"\nObject class = "TextGrid"\nname = "words"\n',
        encoding="utf-8",
    )

    captured = {}

    class FakeProcess:
        def __init__(self, cmd):
            captured["cmd"] = cmd
            self.returncode = 0

        def communicate(self, timeout=None):
            return b"", b""

        def poll(self):
            return self.returncode

    def fake_popen(cmd, **_kwargs):
        return FakeProcess(cmd)

    monkeypatch.setattr(validator_module.subprocess, "Popen", fake_popen)

    events = list(
        validator_module.run_single_alignment_gen(
            accent,
            validator_module.ACCENTS_CONFIG[accent],
            run_id,
            f"/runtime/{run_id}/input",
        )
    )
    result = [event for event in events if event["type"] == "result"][-1]["data"]

    assert result[1] == tg_dir / "input.TextGrid"
    assert "--num_jobs" in captured["cmd"]
    num_jobs_index = captured["cmd"].index("--num_jobs")
    assert captured["cmd"][num_jobs_index + 1] == "3"
