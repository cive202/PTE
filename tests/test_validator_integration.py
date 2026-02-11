from pathlib import Path

import api.validator as validator_module


def _write_minimal_files(base_dir: Path):
    audio_path = base_dir / "input.wav"
    text_path = base_dir / "input.txt"
    audio_path.write_bytes(b"RIFFFAKEAUDIO")
    text_path.write_text("hello world", encoding="utf-8")
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
