import asyncio
import os
import time
from functools import lru_cache
from threading import Lock
from typing import Dict, List, Optional

import edge_tts

TTS_PROVIDER_EDGE = "edge"
DEFAULT_PROVIDER = TTS_PROVIDER_EDGE
DEFAULT_EDGE_VOICE = os.environ.get("PTE_TTS_DEFAULT_VOICE", "en-US-GuyNeural")
DEFAULT_SPEED = "x1.0"
DEFAULT_PITCH = "+0Hz"
VOICE_CACHE_TTL_SECONDS = int(os.environ.get("PTE_TTS_VOICE_CACHE_TTL_SECONDS", "3600"))
AUDIO_CACHE_SIZE = max(8, int(os.environ.get("PTE_TTS_AUDIO_CACHE_SIZE", "64")))

DEFAULT_VOICE_BY_LOCALE = {
    "en-au": "en-AU-NatashaNeural",
    "en-gb": "en-GB-SoniaNeural",
    "en-us": "en-US-GuyNeural",
}

FEATURE_DEFAULTS = {
    "retell_lecture": {
        "provider": TTS_PROVIDER_EDGE,
        "voice": "en-AU-NatashaNeural",
        "speed": "x1.0",
        "locale": "en-AU",
    },
    "default": {
        "provider": TTS_PROVIDER_EDGE,
        "voice": DEFAULT_EDGE_VOICE,
        "speed": DEFAULT_SPEED,
        "locale": "en-US",
    },
}

FEATURE_VOICE_PRESETS = {
    "retell_lecture": [
        "en-US-GuyNeural",
        "en-AU-NatashaNeural",
        "en-GB-SoniaNeural",
        "en-IN-PrabhatNeural",
    ],
    "default": [
        "en-AU-NatashaNeural",
        "en-GB-SoniaNeural",
        "en-US-GuyNeural",
    ],
}

SPEED_OPTIONS = [
    {"id": "x0.85", "label": "x0.85", "edge_rate": "-15%"},
    {"id": "x1.0", "label": "x1.0", "edge_rate": "+0%"},
    {"id": "x1.15", "label": "x1.15", "edge_rate": "+15%"},
]

SPEED_ALIAS_TO_CANONICAL = {
    "slow": "x0.85",
    "default": "x1.0",
    "normal": "x1.0",
    "fast": "x1.15",
}

SPEED_TO_EDGE_RATE = {entry["id"]: entry["edge_rate"] for entry in SPEED_OPTIONS}

_voice_cache_lock = Lock()
_voice_cache: Dict[str, object] = {
    "updated_at": 0.0,
    "voices": [],
}


def _build_cached_synthesizer(maxsize: int):
    @lru_cache(maxsize=maxsize)
    def _cached(text: str, voice: str, rate: str, pitch: str) -> bytes:
        return _run_async(_collect_audio_bytes(text, voice=voice, rate=rate, pitch=pitch))

    return _cached


_cached_edge_synth = _build_cached_synthesizer(AUDIO_CACHE_SIZE)


