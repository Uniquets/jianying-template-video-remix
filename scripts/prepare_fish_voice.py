"""Generate paragraph-level Fish Audio narration for Jianying remix."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


FISH_BASE_URL = "https://api.fish.audio"
DEFAULT_MODEL = "s2-pro"
DEFAULT_LATENCY = "normal"
DEFAULT_FORMAT = "mp3"
MAX_SUBTITLE_CHARS = 14


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text or "") if part.strip()]
    if paragraphs:
        return paragraphs
    return [text.strip()] if text and text.strip() else []


def split_subtitles(text: str, max_chars: int = MAX_SUBTITLE_CHARS) -> list[str]:
    units: list[str] = []
    for sentence in re.split(r"(?<=[。！？!?；;])\s*|\n+", (text or "").strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            units.append(sentence)
            continue
        for clause in re.split(r"(?<=[，,、：:])", sentence):
            clause = clause.strip()
            if clause:
                units.append(clause)
    chunks: list[str] = []
    for unit in units or [text.strip()]:
        while len(unit) > max_chars:
            chunks.append(unit[:max_chars])
            unit = unit[max_chars:]
        if unit:
            chunks.append(unit)
    return chunks


def build_voice_groups(paragraphs: list[str], paragraph_durations: list[float], max_subtitle_chars: int = MAX_SUBTITLE_CHARS) -> list[dict]:
    if len(paragraphs) != len(paragraph_durations):
        raise ValueError("paragraph count and duration count differ")
    groups = []
    start_index = 0
    for paragraph, duration in zip(paragraphs, paragraph_durations):
        chunks = split_subtitles(paragraph, max_chars=max_subtitle_chars)
        groups.append({"start_index": start_index, "chunks": chunks, "duration": float(duration)})
        start_index += len(chunks)
    return groups


def find_binary(name: str) -> str:
    found = shutil_which(name)
    if found:
        return found
    roots = [Path.home() / "Documents" / "Codex"]
    for root in roots:
        if root.exists():
            for candidate in root.rglob(f"{name}.exe"):
                return str(candidate)
    raise FileNotFoundError(f"missing {name}; install ffmpeg or provide it on PATH")


def shutil_which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


def probe_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            [find_binary("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        ).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


def concat_audio(inputs: list[Path], output_wav: Path) -> float:
    if not inputs:
        raise ValueError("no paragraph audio files to concatenate")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    list_file = output_wav.parent / "concat.txt"
    lines = []
    for path in inputs:
        escaped = str(path).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
        [
            find_binary("ffmpeg"),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-ar",
            "24000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return probe_duration(output_wav)


def fish_headers(api_key: str, *, content_type: str | None = None, model: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    if content_type:
        headers["Content-Type"] = content_type
    if model:
        headers["model"] = model
    return headers


def create_voice_model(api_key: str, voice_sample: Path, title: str, transcript: str | None = None, timeout: float = 120.0) -> str:
    if not voice_sample.exists():
        raise FileNotFoundError(f"voice sample not found: {voice_sample}")
    data = {
        "type": "tts",
        "train_mode": "fast",
        "title": title,
        "visibility": "private",
    }
    if transcript:
        data["texts"] = transcript
    with voice_sample.open("rb") as voice_file:
        files = {"voices": (voice_sample.name, voice_file, "application/octet-stream")}
        response = httpx.post(
            f"{FISH_BASE_URL}/model",
            headers=fish_headers(api_key),
            data=data,
            files=files,
            timeout=timeout,
        )
    response.raise_for_status()
    payload = response.json()
    model_id = payload.get("_id") or payload.get("id")
    if not model_id:
        raise RuntimeError("Fish model response did not include _id")
    return model_id


def wait_for_voice_model(api_key: str, model_id: str, max_wait_seconds: float = 180.0, poll_seconds: float = 8.0) -> dict[str, Any]:
    deadline = time.time() + max_wait_seconds
    last_payload: dict[str, Any] = {}
    while True:
        response = httpx.get(f"{FISH_BASE_URL}/model/{model_id}", headers=fish_headers(api_key), timeout=60.0)
        response.raise_for_status()
        last_payload = response.json()
        state = str(last_payload.get("state", "")).lower()
        if state == "trained":
            return last_payload
        if state == "failed":
            raise RuntimeError(f"Fish voice model training failed: {model_id}")
        if time.time() >= deadline:
            raise TimeoutError(f"Fish voice model was not trained within {max_wait_seconds} seconds; current state={state or 'unknown'}")
        time.sleep(poll_seconds)


def synthesize_paragraph(
    *,
    api_key: str,
    reference_id: str,
    text: str,
    output_path: Path,
    model: str = DEFAULT_MODEL,
    audio_format: str = DEFAULT_FORMAT,
    latency: str = DEFAULT_LATENCY,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "text": text,
        "reference_id": reference_id,
        "format": audio_format,
        "latency": latency,
    }
    with httpx.stream(
        "POST",
        f"{FISH_BASE_URL}/v1/tts",
        headers=fish_headers(api_key, content_type="application/json", model=model),
        json=payload,
        timeout=None,
    ) as response:
        response.raise_for_status()
        with output_path.open("wb") as out:
            for chunk in response.iter_bytes():
                out.write(chunk)


def write_fish_profile(profile_path: Path, data: dict[str, Any]) -> None:
    clean = {key: value for key, value in data.items() if key not in {"api_key", "authorization", "Authorization"}}
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise RuntimeError(f"missing Fish API key; set {args.api_key_env}")

    script_path = Path(args.script_file)
    paragraphs = split_paragraphs(script_path.read_text(encoding="utf-8"))
    if not paragraphs:
        raise ValueError("script file has no readable narration paragraphs")

    output_dir = Path(args.output_dir)
    fish_dir = output_dir / "fish_voice"
    paragraph_dir = fish_dir / "paragraphs"
    audio_format = args.format
    reference_id = args.reference_id
    if not reference_id:
        if not args.voice_sample:
            raise ValueError("pass --reference-id or --voice-sample")
        reference_id = create_voice_model(
            api_key,
            Path(args.voice_sample),
            args.voice_title or f"jianying-remix-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            transcript=args.voice_sample_text,
        )
        wait_for_voice_model(api_key, reference_id, max_wait_seconds=args.max_wait_seconds)

    paragraph_paths: list[Path] = []
    durations: list[float] = []
    for idx, paragraph in enumerate(paragraphs, start=1):
        paragraph_path = paragraph_dir / f"paragraph_{idx:03d}.{audio_format}"
        synthesize_paragraph(
            api_key=api_key,
            reference_id=reference_id,
            text=paragraph,
            output_path=paragraph_path,
            model=args.model,
            audio_format=audio_format,
            latency=args.latency,
        )
        duration = probe_duration(paragraph_path)
        if duration <= 0:
            raise RuntimeError(f"Fish paragraph audio is not parseable: {paragraph_path}")
        paragraph_paths.append(paragraph_path)
        durations.append(duration)

    voice_path = fish_dir / "narration_full.wav"
    total_duration = concat_audio(paragraph_paths, voice_path)
    if total_duration > 0 and sum(durations) > 0:
        scale = total_duration / sum(durations)
        durations = [duration * scale for duration in durations]
    groups = build_voice_groups(paragraphs, durations)
    groups_path = fish_dir / "voice_groups.json"
    groups_payload = {
        "provider": "fish_audio",
        "duration": total_duration,
        "voice_file": str(voice_path),
        "groups": groups,
        "generation_unit": "paragraph",
    }
    groups_path.write_text(json.dumps(groups_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    profile_path = fish_dir / "fish_voice_profile.json"
    write_fish_profile(
        profile_path,
        {
            "provider": "fish_audio",
            "model": args.model,
            "reference_id": reference_id,
            "voice_sample": args.voice_sample or "",
            "voice_title": args.voice_title or "",
            "format": audio_format,
            "latency": args.latency,
            "paragraph_count": len(paragraphs),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return {
        "voice_file": str(voice_path),
        "voice_groups": str(groups_path),
        "profile": str(profile_path),
        "duration": total_duration,
        "reference_id": reference_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paragraph-level Fish Audio narration for Jianying remix.")
    parser.add_argument("--script-file", required=True, help="Confirmed narration text. Natural paragraphs become Fish TTS units.")
    parser.add_argument("--output-dir", required=True, help="Project output directory; fish_voice artifacts are written here.")
    parser.add_argument("--voice-sample", help="Clean voice sample file for cloning. Required when --reference-id is absent.")
    parser.add_argument("--voice-sample-text", help="Optional transcript matching the voice sample.")
    parser.add_argument("--voice-title", help="Private Fish voice model title when cloning from a sample.")
    parser.add_argument("--reference-id", help="Existing Fish voice model id to reuse.")
    parser.add_argument("--api-key-env", default="FISH_API_KEY", help="Environment variable containing the Fish API key.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Fish TTS model header. Default: s2-pro.")
    parser.add_argument("--format", default=DEFAULT_FORMAT, choices=("mp3", "wav", "opus", "pcm"))
    parser.add_argument("--latency", default=DEFAULT_LATENCY, choices=("low", "normal", "balanced"))
    parser.add_argument("--max-wait-seconds", type=float, default=180.0, help="Max wait for cloned model training.")
    args = parser.parse_args()

    result = prepare(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
