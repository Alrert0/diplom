import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)

VOICES_DIR = Path(__file__).resolve().parent.parent.parent / "voices"
VOICES_DIR.mkdir(parents=True, exist_ok=True)

# Edge-TTS voice mapping: language -> gender -> voice ID
EDGE_VOICES = {
    "en": {
        "female": "en-US-JennyNeural",
        "male": "en-US-GuyNeural",
    },
    "ru": {
        "female": "ru-RU-SvetlanaNeural",
        "male": "ru-RU-DmitryNeural",
    },
    "kk": {
        "female": "kk-KZ-AigulNeural",
        "male": "kk-KZ-DauletNeural",
    },
}

# Piper voice file pattern: {lang}_{gender}.onnx in voices/ directory
PIPER_VOICE_MAP = {
    "en": {"female": "en_US-lessac-medium", "male": "en_US-ryan-medium"},
    "ru": {"female": "ru_RU-irina-medium", "male": "ru_RU-denis-medium"},
    "kk": {"female": "kk_KZ-female-medium", "male": "kk_KZ-male-medium"},
}


def _find_piper_voice(language: str, gender: str) -> Path | None:
    """Find a Piper .onnx voice model in the voices directory."""
    voice_name = PIPER_VOICE_MAP.get(language, {}).get(gender)
    if not voice_name:
        return None
    onnx_path = VOICES_DIR / f"{voice_name}.onnx"
    if onnx_path.exists():
        return onnx_path
    # Also check for any matching file
    for f in VOICES_DIR.glob(f"*{language}*{gender}*.onnx"):
        return f
    return None


def _piper_available() -> bool:
    """Check if piper CLI is installed."""
    return shutil.which("piper") is not None


async def synthesize_piper(text: str, language: str, gender: str) -> bytes | None:
    """Synthesize audio using Piper TTS (offline). Returns WAV bytes or None."""
    if not _piper_available():
        logger.info("Piper TTS not installed, skipping")
        return None

    voice_path = _find_piper_voice(language, gender)
    if not voice_path:
        logger.info("No Piper voice model found for %s/%s", language, gender)
        return None

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        proc = await asyncio.create_subprocess_exec(
            "piper",
            "--model", str(voice_path),
            "--output_file", tmp_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate(input=text.encode("utf-8"))

        if proc.returncode != 0:
            logger.error("Piper TTS failed: %s", stderr.decode(errors="replace"))
            return None

        audio_bytes = Path(tmp_path).read_bytes()
        Path(tmp_path).unlink(missing_ok=True)
        return audio_bytes
    except Exception as e:
        logger.error("Piper TTS error: %s", e)
        return None


async def synthesize_edge(text: str, language: str, gender: str) -> bytes:
    """Synthesize audio using Edge-TTS (online). Returns MP3 bytes."""
    voice_map = EDGE_VOICES.get(language, EDGE_VOICES["en"])
    voice = voice_map.get(gender, voice_map["female"])

    communicate = edge_tts.Communicate(text, voice)

    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])

    if not chunks:
        raise RuntimeError(f"Edge-TTS returned no audio for voice {voice}")

    return b"".join(chunks)


async def synthesize(
    text: str,
    language: str,
    gender: str = "female",
    use_offline: bool = False,
) -> tuple[bytes, str]:
    """
    Synthesize speech from text.
    Returns (audio_bytes, content_type).
    If use_offline=True, tries Piper first, then falls back to edge-tts.
    """
    if use_offline:
        audio = await synthesize_piper(text, language, gender)
        if audio:
            return audio, "audio/wav"
        logger.info("Piper unavailable, falling back to edge-tts")

    audio = await synthesize_edge(text, language, gender)
    return audio, "audio/mpeg"


def get_available_voices() -> list[dict]:
    """Return list of available TTS voices."""
    voices = []

    # Edge-TTS voices (always available)
    for lang, genders in EDGE_VOICES.items():
        for gender, voice_id in genders.items():
            lang_names = {"en": "English", "ru": "Russian", "kk": "Kazakh"}
            voices.append({
                "id": voice_id,
                "name": voice_id,
                "language": lang,
                "language_name": lang_names.get(lang, lang),
                "gender": gender,
                "engine": "edge",
            })

    # Piper voices (only if model files exist)
    for lang, genders in PIPER_VOICE_MAP.items():
        for gender, voice_name in genders.items():
            voice_path = _find_piper_voice(lang, gender)
            if voice_path:
                lang_names = {"en": "English", "ru": "Russian", "kk": "Kazakh"}
                voices.append({
                    "id": f"piper-{voice_name}",
                    "name": voice_name,
                    "language": lang,
                    "language_name": lang_names.get(lang, lang),
                    "gender": gender,
                    "engine": "piper",
                })

    return voices
