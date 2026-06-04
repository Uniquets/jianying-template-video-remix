"""Copy local Jianying cache/install files into skill defaults/assets (idempotent)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from skill_paths import BUNDLED_ASSETS_DIR, SKILL_ROOT, jianying_install_candidates


POPUP_FONT_ID = "7080096967543493150"
BGM_CACHE_NAME = "3cf4b8a5f6fdebfae12664934481ab98.mp3"

POPUP_DST = BUNDLED_ASSETS_DIR / "fonts" / "popup_title.ttf"
SUB_DST = BUNDLED_ASSETS_DIR / "fonts" / "subtitle.ttf"
BGM_DST = BUNDLED_ASSETS_DIR / "bgm" / "fallback_bgm.mp3"


def _localappdata() -> Path | None:
    root = os.environ.get("LOCALAPPDATA")
    return Path(root) if root else None


def _find_popup_font() -> Path | None:
    local = _localappdata()
    if not local:
        return None
    cache = local / "JianyingPro" / "User Data" / "Cache" / "effect" / POPUP_FONT_ID
    if not cache.exists():
        return None
    matches = list(cache.rglob("*.ttf"))
    return matches[0] if matches else None


def _find_bgm() -> Path | None:
    local = _localappdata()
    if not local:
        return None
    path = local / "JianyingPro" / "User Data" / "Cache" / "music" / BGM_CACHE_NAME
    return path if path.exists() else None


def _pick_subtitle_font() -> Path | None:
    for install in jianying_install_candidates():
        font_dir = install / "Resources" / "Font"
        if not font_dir.exists():
            continue
        for pattern in ("zh-hans.ttf", "*.ttf"):
            matches = sorted(font_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def bootstrap(report_path: Path | None = None) -> dict:
    (BUNDLED_ASSETS_DIR / "fonts").mkdir(parents=True, exist_ok=True)
    (BUNDLED_ASSETS_DIR / "bgm").mkdir(parents=True, exist_ok=True)
    report = {"skill_root": str(SKILL_ROOT), "copied": [], "skipped": []}

    def record_copy(label: str, src: Path, dst: Path) -> None:
        shutil.copy2(src, dst)
        report["copied"].append({"label": label, "src": str(src), "dst": str(dst), "bytes": dst.stat().st_size})

    popup = _find_popup_font()
    if popup:
        record_copy("popup_title", popup, POPUP_DST)
    else:
        report["skipped"].append({"label": "popup_title", "reason": "missing"})

    sub = _pick_subtitle_font()
    if sub:
        record_copy("subtitle", sub, SUB_DST)
    else:
        report["skipped"].append({"label": "subtitle", "reason": "missing"})

    bgm = _find_bgm()
    if bgm:
        record_copy("fallback_bgm", bgm, BGM_DST)
    else:
        report["skipped"].append({"label": "fallback_bgm", "reason": "missing"})

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = bootstrap(BUNDLED_ASSETS_DIR / "_copy_report.json")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