def _run_async(coro):
    """Run async coroutine in a dedicated event loop."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def normalize_provider(provider: Optional[str]) -> str:
    normalized = str(provider or DEFAULT_PROVIDER).strip().lower()
    if normalized != TTS_PROVIDER_EDGE:
        raise ValueError(f"Unsupported TTS provider: {provider}")
    return normalized


def normalize_speed_token(speed: Optional[str]) -> str:
    token = str(speed or DEFAULT_SPEED).strip().lower()
    if token in SPEED_ALIAS_TO_CANONICAL:
        return SPEED_ALIAS_TO_CANONICAL[token]
    if token in SPEED_TO_EDGE_RATE:
        return token
    if token.startswith("x"):
        try:
            multiplier = float(token[1:])
            if 0.5 <= multiplier <= 2.0:
                formatted = f"x{multiplier:.2f}".rstrip("0").rstrip(".")
                return formatted if formatted != "x1" else "x1.0"
        except ValueError:
            pass
    return DEFAULT_SPEED


def speed_token_to_edge_rate(speed: Optional[str]) -> str:
    normalized = normalize_speed_token(speed)
    if normalized in SPEED_TO_EDGE_RATE:
        return SPEED_TO_EDGE_RATE[normalized]
    try:
        multiplier = float(normalized[1:])
    except (TypeError, ValueError):
        multiplier = 1.0
    percent = int(round((multiplier - 1.0) * 100))
    return f"{percent:+d}%"


def speed_options() -> List[Dict[str, str]]:
    return [{"id": item["id"], "label": item["label"]} for item in SPEED_OPTIONS]


def feature_defaults(feature: Optional[str] = None) -> Dict[str, str]:
    normalized = str(feature or "default").strip().lower()
    return FEATURE_DEFAULTS.get(normalized, FEATURE_DEFAULTS["default"]).copy()


def feature_voice_presets(feature: Optional[str] = None) -> List[str]:
    normalized = str(feature or "default").strip().lower()
    presets = FEATURE_VOICE_PRESETS.get(normalized, FEATURE_VOICE_PRESETS["default"])
    return list(dict.fromkeys(presets))


def get_default_voice(
    *,
    locale: Optional[str] = None,
    feature: Optional[str] = None,
) -> str:
    defaults = feature_defaults(feature)
    if locale:
        normalized_locale = str(locale).strip().lower()
        for key, voice in DEFAULT_VOICE_BY_LOCALE.items():
            if normalized_locale.startswith(key):
                return voice
    return str(defaults.get("voice", DEFAULT_EDGE_VOICE))


def _normalize_voice_entry(raw_voice: Dict) -> Optional[Dict]:
    short_name = str(raw_voice.get("ShortName", "")).strip()
    locale = str(raw_voice.get("Locale", "")).strip()
    if not short_name or not locale:
        return None
    tag_info = raw_voice.get("VoiceTag") or {}
    personalities = tag_info.get("VoicePersonalities") or []
    content_categories = tag_info.get("ContentCategories") or []
    return {
        "short_name": short_name,
        "friendly_name": str(raw_voice.get("FriendlyName", short_name)).strip(),
        "display_name": str(raw_voice.get("DisplayName", "")).strip(),
        "locale": locale,
        "gender": str(raw_voice.get("Gender", "Unknown")).strip(),
        "personality": [str(item).strip() for item in personalities if str(item).strip()],
        "content_categories": [str(item).strip() for item in content_categories if str(item).strip()],
    }


def _preset_voice_entries(feature: Optional[str] = None) -> List[Dict]:
    entries: List[Dict] = []
    for short_name in feature_voice_presets(feature):
        locale = short_name.split("-")[0:2]
        locale_code = "-".join(locale) if len(locale) >= 2 else "en-US"
        entries.append(
            {
                "short_name": short_name,
                "friendly_name": short_name,
                "display_name": short_name,
                "locale": locale_code,
                "gender": "Unknown",
                "personality": [],
                "content_categories": [],
            }
        )
    return entries


async def _fetch_edge_voices() -> List[Dict]:
    raw_voices = await edge_tts.list_voices()
    voices = []
    for voice in raw_voices:
        normalized = _normalize_voice_entry(voice)
        if normalized:
            voices.append(normalized)
    voices.sort(key=lambda item: (item["locale"], item["short_name"]))
    return voices


def _filter_voices_by_locale(voices: List[Dict], locale: Optional[str] = None) -> List[Dict]:
    if not locale:
        return voices
    locale_filter = str(locale).strip().lower().replace("_", "-")
    return [
        voice
        for voice in voices
        if str(voice.get("locale", "")).lower().replace("_", "-").startswith(locale_filter)
    ]


def list_voices(
    *,
    provider: str = TTS_PROVIDER_EDGE,
    locale: Optional[str] = None,
    feature: Optional[str] = None,
    force_refresh: bool = False,
) -> List[Dict]:
    normalize_provider(provider)
    now = time.time()
    with _voice_cache_lock:
        cached_voices = list(_voice_cache.get("voices") or [])
        cached_at = float(_voice_cache.get("updated_at") or 0.0)
    should_refresh = force_refresh or not cached_voices or (now - cached_at) > VOICE_CACHE_TTL_SECONDS

    if should_refresh:
        try:
            fetched = _run_async(_fetch_edge_voices())
            with _voice_cache_lock:
                _voice_cache["voices"] = fetched
                _voice_cache["updated_at"] = now
            cached_voices = fetched
        except Exception:
            if not cached_voices:
                cached_voices = _preset_voice_entries(feature)

    filtered = _filter_voices_by_locale(cached_voices, locale)
    if filtered:
        return filtered
    fallback = _preset_voice_entries(feature)
    return _filter_voices_by_locale(fallback, locale) or fallback


def get_tts_capabilities(feature: Optional[str] = None) -> Dict:
    defaults = feature_defaults(feature)
    return {
        "providers": [TTS_PROVIDER_EDGE],
        "default_provider": defaults.get("provider", TTS_PROVIDER_EDGE),
        "default_voice": defaults.get("voice", DEFAULT_EDGE_VOICE),
        "default_speed": defaults.get("speed", DEFAULT_SPEED),
        "default_locale": defaults.get("locale", "en-US"),
        "speed_options": speed_options(),
        "voice_presets": feature_voice_presets(feature),
    }


async def _collect_audio_bytes(text: str, voice: str, rate: str, pitch: str = DEFAULT_PITCH) -> bytes:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    chunks = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            chunks.append(chunk.get("data", b""))
    return b"".join(chunks)


def synthesize_speech(
    text: str,
    *,
    speed: str = DEFAULT_SPEED,
    voice: Optional[str] = None,
    provider: str = TTS_PROVIDER_EDGE,
    rate: Optional[str] = None,
    pitch: str = DEFAULT_PITCH,
    feature: Optional[str] = None,
) -> bytes:
    normalized_provider = normalize_provider(provider)
    defaults = feature_defaults(feature)
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("No text provided for synthesis")

    selected_voice = str(voice or defaults.get("voice") or DEFAULT_EDGE_VOICE).strip()
    selected_rate = str(rate or speed_token_to_edge_rate(speed)).strip()
    selected_pitch = str(pitch or DEFAULT_PITCH).strip()

    if normalized_provider != TTS_PROVIDER_EDGE:
        raise ValueError(f"Provider is not implemented: {normalized_provider}")

    return _cached_edge_synth(clean_text, selected_voice, selected_rate, selected_pitch)
