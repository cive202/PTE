from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Staged data roots:
# - Canonical root (`data/`) for production structure
# - Legacy root (`data_2/`) for current runtime compatibility
CANONICAL_DATA_ROOT = Path(os.environ.get("PTE_DATA_ROOT", PROJECT_ROOT / "data"))
LEGACY_DATA_ROOT = PROJECT_ROOT / "data_2"

# Legacy and canonical user/runtime storage roots
LEGACY_USER_UPLOADS_DIR = PROJECT_ROOT / "corpus"
CANONICAL_USER_UPLOADS_DIR = CANONICAL_DATA_ROOT / "user_uploads"
CANONICAL_PROCESSED_ROOT = CANONICAL_DATA_ROOT / "processed"
CANONICAL_MFA_RUNTIME_DIR = CANONICAL_PROCESSED_ROOT / "mfa_runs"
CANONICAL_MFA_MODEL_DIR = CANONICAL_DATA_ROOT / "models" / "mfa"
LEGACY_MFA_MODEL_DIR = PROJECT_ROOT / "PTE_MFA_TESTER_DOCKER"

def _first_existing(candidates: Iterable[Path], fallback: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return fallback


# User-generated runtime files (write-target defaults to canonical `data/user_uploads`)
USER_UPLOADS_DIR = Path(
    os.environ.get(
        "PTE_USER_UPLOADS_DIR",
        str(CANONICAL_USER_UPLOADS_DIR),
    )
)

# MFA local model source (canonical under data/models/mfa with legacy fallback)
MFA_BASE_DIR = Path(
    os.environ.get(
        "PTE_MFA_BASE_DIR",
        str(_first_existing((CANONICAL_MFA_MODEL_DIR, LEGACY_MFA_MODEL_DIR), CANONICAL_MFA_MODEL_DIR)),
    )
)

# MFA generated runtime artifacts (run input/output) centralized under `data/processed`
MFA_RUNTIME_DIR = Path(
    os.environ.get(
        "PTE_MFA_RUNTIME_DIR",
        str(CANONICAL_MFA_RUNTIME_DIR),
    )
)


# Canonical targets (future)
CANONICAL_REFERENCE_ROOT = CANONICAL_DATA_ROOT / "reference"
CANONICAL_READ_ALOUD_JSON = CANONICAL_REFERENCE_ROOT / "read_aloud" / "references.json"
CANONICAL_REPEAT_SENTENCE_JSON = CANONICAL_REFERENCE_ROOT / "repeat_sentence" / "references.json"
CANONICAL_IMAGE_JSON = CANONICAL_REFERENCE_ROOT / "describe_image" / "references.json"
CANONICAL_LECTURE_JSON = CANONICAL_REFERENCE_ROOT / "retell_lecture" / "references.json"
CANONICAL_WRITING_ROOT = CANONICAL_REFERENCE_ROOT / "writing"
CANONICAL_WRITING_JSON = CANONICAL_WRITING_ROOT / "references.json"
CANONICAL_SWT_WRITING_JSON = CANONICAL_WRITING_ROOT / "summarize_written_text" / "references.json"
CANONICAL_ESSAY_WRITING_JSON = CANONICAL_WRITING_ROOT / "write_essay" / "references.json"
CANONICAL_EMAIL_WRITING_JSON = CANONICAL_WRITING_ROOT / "write_email" / "references.json"
CANONICAL_LISTENING_ROOT = CANONICAL_REFERENCE_ROOT / "listening"
CANONICAL_SST_LISTENING_JSON = CANONICAL_LISTENING_ROOT / "summarize_spoken_text" / "references.json"
CANONICAL_MCM_LISTENING_JSON = CANONICAL_LISTENING_ROOT / "multiple_choice_multiple" / "references.json"
CANONICAL_MCS_LISTENING_JSON = CANONICAL_LISTENING_ROOT / "multiple_choice_single" / "references.json"
CANONICAL_FIB_LISTENING_JSON = CANONICAL_LISTENING_ROOT / "fill_in_the_blanks" / "references.json"
CANONICAL_SMW_LISTENING_JSON = CANONICAL_LISTENING_ROOT / "select_missing_word" / "references.json"
CANONICAL_READING_ROOT = CANONICAL_REFERENCE_ROOT / "readingset"
CANONICAL_MCM_READING_JSON = CANONICAL_READING_ROOT / "multiple_choice_multiple" / "references.json"
CANONICAL_MCS_READING_JSON = CANONICAL_READING_ROOT / "multiple_choice_multiple" / "references_single.json"
CANONICAL_FIB_DROPDOWN_READING_JSON = (
    CANONICAL_READING_ROOT / "multiple_choice_multiple" / "references_fib_dropdown.json"
)
CANONICAL_IMAGES_DIR = CANONICAL_REFERENCE_ROOT / "describe_image" / "images"
CANONICAL_LECTURES_DIR = CANONICAL_REFERENCE_ROOT / "retell_lecture" / "lectures"
CANONICAL_REPEAT_SENTENCE_AUDIO_DIR = CANONICAL_REFERENCE_ROOT / "repeat_sentence" / "audio"
CANONICAL_READ_ALOUD_TEXTGRIDS_DIR = CANONICAL_REFERENCE_ROOT / "read_aloud" / "textgrids"

# Legacy paths (current)
LEGACY_READ_ALOUD_JSON = LEGACY_DATA_ROOT / "read_aloud_references.json"
LEGACY_REPEAT_SENTENCE_JSON = LEGACY_DATA_ROOT / "repeat_sentence_references.json"
LEGACY_IMAGE_JSON = LEGACY_DATA_ROOT / "image_references.json"
LEGACY_LECTURE_JSON = LEGACY_DATA_ROOT / "lecture_references.json"
LEGACY_WRITING_ROOT = LEGACY_DATA_ROOT / "writing"
LEGACY_WRITING_JSON = LEGACY_DATA_ROOT / "writing_references.json"
LEGACY_SWT_WRITING_JSON = LEGACY_WRITING_ROOT / "summarize_written_text_references.json"
LEGACY_ESSAY_WRITING_JSON = LEGACY_WRITING_ROOT / "write_essay_references.json"
LEGACY_EMAIL_WRITING_JSON = LEGACY_WRITING_ROOT / "write_email_references.json"
LEGACY_LISTENING_ROOT = LEGACY_DATA_ROOT / "listening"
LEGACY_SST_LISTENING_JSON = LEGACY_LISTENING_ROOT / "summarize_spoken_text" / "references.json"
LEGACY_MCM_LISTENING_JSON = LEGACY_LISTENING_ROOT / "multiple_choice_multiple" / "references.json"
LEGACY_MCS_LISTENING_JSON = LEGACY_LISTENING_ROOT / "multiple_choice_single" / "references.json"
LEGACY_FIB_LISTENING_JSON = LEGACY_LISTENING_ROOT / "fill_in_the_blanks" / "references.json"
LEGACY_SMW_LISTENING_JSON = LEGACY_LISTENING_ROOT / "select_missing_word" / "references.json"
LEGACY_READING_ROOT = LEGACY_DATA_ROOT / "readingset"
LEGACY_MCM_READING_JSON = LEGACY_READING_ROOT / "multiple_choice_multiple" / "references.json"
LEGACY_MCS_READING_JSON = LEGACY_READING_ROOT / "multiple_choice_multiple" / "references_single.json"
LEGACY_FIB_DROPDOWN_READING_JSON = (
    LEGACY_READING_ROOT / "multiple_choice_multiple" / "references_fib_dropdown.json"
)
LEGACY_IMAGES_DIR = LEGACY_DATA_ROOT / "images"
LEGACY_LECTURES_DIR = LEGACY_DATA_ROOT / "lectures"
LEGACY_REPEAT_SENTENCE_AUDIO_DIR = LEGACY_DATA_ROOT / "repeat-sentence-audio"
LEGACY_READ_ALOUD_TEXTGRIDS_DIR = LEGACY_DATA_ROOT / "read_aloud_textgrids"


READ_ALOUD_REFERENCE_FILE = _first_existing(
    (CANONICAL_READ_ALOUD_JSON, LEGACY_READ_ALOUD_JSON),
    LEGACY_READ_ALOUD_JSON,
)
REPEAT_SENTENCE_REFERENCE_FILE = _first_existing(
    (CANONICAL_REPEAT_SENTENCE_JSON, LEGACY_REPEAT_SENTENCE_JSON),
    LEGACY_REPEAT_SENTENCE_JSON,
)
IMAGE_REFERENCE_FILE = _first_existing(
    (CANONICAL_IMAGE_JSON, LEGACY_IMAGE_JSON),
    LEGACY_IMAGE_JSON,
)
LECTURE_REFERENCE_FILE = _first_existing(
    (CANONICAL_LECTURE_JSON, LEGACY_LECTURE_JSON),
    LEGACY_LECTURE_JSON,
)
WRITING_REFERENCE_FILE = _first_existing(
    (CANONICAL_WRITING_JSON, LEGACY_WRITING_JSON),
    CANONICAL_WRITING_JSON,
)
SWT_WRITING_REFERENCE_FILE = _first_existing(
    (
        CANONICAL_SWT_WRITING_JSON,
        LEGACY_SWT_WRITING_JSON,
        CANONICAL_WRITING_JSON,
        LEGACY_WRITING_JSON,
    ),
    CANONICAL_SWT_WRITING_JSON,
)
ESSAY_WRITING_REFERENCE_FILE = _first_existing(
    (
        CANONICAL_ESSAY_WRITING_JSON,
        LEGACY_ESSAY_WRITING_JSON,
        CANONICAL_WRITING_JSON,
        LEGACY_WRITING_JSON,
    ),
    CANONICAL_ESSAY_WRITING_JSON,
)
EMAIL_WRITING_REFERENCE_FILE = _first_existing(
    (
        CANONICAL_EMAIL_WRITING_JSON,
        LEGACY_EMAIL_WRITING_JSON,
        CANONICAL_WRITING_JSON,
        LEGACY_WRITING_JSON,
    ),
    CANONICAL_EMAIL_WRITING_JSON,
)
SST_LISTENING_REFERENCE_FILE = _first_existing(
    (CANONICAL_SST_LISTENING_JSON, LEGACY_SST_LISTENING_JSON),
    CANONICAL_SST_LISTENING_JSON,
)
MCM_LISTENING_REFERENCE_FILE = _first_existing(
    (CANONICAL_MCM_LISTENING_JSON, LEGACY_MCM_LISTENING_JSON),
    CANONICAL_MCM_LISTENING_JSON,
)
MCS_LISTENING_REFERENCE_FILE = _first_existing(
    (CANONICAL_MCS_LISTENING_JSON, LEGACY_MCS_LISTENING_JSON),
    CANONICAL_MCS_LISTENING_JSON,
)
FIB_LISTENING_REFERENCE_FILE = _first_existing(
    (CANONICAL_FIB_LISTENING_JSON, LEGACY_FIB_LISTENING_JSON),
    CANONICAL_FIB_LISTENING_JSON,
)
SMW_LISTENING_REFERENCE_FILE = _first_existing(
    (CANONICAL_SMW_LISTENING_JSON, LEGACY_SMW_LISTENING_JSON),
    CANONICAL_SMW_LISTENING_JSON,
)
MCM_READING_REFERENCE_FILE = _first_existing(
    (CANONICAL_MCM_READING_JSON, LEGACY_MCM_READING_JSON),
    CANONICAL_MCM_READING_JSON,
)
MCS_READING_REFERENCE_FILE = _first_existing(
    (CANONICAL_MCS_READING_JSON, LEGACY_MCS_READING_JSON),
    CANONICAL_MCS_READING_JSON,
)
FIB_DROPDOWN_READING_REFERENCE_FILE = _first_existing(
    (CANONICAL_FIB_DROPDOWN_READING_JSON, LEGACY_FIB_DROPDOWN_READING_JSON),
    CANONICAL_FIB_DROPDOWN_READING_JSON,
)
REFERENCE_DATA_DIR = _first_existing((CANONICAL_REFERENCE_ROOT, LEGACY_DATA_ROOT), LEGACY_DATA_ROOT)
IMAGES_DIR = _first_existing((CANONICAL_IMAGES_DIR, LEGACY_IMAGES_DIR), LEGACY_IMAGES_DIR)
LECTURES_DIR = _first_existing((CANONICAL_LECTURES_DIR, LEGACY_LECTURES_DIR), LEGACY_LECTURES_DIR)
REPEAT_SENTENCE_AUDIO_DIR = _first_existing(
    (CANONICAL_REPEAT_SENTENCE_AUDIO_DIR, LEGACY_REPEAT_SENTENCE_AUDIO_DIR),
    LEGACY_REPEAT_SENTENCE_AUDIO_DIR,
)
READ_ALOUD_TEXTGRIDS_DIR = _first_existing(
    (CANONICAL_READ_ALOUD_TEXTGRIDS_DIR, LEGACY_READ_ALOUD_TEXTGRIDS_DIR),
    LEGACY_READ_ALOUD_TEXTGRIDS_DIR,
)


def ensure_runtime_dirs() -> None:
    CANONICAL_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    CANONICAL_REFERENCE_ROOT.mkdir(parents=True, exist_ok=True)
    CANONICAL_WRITING_ROOT.mkdir(parents=True, exist_ok=True)
    (CANONICAL_WRITING_ROOT / "summarize_written_text").mkdir(parents=True, exist_ok=True)
    (CANONICAL_WRITING_ROOT / "write_essay").mkdir(parents=True, exist_ok=True)
    (CANONICAL_WRITING_ROOT / "write_email").mkdir(parents=True, exist_ok=True)
    CANONICAL_LISTENING_ROOT.mkdir(parents=True, exist_ok=True)
    (CANONICAL_LISTENING_ROOT / "summarize_spoken_text").mkdir(parents=True, exist_ok=True)
    (CANONICAL_LISTENING_ROOT / "multiple_choice_multiple").mkdir(parents=True, exist_ok=True)
    (CANONICAL_LISTENING_ROOT / "multiple_choice_single").mkdir(parents=True, exist_ok=True)
    (CANONICAL_LISTENING_ROOT / "fill_in_the_blanks").mkdir(parents=True, exist_ok=True)
    (CANONICAL_LISTENING_ROOT / "select_missing_word").mkdir(parents=True, exist_ok=True)
    CANONICAL_READING_ROOT.mkdir(parents=True, exist_ok=True)
    (CANONICAL_READING_ROOT / "multiple_choice_multiple").mkdir(parents=True, exist_ok=True)
    (CANONICAL_READING_ROOT / "multiple_choice_single").mkdir(parents=True, exist_ok=True)
    (CANONICAL_READING_ROOT / "fill_in_the_blanks_dropdown").mkdir(parents=True, exist_ok=True)
    CANONICAL_PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    USER_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    MFA_BASE_DIR.mkdir(parents=True, exist_ok=True)
    MFA_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
