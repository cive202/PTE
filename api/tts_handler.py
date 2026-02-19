import asyncio
from typing import Optional

import edge_tts

DEFAULT_VOICE = "en-US-GuyNeural"
DEFAULT_RATE = "+0%"
SLOW_RATE = "-15%"


def _run_async(coro):
    """Run async coroutine in a dedicated event loop."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _collect_audio_bytes(text: str, voice: str, rate: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    chunks = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            chunks.append(chunk.get("data", b""))
    return b"".join(chunks)


def synthesize_speech(text: str, speed: str = "default", voice: Optional[str] = None) -> bytes:
    selected_voice = voice or DEFAULT_VOICE
    normalized_speed = (speed or "default").lower()
    rate = SLOW_RATE if normalized_speed == "slow" else DEFAULT_RATE
    return _run_async(_collect_audio_bytes(text, selected_voice, rate))
