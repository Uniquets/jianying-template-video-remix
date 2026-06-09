"""Prepare local historical writing references for Jianying template remix."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXTRACTOR = SKILL_ROOT / "vendor" / "jianying-draft-text-extractor" / "scripts" / "extract_jianying_draft_texts.py"
MEDIA_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class HistoricalStylePaths:
    history_dir: Path
    profile_path: Path
    brief_path: Path


def output_paths(output_dir: Path) -> HistoricalStylePaths:
    history_dir = output_dir / "history_scripts"
    return HistoricalStylePaths(
        history_dir=history_dir,
        profile_path=history_dir / "writing_style_profile.json",
        brief_path=history_dir / "narration_brief.md",
    )


def media_file_names(media_dir: Path) -> list[Path]:
    if not media_dir.exists():
        raise FileNotFoundError(f"media_dir not found: {media_dir}")
    if not media_dir.is_dir():
        raise NotADirectoryError(f"media_dir is not a directory: {media_dir}")
    files = [path for path in media_dir.iterdir() if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES]
    return sorted(files, key=lambda path: path.name.lower())


def run_extractor(
    *,
    extractor_script: Path,
    history_dir: Path,
    limit: int,
    root_meta: str | None,
    jy_install: str | None,
) -> dict[str, str]:
    if not extractor_script.exists():
        raise FileNotFoundError(f"extractor script not found: {extractor_script}")
    history_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(extractor_script),
        "--limit",
        str(limit),
        "--output-dir",
        str(history_dir),
    ]
    if root_meta:
        command.extend(["--root-meta", root_meta])
    if jy_install:
        command.extend(["--jy-install", jy_install])
    subprocess.run(command, check=True)
    return latest_extractor_outputs(history_dir)


def latest_extractor_outputs(history_dir: Path) -> dict[str, str]:
    data_files = sorted(history_dir.glob("jianying_draft_texts_*_data.json"), key=lambda path: path.stat().st_mtime)
    style_files = sorted(history_dir.glob("jianying_draft_texts_*_style_analysis.md"), key=lambda path: path.stat().st_mtime)
    full_scripts = sorted(history_dir.glob("jianying_draft_texts_*_full_scripts.md"), key=lambda path: path.stat().st_mtime)
    if not data_files or not style_files:
        raise FileNotFoundError(f"extractor outputs not found in {history_dir}")
    outputs = {
        "data": str(data_files[-1]),
        "style": str(style_files[-1]),
    }
    if full_scripts:
        outputs["full_scripts"] = str(full_scripts[-1])
    return outputs


def build_writing_style_profile(
    *,
    payload: dict,
    style_analysis: str,
    topic: str,
    media_files: list[Path],
    extractor_outputs: dict[str, str],
) -> dict:
    scripted_drafts = [draft for draft in payload.get("drafts", []) if draft.get("script")]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "root_meta": payload.get("source_root_meta", ""),
            "jianying_install": payload.get("jianying_install", ""),
            "limit": payload.get("limit", 0),
            "extractor_outputs": extractor_outputs,
        },
        "sample": {
            "draft_count": len(payload.get("drafts", [])),
            "draft_count_with_script": len(scripted_drafts),
            "total_script_chars": payload.get("total_script_chars", 0),
            "empty_script_drafts": payload.get("empty_script_drafts", []),
            "failures": payload.get("failures", []),
            "draft_names": [draft.get("draft_name", "") for draft in scripted_drafts],
        },
        "current_project": {
            "topic": topic,
            "media_files": [path.name for path in media_files],
        },
        "imitation_policy": {
            "enabled_by_default": True,
            "content_source": "topic_and_current_media_filenames",
            "requires_user_confirmation_before_remix": True,
            "anti_copy_rules": [
                "禁止复制历史草稿原句",
                "禁止复用旧草稿桥段",
                "禁止读取其他草稿的 media_plan.json 或字幕轨来抄 context/旁白",
                "每个大段必须对齐本次 topic 和本次 media_dir 中真实存在的素材文件名语义",
            ],
        },
        "style_analysis": style_analysis,
    }


def write_narration_brief(profile: dict, brief_path: Path) -> None:
    project = profile.get("current_project", {})
    policy = profile.get("imitation_policy", {})
    media_lines = "\n".join(f"- {name}" for name in project.get("media_files", [])) or "- 无可识别素材文件"
    rules = "\n".join(f"- {rule}" for rule in policy.get("anti_copy_rules", []))
    text = f"""# 历史风格仿写写稿 Brief

默认参考历史草稿文案风格，为本次主题新写口播；历史文案只作为口吻、结构和节奏参考。

## 本次主题

{project.get("topic", "")}

## 本次素材文件

{media_lines}

## 写稿硬规则

{rules}
- 生成的新文案必须先给用户确认；用户确认后，才允许进入 TTS、字幕、素材编排和 remix_draft.py。

## 历史风格分析

{profile.get("style_analysis", "")}
"""
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(text, encoding="utf-8")


def prepare(args: argparse.Namespace) -> dict:
    out_dir = Path(args.output_dir)
    paths = output_paths(out_dir)
    media_files = media_file_names(Path(args.media_dir))
    extractor_outputs = run_extractor(
        extractor_script=Path(args.extractor_script),
        history_dir=paths.history_dir,
        limit=args.limit,
        root_meta=args.root_meta,
        jy_install=args.jy_install,
    )
    payload = json.loads(Path(extractor_outputs["data"]).read_text(encoding="utf-8"))
    style_analysis = Path(extractor_outputs["style"]).read_text(encoding="utf-8")
    profile = build_writing_style_profile(
        payload=payload,
        style_analysis=style_analysis,
        topic=args.topic,
        media_files=media_files,
        extractor_outputs=extractor_outputs,
    )
    paths.profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    write_narration_brief(profile, paths.brief_path)
    return {
        "history_dir": str(paths.history_dir),
        "profile": str(paths.profile_path),
        "brief": str(paths.brief_path),
        "extractor_outputs": extractor_outputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare historical writing style references before Jianying remix.")
    parser.add_argument("--topic", required=True, help="Current video topic; used in the narration brief.")
    parser.add_argument("--media-dir", required=True, help="Current media folder used to constrain new narration content.")
    parser.add_argument("--output-dir", required=True, help="Project output directory for history_scripts artifacts.")
    parser.add_argument("--limit", type=int, default=20, help="Number of latest historical drafts to extract.")
    parser.add_argument("--root-meta", default=None, help="Optional root_meta_info.json override.")
    parser.add_argument("--jy-install", default=None, help="Optional JianyingPro install folder containing videoeditor.dll.")
    parser.add_argument("--extractor-script", default=str(DEFAULT_EXTRACTOR), help="Bundled extractor script path.")
    args = parser.parse_args()

    result = prepare(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
