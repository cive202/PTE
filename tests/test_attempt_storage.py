import json
from pathlib import Path

import api.app as app_module
import api.file_utils as file_utils


def test_get_paired_paths_creates_feature_named_attempt_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(file_utils, "CORPUS_DIR", tmp_path)

    audio_path, text_path = file_utils.get_paired_paths("Read Aloud")
    audio_file = Path(audio_path)
    text_file = Path(text_path)

    assert audio_file.parent == text_file.parent
    assert audio_file.parent.exists()
    assert audio_file.parent.name.startswith("read_aloud_")
    assert audio_file.stem == text_file.stem == audio_file.parent.name
    assert audio_file.suffix == ".wav"
    assert text_file.suffix == ".txt"


def test_get_temp_filepath_uses_attempt_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(file_utils, "CORPUS_DIR", tmp_path)
    attempt_dir = tmp_path / "read_aloud_20260211_190000_abcdef"

    temp_path = Path(
        file_utils.get_temp_filepath("upload", "tmp", directory=str(attempt_dir))
    )

    assert temp_path.parent == attempt_dir
    assert temp_path.name.startswith("upload_")
    assert temp_path.suffix == ".tmp"


def test_persist_attempt_artifacts_writes_all_outputs(tmp_path):
    attempt_name = "read_aloud_20260211_190000_abcdef"
    attempt_dir = tmp_path / attempt_name
    attempt_dir.mkdir(parents=True, exist_ok=True)
    audio_path = attempt_dir / f"{attempt_name}.wav"
    audio_path.write_bytes(b"RIFFFAKE")

    source_output_root = tmp_path / "processed" / "mfa_runs" / "run1" / "output"
    accent_dir = source_output_root / "US_ARPA"
    accent_dir.mkdir(parents=True, exist_ok=True)
    (accent_dir / "alignment_analysis.csv").write_text("word,status\nhello,correct\n", encoding="utf-8")

    payload = {
        "words": [
            {"word": "hello", "observed_phones": ["HH", "AH0", "L", "OW1"]},
            {"word": "world"},
        ],
        "textgrid_content": "File type = \"ooTextFile\"",
        "meta": {
            "mfa_output_root": str(source_output_root),
        },
        "summary": {"total": 2, "correct": 1},
    }

    app_module._persist_attempt_artifacts(str(audio_path), payload, filename="check_result.json")

    result_file = attempt_dir / "analysis" / "check_result.json"
    phoneme_file = attempt_dir / "analysis" / "phoneme_data.json"
    textgrid_file = attempt_dir / "mfa" / "input.TextGrid"
    copied_csv = attempt_dir / "mfa" / "US_ARPA" / "alignment_analysis.csv"

    assert result_file.exists()
    assert phoneme_file.exists()
    assert textgrid_file.exists()
    assert copied_csv.exists()

    result_payload = json.loads(result_file.read_text(encoding="utf-8"))
    phoneme_payload = json.loads(phoneme_file.read_text(encoding="utf-8"))

    assert result_payload["summary"]["total"] == 2
    assert phoneme_payload["count"] == 1
    assert phoneme_payload["words"][0]["word"] == "hello"


def test_cleanup_force_removes_temp_files(tmp_path, monkeypatch):
    temp_file = tmp_path / "upload_a1b2c3.tmp"
    temp_file.write_text("temp", encoding="utf-8")
    monkeypatch.setattr(app_module, "KEEP_UPLOAD_ARTIFACTS", True)

    app_module._maybe_cleanup([str(temp_file)])
    assert temp_file.exists()

    app_module._maybe_cleanup([str(temp_file)], force=True)
    assert not temp_file.exists()
