import re
import io
from typing import List
from pydub import AudioSegment
from dataclasses import dataclass
from sacremoses import MosesPunctNormalizer

from smallest.exceptions import ValidationError
from smallest.models import TTSModels, TTSLanguages


API_BASE_URL = "https://waves-api.smallest.ai/api/v1"
SENTENCE_END_REGEX = re.compile(r'.*[-.—!?,;:…।|]$')
mpn = MosesPunctNormalizer()
SAMPLE_WIDTH = 2
CHANNELS = 1


@dataclass
class TTSOptions:
    model: str
    sample_rate: int
    voice_id: str
    api_key: str
    add_wav_header: bool
    speed: float
    transliterate: bool
    remove_extra_silence: bool


def validate_input(text: str, model: str, sample_rate: int, speed: float):
    if not text:
        raise ValidationError("Text cannot be empty.")
    if model not in TTSModels:
        raise ValidationError(f"Invalid model: {model}. Must be one of {TTSModels}")
    if not 8000 <= sample_rate <= 24000:
        raise ValidationError(f"Invalid sample rate: {sample_rate}. Must be between 8000 and 24000")
    if not 0.5 <= speed <= 2.0:
        raise ValidationError(f"Invalid speed: {speed}. Must be between 0.5 and 2.0")


def add_wav_header(frame_input: bytes, sample_rate: int = 24000, sample_width: int = 2, channels: int = 1) -> bytes:
        audio = AudioSegment(data=frame_input, sample_width=sample_width, frame_rate=sample_rate, channels=channels)
        wav_buf = io.BytesIO()
        audio.export(wav_buf, format="wav")
        wav_buf.seek(0)
        return wav_buf.read()


def preprocess_text(text: str) -> str:
    text = text.replace("\n", " ").replace("\t", " ").replace("—", " ").replace("-", " ").replace("–", " ")
    text = re.sub(r'\s+', ' ', text)
    text = mpn.normalize(text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 250) -> List[str]:
    """
    Splits the input text into chunks based on sentence boundaries
    defined by SENTENCE_END_REGEX and the maximum chunk size.
    Only splits at valid sentence boundaries to avoid breaking words.
    """
    chunks = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text.strip())
            break

        chunk_text = text[:chunk_size]
        last_break_index = -1

        # Find last sentence boundary using regex
        for i in range(len(chunk_text) - 1, -1, -1):
            if SENTENCE_END_REGEX.match(chunk_text[:i + 1]):
                last_break_index = i
                break

        if last_break_index == -1:
            # Fallback to space if no sentence boundary found
            last_space = chunk_text.rfind(' ')
            if last_space != -1:
                last_break_index = last_space 
            else:
                last_break_index = chunk_size - 1

        chunks.append(text[:last_break_index + 1].strip())
        text = text[last_break_index + 1:].strip()

    return chunks


def get_smallest_languages() -> List[str]:
    return TTSLanguages

def get_smallest_models() -> List[str]:
    return TTSModels
