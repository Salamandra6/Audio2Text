from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from .exporters import TranscriptionResult

STOPWORDS = {
    "a", "al", "algo", "ante", "como", "con", "contra", "cual", "cuando", "de", "del",
    "desde", "donde", "durante", "e", "el", "ella", "ellas", "ellos", "en", "entre", "era",
    "es", "esa", "ese", "eso", "esta", "este", "esto", "fue", "ha", "hasta", "hay", "la",
    "las", "le", "les", "lo", "los", "más", "me", "mi", "muy", "no", "nos", "o", "para",
    "pero", "por", "porque", "que", "qué", "se", "sin", "sobre", "su", "sus", "también",
    "te", "tiene", "todo", "un", "una", "uno", "unos", "y", "ya", "the", "and", "or",
    "to", "of", "in", "on", "for", "is", "are", "was", "were", "it", "this", "that",
    "with", "as", "at", "by", "from", "be", "been", "has", "have", "had",
}


def timestamp(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])", r"\1 ", text)
    if text and text[0].isalpha():
        text = text[0].upper() + text[1:]
    return text


def clean_transcript(result: TranscriptionResult) -> str:
    source = " ".join(segment.text.strip() for segment in result.segments if segment.text.strip())
    normalized = normalize_text(source)
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
    paragraphs, current, length = [], [], 0
    for sentence in sentences:
        if current and (len(current) >= 4 or length + len(sentence) > 650):
            paragraphs.append(" ".join(current))
            current, length = [], 0
        current.append(sentence)
        length += len(sentence)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def transcript_lines(result: TranscriptionResult, mode: str, timestamps: bool) -> list[str]:
    if mode == "clean" and not timestamps:
        return [part for part in clean_transcript(result).split("\n\n") if part]
    lines = []
    for segment in result.segments:
        text = segment.text.strip()
        if not text:
            continue
        if mode == "clean":
            text = normalize_text(text)
        prefix = f"[{timestamp(segment.start)}] " if timestamps else ""
        lines.append(prefix + text)
    return lines


def words(text: str) -> list[str]:
    return [
        word.lower() for word in re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}", text)
        if word.lower() not in STOPWORDS
    ]


def extractive_summary(result: TranscriptionResult, limit: int = 5) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalize_text(result.text)) if part.strip()]
    if len(sentences) <= limit:
        return sentences
    frequency = Counter(words(result.text))
    if not frequency:
        return sentences[:limit]
    maximum = max(frequency.values())
    scored = []
    for index, sentence in enumerate(sentences):
        tokens = words(sentence)
        if tokens:
            score = sum(frequency[token] / maximum for token in tokens) / len(tokens)
            scored.append((score + (0.12 if index == 0 else 0), index, sentence))
    selected = sorted(scored, reverse=True)[:limit]
    return [sentence for _, _, sentence in sorted(selected, key=lambda item: item[1])]


def main_topics(result: TranscriptionResult, limit: int = 8) -> list[str]:
    tokens = words(result.text)
    unigrams = Counter(tokens)
    bigrams = Counter(f"{a} {b}" for a, b in zip(tokens, tokens[1:]) if a != b)
    candidates = [(float(count), term) for term, count in unigrams.items()]
    candidates += [(count * 1.6, term) for term, count in bigrams.items() if count >= 2]
    topics = []
    for _, term in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if any(term in existing or existing in term for existing in topics):
            continue
        topics.append(term)
        if len(topics) >= limit:
            break
    return topics


def metadata_rows(result: TranscriptionResult) -> list[tuple[str, str]]:
    probability = max(0.0, min(1.0, float(result.language_probability)))
    return [
        ("Archivo de origen", Path(result.source_file).name),
        ("Ruta de origen", str(result.source_file)),
        ("Idioma detectado", result.language or "No determinado"),
        ("Confianza del idioma", f"{probability * 100:.1f}%"),
        ("Duración", timestamp(result.duration)),
        ("Segmentos", str(len(result.segments))),
        ("Fecha de generación", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]


def build_sections(result: TranscriptionResult, options: dict | None) -> dict:
    config = options or {}
    mode = str(config.get("mode", "literal")).lower()
    return {
        "mode": mode,
        "timestamps": bool(config.get("timestamps", False)),
        "metadata": metadata_rows(result) if config.get("metadata", True) else [],
        "summary": extractive_summary(result) if config.get("summary", False) else [],
        "topics": main_topics(result) if config.get("topics", False) else [],
        "transcript": transcript_lines(result, mode, bool(config.get("timestamps", False))),
    }
