"""Generate machine-local fallback overrides for this skill."""

from __future__ import annotations

import json
import os
from pathlib import Path

from bootstrap_assets import bootstrap
from skill_paths import (
    BUNDLED_ASSETS_DIR,
    DEFAULTS_DIR,
    jianying_install_candidates,
    resolve_asset_path,
)


LOCAL_FALLBACK = DEFAULTS_DIR / "default_fallbacks.local.json"


def _find_popup_font() -> tuple[str | None, str | None]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None, None
    cache = Path(local) / "JianyingPro" / "User Data" / "Cache" / "effect"
    if not cache.exists():
        return None, None
    for effect_dir in cache.iterdir():
        if not effect_dir.is_dir():
            continue
        fonts = list(effect_dir.rglob("*.ttf"))
        if fonts:
            return effect_dir.name, str(fonts[0].resolve())
    return None, None


def _find_bgm() -> str | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    music_dir = Path(local) / "JianyingPro" / "User Data" / "Cache" / "music"
    if not music_dir.exists():
        return None
    tracks = sorted(music_dir.glob("*.mp3"), key=lambda p: p.stat().st_size, reverse=True)
    return str(tracks[0].resolve()) if tracks else None


def _subtitle_font() -> str | None:
    for install in jianying_install_candidates():
        font_dir = install / "Resources" / "Font"
        if font_dir.exists():
            fonts = sorted(font_dir.glob("*.ttf"))
            if fonts:
                return str(fonts[0].resolve())
    return None


def build_local_fallbacks() -> dict:
    bootstrap(BUNDLED_ASSETS_DIR / "_copy_report.json")
    popup_id, popup_path = _find_popup_font()
    subtitle_path = resolve_asset_path("assets/fonts/subtitle.ttf") or _subtitle_font()
    bgm_path = resolve_asset_path("assets/bgm/fallback_bgm.mp3") or _find_bgm()

    return {
        "schema": "jianying-template-video-remix.default-fallbacks.v1",
        "name": "default_fallbacks.local",
        "usage": "Auto-generated on this machine. Gitignored.",
        "fallbacks": {
            "popup_title": {
                "default_style": "shadow_notice",
                "styles": {
                    "shadow_notice": {
                        "font_resource_id": popup_id or "",
                        "font_path": popup_path or resolve_asset_path("assets/fonts/popup_title.ttf") or "",
                        "font_size": 15,
                        "default_text_color": "#ffde00",
                    }
                },
            },
            "subtitle": {
                "font_resource_id": "6740435892441190919",
                "font_path": subtitle_path or "",
                "font_size": 9.0,
                "text_color": "#ffffff",
            },
            "bgm": {
                "path": bgm_path or "",
                "name": "Local Fallback BGM",
            },
            "tts": {
                "default_voice": {
                    "tone_speaker": "zh_female_mizai_saturn_bigtts",
                    "tone_platform": "sami",
                }
            },
        },
    }


def main() -> int:
    profile = build_local_fallbacks()
    LOCAL_FALLBACK.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(LOCAL_FALLBACK)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
