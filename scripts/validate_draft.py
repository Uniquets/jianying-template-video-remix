import argparse
import json
import os
import subprocess
import sys
import tempfile
import statistics
from pathlib import Path


def default_drafts_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
    return Path.home() / "AppData" / "Local" / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"


def load_draft(path: Path, jy_install: str | None = None) -> dict:
    content_path = path / "draft_content.json"
    try:
        return json.loads(content_path.read_text(encoding="utf-8"))
    except Exception:
        if not jy_install:
            raise
        out = Path(tempfile.mkdtemp(prefix="jy_validate_")) / "draft_content.dec.json"
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


def content_text(mat: dict) -> str:
    try:
        return json.loads(mat.get("content") or "{}").get("text", "")
    except Exception:
        return ""


def overlaps(data: dict) -> list[dict]:
    bad = []
    for track in data.get("tracks", []):
        segs = sorted(track.get("segments", []), key=lambda s: s.get("target_timerange", {}).get("start", 0))
        for prev, curr in zip(segs, segs[1:]):
            prev_range = prev.get("target_timerange", {})
            curr_range = curr.get("target_timerange", {})
            prev_end = prev_range.get("start", 0) + prev_range.get("duration", 0)
            curr_start = curr_range.get("start", 0)
            if prev_end > curr_start:
                bad.append({"track": track.get("name"), "prev_end": prev_end, "curr_start": curr_start})
    return bad


def validate(draft_path: Path, jy_install: str | None = None) -> dict:
    data = load_draft(draft_path, jy_install)
    mats = material_index(data)
    tracks = {t.get("name"): t for t in data.get("tracks", [])}

    def segs(name: str) -> list:
        return tracks.get(name, {}).get("segments", [])

    subs = segs("Template_Subtitles_Short")
    sub_mats = [mats[s["material_id"]] for s in subs if s.get("material_id") in mats]
    sub_lens = [len(content_text(m)) for m in sub_mats] or [0]
    sub_durs = [s.get("target_timerange", {}).get("duration", 0) / 1e6 for s in subs] or [0]
    audios = data.get("materials", {}).get("audios", [])
    voice = [m for m in audios if "narration_full" in m.get("path", "")]
    bgm = [m for m in audios if m.get("type") == "music" or m.get("music_id")]
    title_segments = (
        segs("Template_Hero_Title")
        + segs("Template_Event_Titles")
        + segs("Template_Red_Notes")
    )
    style_flags = sorted({m.get("check_flag") for m in sub_mats if "check_flag" in m})
    subtitle_font_ids = sorted({m.get("font_resource_id") for m in sub_mats if m.get("font_resource_id")})

    return {
        "draft_path": str(draft_path),
        "duration_s": round(data.get("duration", 0) / 1e6, 3),
        "video_segments": len(segs("Template_Main_Video")),
        "voice_segments": len(segs("Template_Continuous_Voice")),
        "voice_materials": len(voice),
        "voice_speaker": voice[0].get("tone_speaker") if voice else None,
        "subtitle_segments": len(subs),
        "subtitle_median_chars": statistics.median(sub_lens),
        "subtitle_median_duration_s": round(statistics.median(sub_durs), 3),
        "subtitle_max_chars": max(sub_lens),
        "subtitle_check_flags": style_flags,
        "subtitle_font_ids": subtitle_font_ids,
        "title_segments": len(title_segments),
        "sfx_segments": len(segs("Template_Event_SFX")),
        "bgm_materials": len(bgm),
        "overlaps": overlaps(data),
        "ok": len(overlaps(data)) == 0 and len(segs("Template_Continuous_Voice")) <= 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-path")
    parser.add_argument("--draft-name")
    parser.add_argument("--draft-root", default=str(default_drafts_root()))
    parser.add_argument("--jy-install")
    args = parser.parse_args()
    if not args.draft_path and not args.draft_name:
        parser.error("pass --draft-path or --draft-name")
    path = Path(args.draft_path) if args.draft_path else Path(args.draft_root) / args.draft_name
    print(json.dumps(validate(path, args.jy_install), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
