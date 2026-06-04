import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from skill_paths import looks_like_bgm_audio, looks_like_voiceover_audio, sanitize_profile


def load_json_maybe_decrypt(draft_path: Path, jy_install: str | None) -> dict:
    content_path = draft_path / "draft_content.json"
    if not content_path.exists():
        raise FileNotFoundError(f"missing draft_content.json: {content_path}")
    try:
        return json.loads(content_path.read_text(encoding="utf-8"))
    except Exception:
        if not jy_install:
            raise RuntimeError("draft_content.json is not plaintext JSON; pass --jy-install")
        out = Path(tempfile.mkdtemp(prefix="jy_style_")) / "draft_content.dec.json"
        script = Path(__file__).resolve().parent / "decrypt_jianying_draft.py"
        subprocess.run([sys.executable, str(script), jy_install, str(content_path), str(out)], check=True)
        return json.loads(out.read_text(encoding="utf-8"))


def material_index(data: dict) -> dict:
    return {
        m["id"]: m
        for values in data.get("materials", {}).values()
        if isinstance(values, list)
        for m in values
        if isinstance(m, dict) and "id" in m
    }


def track_material_ids(data: dict, track_type: str | None = None) -> list[str]:
    ids = []
    for track in data.get("tracks", []):
        if track_type and track.get("type") != track_type:
            continue
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            if mid:
                ids.append(mid)
    return ids


def text_content(mat: dict) -> dict:
    try:
        return json.loads(mat.get("content") or "{}")
    except Exception:
        return {}


def text_transform(data: dict, mat_id: str) -> dict:
    for track in data.get("tracks", []):
        for seg in track.get("segments", []):
            if seg.get("material_id") == mat_id:
                return seg.get("clip", {}).get("transform", {}) or {}
    return {}


def first_style_content(mat: dict) -> dict:
    content = text_content(mat)
    styles = content.get("styles") or []
    return styles[0] if styles else {}


def pick_subtitle_text(data: dict, mats: dict) -> dict:
    candidates = []
    for mid in track_material_ids(data, "text"):
        mat = mats.get(mid, {})
        if mat.get("type") == "subtitle":
            candidates.append(mat)
    if candidates:
        return max(candidates, key=lambda m: len(text_content(m).get("text", "")))
    texts = [mats[mid] for mid in track_material_ids(data, "text") if mid in mats]
    return max(texts, key=lambda m: len(text_content(m).get("text", "")), default={})


def pick_title_texts(data: dict, mats: dict, subtitle_id: str | None) -> list[dict]:
    out = []
    for mid in track_material_ids(data, "text"):
        if mid == subtitle_id or mid not in mats:
            continue
        mat = mats[mid]
        txt = text_content(mat).get("text", "")
        if txt.strip():
            out.append(mat)
    return out


def audio_usage_span(data: dict) -> dict[str, int]:
    spans: dict[str, int] = {}
    for track in data.get("tracks", []):
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            if not mid:
                continue
            tr = seg.get("target_timerange") or {}
            spans[mid] = max(spans.get(mid, 0), int(tr.get("duration") or 0))
    return spans


def pick_bgm_material(audios: list[dict], spans: dict[str, int], draft_duration: int) -> dict:
    candidates = [m for m in audios if m.get("path") and looks_like_bgm_audio(m)]
    if not candidates:
        return {}

    def score(mat: dict) -> tuple[int, int]:
        label = f"{mat.get('name', '')} {mat.get('path', '')}".lower()
        points = 0
        if mat.get("music_id"):
            points += 4
        if any(h in label for h in ("bgm", "背景", "配乐")):
            points += 8
        span = spans.get(mat.get("id", ""), 0)
        if draft_duration > 0 and span >= int(draft_duration * 0.45):
            points += 6
        return (points, span)

    return max(candidates, key=score)


def audio_profile(data: dict) -> dict:
    audios = data.get("materials", {}).get("audios", [])
    tts = next((m for m in audios if m.get("tone_speaker")), {})
    spans = audio_usage_span(data)
    draft_duration = int(data.get("duration") or 0)
    bgm_mat = pick_bgm_material(audios, spans, draft_duration)
    bgm_id = bgm_mat.get("id")
    sfx = []
    for m in audios:
        if not m.get("path") or m is tts or (bgm_id and m.get("id") == bgm_id):
            continue
        if looks_like_voiceover_audio(m):
            continue
        sfx.append({"path": m.get("path", ""), "name": m.get("name", ""), "duration": m.get("duration", 0)})
    return {
        "tts": {k: tts.get(k) for k in ["tone_speaker", "tone_platform", "resource_id", "tone_type", "tone_effect_name"] if tts.get(k)},
        "bgm": {k: bgm_mat.get(k) for k in ["path", "name", "music_id", "category_id", "duration"] if bgm_mat.get(k)},
        "sound_effects": sfx[:20],
    }


def analyze(draft_path: Path, jy_install: str | None = None) -> dict:
    data = load_json_maybe_decrypt(draft_path, jy_install)
    mats = material_index(data)
    subtitle = pick_subtitle_text(data, mats)
    subtitle_style = first_style_content(subtitle)
    subtitle_id = subtitle.get("id")
    title_texts = pick_title_texts(data, mats, subtitle_id)
    title = title_texts[0] if title_texts else {}
    title_style = first_style_content(title)

    animations = []
    for track in data.get("tracks", []):
        for seg in track.get("segments", []):
            if seg.get("material_id") in {m.get("id") for m in title_texts}:
                for anim in seg.get("animations", {}).get("animations", []):
                    name = anim.get("name") or anim.get("resource_id") or anim.get("id")
                    if name and name not in animations:
                        animations.append(name)

    profile = {
        "template_path": str(draft_path),
        "subtitle": {
            "font_resource_id": subtitle.get("font_resource_id") or subtitle_style.get("font", {}).get("id"),
            "font_path": subtitle.get("font_path") or subtitle_style.get("font", {}).get("path"),
            "font_size": subtitle.get("font_size") or subtitle_style.get("size") or 9.0,
            "text_color": subtitle.get("text_color", "#ffffff"),
            "background_style": subtitle.get("background_style", 1),
            "background_color": subtitle.get("background_color", "#000000"),
            "background_alpha": subtitle.get("background_alpha", 0.16),
            "background_width": subtitle.get("background_width", 0.0),
            "background_height": subtitle.get("background_height", 0.0),
            "has_shadow": subtitle.get("has_shadow", True),
            "shadow_alpha": subtitle.get("shadow_alpha", 0.9),
            "shadow_color": subtitle.get("shadow_color", "#000000"),
            "shadow_distance": subtitle.get("shadow_distance", 5.0),
            "shadow_smoothing": subtitle.get("shadow_smoothing", 0.45),
            "border_width": subtitle.get("border_width", 0.08),
            "line_spacing": subtitle.get("line_spacing", 0.02),
            "transform": text_transform(data, subtitle_id) if subtitle_id else {"x": 0, "y": -0.85},
        },
        "title": {
            "font_resource_id": title.get("font_resource_id") or title_style.get("font", {}).get("id"),
            "font_path": title.get("font_path") or title_style.get("font", {}).get("path"),
            "font_size": title.get("font_size") or title_style.get("size") or 15.0,
            "text_color": title.get("text_color", "#ffde00"),
            "border_color": title.get("border_color", "#000000"),
            "border_width": title.get("border_width", 0.08),
            "animations": animations[:12],
        },
        "audio": audio_profile(data),
    }
    return sanitize_profile(profile)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template-draft", required=True)
    parser.add_argument("--jy-install")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    profile = analyze(Path(args.template_draft), args.jy_install)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
