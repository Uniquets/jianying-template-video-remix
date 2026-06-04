"""Shared path resolution and profile sanitization for jianying-template-video-remix."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULTS_DIR = SKILL_ROOT / "defaults"
DEFAULT_FALLBACK_PROFILE = DEFAULTS_DIR / "default_fallbacks.json"
DEFAULT_FALLBACK_EXAMPLE = DEFAULTS_DIR / "default_fallbacks.example.json"
BUNDLED_ASSETS_DIR = DEFAULTS_DIR / "assets"

# Filename/path hints: narration or dub tracks are not background music.
VOICEOVER_AUDIO_HINTS = (
    "配音",
    "旁白",
    "解说",
    "口播",
    "人声",
    "voiceover",
    "narration",
    "解说词",
    "工具配音",
)
BGM_AUDIO_HINTS = ("bgm", "背景", "配乐", "纯音乐", "background", "主题曲", "插曲")


def audio_label(mat: dict) -> str:
    return f"{mat.get('name', '')} {mat.get('path', '')}".lower()


def looks_like_voiceover_audio(mat: dict | None = None, *, path: str | None = None, name: str | None = None) -> bool:
    if mat:
        if mat.get("tone_speaker") or mat.get("tts_generate_scene"):
            return True
        label = audio_label(mat)
    else:
        label = f"{name or ''} {path or ''}".lower()
    return any(hint in label for hint in VOICEOVER_AUDIO_HINTS)


def looks_like_bgm_audio(mat: dict) -> bool:
    if looks_like_voiceover_audio(mat):
        return False
    label = audio_label(mat)
    if any(hint in label for hint in BGM_AUDIO_HINTS):
        return True
    return bool(mat.get("type") == "music" or mat.get("music_id"))


def resolve_asset_path(path: str | None, base: Path | None = None) -> str | None:
    if not path or not str(path).strip():
        return None
    raw = str(path).strip()
    candidate = Path(raw)
    if not candidate.is_absolute():
        root = base or DEFAULTS_DIR
        candidate = (root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return str(candidate) if candidate.exists() else None


def _resolve_mapping_paths(mapping: dict, keys: tuple[str, ...], base: Path | None = None) -> dict:
    out = dict(mapping)
    for key in keys:
        if key in out and out[key]:
            resolved = resolve_asset_path(out[key], base=base)
            if resolved:
                out[key] = resolved
            else:
                out.pop(key, None)
    return out


def resolve_fallback_bundle(fallback_profile: dict) -> dict:
    """Resolve relative asset paths inside a loaded fallback profile."""
    profile = json.loads(json.dumps(fallback_profile, ensure_ascii=False))
    fallbacks = profile.get("fallbacks") or {}
    popup = fallbacks.get("popup_title") or {}
    for name, style in (popup.get("styles") or {}).items():
        popup["styles"][name] = _resolve_mapping_paths(style, ("font_path",))
    if popup:
        fallbacks["popup_title"] = popup
    if fallbacks.get("subtitle"):
        fallbacks["subtitle"] = _resolve_mapping_paths(fallbacks["subtitle"], ("font_path",))
    if fallbacks.get("bgm"):
        fallbacks["bgm"] = _resolve_mapping_paths(fallbacks["bgm"], ("path",))
    profile["fallbacks"] = fallbacks
    return profile


def sanitize_profile(profile: dict) -> dict:
    """Drop missing filesystem paths; resolve skill-relative bundled assets."""
    data = json.loads(json.dumps(profile, ensure_ascii=False))

    for section in ("subtitle", "title"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        resolved = resolve_asset_path(block.get("font_path"))
        if resolved:
            block["font_path"] = resolved
        elif block.get("font_path"):
            block.pop("font_path", None)
        data[section] = block

    audio = dict(data.get("audio") or {})
    bgm = dict(audio.get("bgm") or {})
    if bgm.get("path"):
        resolved = resolve_asset_path(bgm.get("path"))
        if resolved:
            bgm["path"] = resolved
        else:
            bgm.pop("path", None)
    if looks_like_voiceover_audio(bgm):
        bgm = {}
    audio["bgm"] = bgm

    sfx_list = []
    for item in audio.get("sound_effects") or []:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        resolved = resolve_asset_path(entry.get("path"))
        if resolved:
            entry["path"] = resolved
            sfx_list.append(entry)
        elif not entry.get("path"):
            sfx_list.append(entry)
    audio["sound_effects"] = sfx_list
    data["audio"] = audio
    return data


def default_tts_speaker(fallback_profile: dict | None = None) -> str | None:
    profile = fallback_profile or {}
    fallbacks = profile.get("fallbacks") or {}
    tts = fallbacks.get("tts") or {}
    voice = tts.get("default_voice") or tts
    return voice.get("tone_speaker")


def jianying_install_candidates() -> list[Path]:
    candidates: list[Path] = []
    for drive in ("C", "D", "E", "F"):
        root = Path(f"{drive}:/JianyingPro")
        if root.exists():
            for child in sorted(root.iterdir(), reverse=True):
                if child.is_dir() and child.name[:1].isdigit():
                    candidates.append(child)
    return candidates


def localappdata_drafts_root() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    root = Path(local) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
    return root if root.exists() else None
