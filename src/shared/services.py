from __future__ import annotations

import os


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


ASR_GRAMMAR_BASE_URL = _normalize_base_url(
    os.environ.get("PTE_ASR_GRAMMAR_BASE_URL", "http://localhost:8000")
)
PHONEME_BASE_URL = _normalize_base_url(
    os.environ.get("PTE_PHONEME_BASE_URL", "http://localhost:8001")
)

ASR_SERVICE_URL = os.environ.get("PTE_ASR_SERVICE_URL", f"{ASR_GRAMMAR_BASE_URL}/asr")
GRAMMAR_SERVICE_URL = os.environ.get("PTE_GRAMMAR_SERVICE_URL", f"{ASR_GRAMMAR_BASE_URL}/grammar")
ASR_HEALTH_URL = os.environ.get("PTE_ASR_HEALTH_URL", f"{ASR_GRAMMAR_BASE_URL}/health")

PHONEME_SERVICE_URL = os.environ.get("PHONEME_SERVICE_URL", f"{PHONEME_BASE_URL}/phonemes")
PHONEME_HEALTH_URL = os.environ.get("PTE_PHONEME_HEALTH_URL", f"{PHONEME_BASE_URL}/health")

MFA_DOCKER_IMAGE = os.environ.get(
    "PTE_MFA_DOCKER_IMAGE",
    "mmcauliffe/montreal-forced-aligner:latest",
)

