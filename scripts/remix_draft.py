import argparse
import asyncio
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from skill_paths import (
    DEFAULTS_DIR,
    DEFAULT_FALLBACK_PROFILE,
    default_tts_speaker,
    resolve_asset_path,
    resolve_fallback_bundle,
    sanitize_profile,
)


VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VOICE_WAV_NAME = "narration_full.wav"
TARGET_TRACKS = {
    "video": "Template_Main_Video",
    "voice": "Template_Continuous_Voice",
    "subtitle": "Template_Subtitles_Short",
    "title": "Template_Event_Titles",
    "hero": "Template_Hero_Title",
    "note": "Template_Red_Notes",
    "sfx": "Template_Event_SFX",
    "bgm": "Template_BGM",
}
ANIMS = ["冲屏位移", "打字机_I", "弹入跳动", "辉光扫描", "弹性伸缩", "便利贴", "放大震动", "圆柱体滚动", "电光", "向右滑动", "随机弹跳", "鼠标点击"]


LEGACY_TITLE_TRACKS = {TARGET_TRACKS["title"], TARGET_TRACKS["hero"], TARGET_TRACKS["note"]}
POPUP_TITLE_TRACK_PREFIX = "Template_Popup_Title_"
POPUP_TITLE_TRACK_NAME = TARGET_TRACKS["title"]
TITLE_MIN_GAP_S = 0.55
TITLE_MIN_DURATION_S = 1.20
TITLE_MAX_DURATION_S = 1.85
DEFAULT_SOURCE_VOLUME = 1.0
DEFAULT_MUTE_MAIN_VIDEO_TRACK = True
TITLE_COLOR_PALETTE = [
    (1.0, 0.87, 0.0),
    (0.996, 0.322, 0.322),
    (0.0, 0.902, 0.463),
    (1.0, 1.0, 1.0),
    (1.0, 0.157, 0.498),
    (0.914, 0.843, 0.643),
]


def title_color_for_index(index: int) -> tuple[float, float, float]:
    return TITLE_COLOR_PALETTE[index % len(TITLE_COLOR_PALETTE)]


def title_track_name(index: int) -> str:
    return POPUP_TITLE_TRACK_NAME


def is_title_track_name(name: str | None) -> bool:
    return bool(name) and (name in LEGACY_TITLE_TRACKS or name.startswith(POPUP_TITLE_TRACK_PREFIX))


def popup_title_index(name: str | None) -> int | None:
    if not name or not name.startswith(POPUP_TITLE_TRACK_PREFIX):
        return None


def title_duration_for_row(row: dict) -> float:
    source_duration = max(0.0, float(row.get("end", 0.0)) - float(row.get("start", 0.0)))
    return round(min(TITLE_MAX_DURATION_S, max(TITLE_MIN_DURATION_S, source_duration + 0.45)), 3)


def title_start_for_row(row: dict) -> float:
    return round(max(0.0, float(row.get("start", 0.0)) + 0.03), 3)


def title_windows_conflict(start_a: float, duration_a: float, start_b: float, duration_b: float, min_gap: float = TITLE_MIN_GAP_S) -> bool:
    end_a = start_a + duration_a
    end_b = start_b + duration_b
    return start_a < end_b + min_gap and start_b < end_a + min_gap
    try:
        return max(0, int(name.removeprefix(POPUP_TITLE_TRACK_PREFIX)) - 1)
    except ValueError:
        return None


def add_jianying_skill_path(path: str | None) -> Path:
    candidates = []
    if path:
        candidates.append(Path(path))
    env = os.environ.get("JIANYING_EDITOR_SKILL")
    if env:
        candidates.append(Path(env))
    skill_root = Path(__file__).resolve().parent.parent
    candidates.append(skill_root / "vendor" / "jianying-editor-skill")
    here = Path.cwd()
    candidates.extend([here / "repo", here, here / "jianying-editor-skill"])
    for root in candidates:
        scripts = root / "scripts"
        if scripts.exists():
            sys.path.insert(0, str(scripts))
            return root
    raise FileNotFoundError("Cannot find bundled editor helper. Reinstall this skill or pass --jianying-skill to override it.")


def load_profile(path: str | None, template_draft: str | None, jy_install: str | None) -> dict:
    if path:
        return sanitize_profile(json.loads(Path(path).read_text(encoding="utf-8")))
    if not template_draft:
        return {}
    from analyze_template_style import analyze

    return analyze(Path(template_draft), jy_install)


def load_default_fallbacks(path: str | None = None) -> dict:
    if path:
        candidates = [Path(path)]
    else:
        candidates = [
            DEFAULTS_DIR / "default_fallbacks.local.json",
            DEFAULT_FALLBACK_PROFILE,
        ]
    for fallback_path in candidates:
        if fallback_path.exists():
            return resolve_fallback_bundle(json.loads(fallback_path.read_text(encoding="utf-8")))
    return {}


def missing_subtitle_style(profile: dict) -> bool:
    sub = profile.get("subtitle") or {}
    return not (sub.get("font_resource_id") or sub.get("font_path") or sub.get("text_color")) or not sub.get("font_size")


def missing_bgm(profile: dict) -> bool:
    bgm = (profile.get("audio") or {}).get("bgm") or {}
    return not (bgm.get("path") and Path(bgm["path"]).exists())


def missing_tts(profile: dict) -> bool:
    tts = (profile.get("audio") or {}).get("tts") or {}
    return not tts.get("tone_speaker")


def weak_title_style(profile: dict) -> bool:
    title = profile.get("title") or {}
    sub = profile.get("subtitle") or {}
    if not (title.get("font_resource_id") or title.get("font_path")):
        return True
    title_size = float(title.get("font_size") or 0)
    sub_size = float(sub.get("font_size") or -999)
    title_color = str(title.get("text_color") or "").lower()
    sub_color = str(sub.get("text_color") or "").lower()
    same_as_subtitle = abs(title_size - sub_size) < 0.01 and title_color == sub_color
    return same_as_subtitle and not title.get("animations")


def title_from_popup_fallback(fallbacks: dict) -> dict:
    popup = (fallbacks.get("popup_title") or {})
    styles = popup.get("styles") or {}
    style_name = popup.get("default_style") or next(iter(styles), "")
    style = styles.get(style_name) or {}
    font_path = resolve_asset_path(style.get("font_path")) or style.get("font_path")
    return {
        "font_resource_id": style.get("font_resource_id"),
        "font_path": font_path,
        "font_size": style.get("font_size") or 15.0,
        "text_color": style.get("default_text_color") or "#ffde00",
        "border_color": style.get("border_color"),
        "border_width": style.get("border_width", 0.08),
        "has_shadow": style.get("has_shadow", True),
        "shadow_alpha": style.get("shadow_alpha", 0.9),
        "shadow_color": style.get("shadow_color", "#000000"),
        "shadow_distance": style.get("shadow_distance", 5.0),
        "shadow_smoothing": style.get("shadow_smoothing", 0.45),
        "preserve_existing_color": True,
        "color_policy": popup.get("color_policy") or {},
        "animations": [],
    }


def apply_default_fallbacks(profile: dict, fallback_path: str | None = None) -> dict:
    fallback_profile = load_default_fallbacks(fallback_path)
    fallbacks = fallback_profile.get("fallbacks") or {}
    if not fallbacks:
        return profile

    profile = dict(profile)
    audio = dict(profile.get("audio") or {})
    if weak_title_style(profile):
        profile["title"] = title_from_popup_fallback(fallbacks)
    if missing_subtitle_style(profile) and fallbacks.get("subtitle"):
        sub = dict(fallbacks["subtitle"])
        resolved = resolve_asset_path(sub.get("font_path"))
        if resolved:
            sub["font_path"] = resolved
        elif sub.get("font_path"):
            sub.pop("font_path", None)
        profile["subtitle"] = sub
    if missing_bgm(profile) and fallbacks.get("bgm"):
        bgm = dict(fallbacks["bgm"])
        resolved = resolve_asset_path(bgm.get("path"))
        if resolved:
            bgm["path"] = resolved
            audio["bgm"] = bgm
    if missing_tts(profile) and fallbacks.get("tts"):
        tts = fallbacks["tts"].get("default_voice") or fallbacks["tts"]
        audio["tts"] = {k: v for k, v in tts.items() if v}
    profile["audio"] = audio
    return profile


def read_script(args) -> str:
    if args.script_file:
        return Path(args.script_file).read_text(encoding="utf-8").strip()
    if args.script:
        return args.script.strip()
    raise ValueError("Pass --script-file or --script. Write narration from the user's topic before calling remix.")


MAX_SUBTITLE_CHARS = 14


def split_subtitles(text: str) -> list[str]:
    """Short single-line subtitle chunks; avoid on-screen line wrap."""
    text = (text or "").strip()
    if not text:
        return []
    units: list[str] = []
    for sentence in re.split(r"(?<=[。！？!?；;])\s*|\n+", text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= MAX_SUBTITLE_CHARS:
            units.append(sentence)
            continue
        for clause in re.split(r"(?<=[，,、：:])", sentence):
            clause = clause.strip()
            if clause:
                units.append(clause)
    if not units:
        units = [text]
    chunks: list[str] = []
    for unit in units:
        while len(unit) > MAX_SUBTITLE_CHARS:
            chunks.append(unit[:MAX_SUBTITLE_CHARS])
            unit = unit[MAX_SUBTITLE_CHARS:]
        if unit:
            chunks.append(unit)
    return chunks or [text]


TITLE_STOP_PREFIXES = (
    "如果",
    "所以",
    "而是",
    "但是",
    "这套",
    "这个",
    "这种",
    "你可以",
    "它会",
    "它也会",
)

TITLE_KEYWORDS = (
    "核心",
    "关系",
    "影响",
    "反馈",
    "探索",
    "策略",
    "系统",
    "生态",
    "规则",
    "边界",
    "资源",
    "状态",
    "时机",
    "目标",
    "情绪",
    "风险",
    "机制",
)

TITLE_EXACT_PHRASES = (
    "宠物互动",
    "新手关卡",
    "稳定性问题",
    "生态感",
    "触发逃跑",
    "拿走食物",
    "抱走",
    "单纯数值宠物",
    "继续打磨",
    "完成品",
    "操作策略",
    "边界反馈",
    "互动反馈",
    "生态系统",
    "资源线索",
    "失败修正",
    "捕捉策略",
)

TITLE_DYNAMIC_PATTERNS = (
    re.compile(r"捕捉[^，。！？!?；;、：:\s会]{2,8}"),
    re.compile(r"[A-Za-z0-9]+[^，。！？!?；;、：:\s]{0,8}BUG"),
)





def clean_title_source(text: str) -> str:
    cleaned = re.sub(r"[，。！？!?；;、：:\s]", "", text or "")
    for prefix in TITLE_STOP_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    return cleaned


def exact_title_candidates(text: str) -> list[str]:
    cleaned = clean_title_source(text)
    candidates = [match.group(0) for pattern in TITLE_DYNAMIC_PATTERNS for match in pattern.finditer(cleaned)]
    candidates.extend(phrase for phrase in TITLE_EXACT_PHRASES if phrase in cleaned)
    if candidates:
        return list(dict.fromkeys(candidates))
    clauses = [clean_title_source(x) for x in re.split(r"[，。！？!?；;、：:\s]+", text or "")]
    return [
        clause
        for clause in clauses
        if 2 <= len(clause) <= 10 and any(keyword in clause for keyword in TITLE_KEYWORDS)
    ]


def core_title_for_text(text: str) -> str:
    candidates = exact_title_candidates(text)
    if candidates:
        return max(candidates, key=lambda item: (sum(keyword in item for keyword in TITLE_KEYWORDS), len(item)))
    return ""


def title_rank(title: str) -> float:
    if title.startswith("捕捉"):
        return 2.5
    if "BUG" in title.upper():
        return 8.5
    try:
        return float(TITLE_EXACT_PHRASES.index(title))
    except ValueError:
        return float(len(TITLE_EXACT_PHRASES) + 10)


def safe_title_position(index: int, event_count: int, title: str) -> tuple[float, float]:
    positions = [
        (-0.24, 0.48),
        (0.24, 0.42),
        (-0.20, 0.30),
        (0.20, 0.18),
        (0.00, 0.54),
        (0.00, 0.12),
    ]
    x, y = positions[index % len(positions)]
    max_x = max(0.12, 0.34 - max(0, len(title) - 4) * 0.018)
    x = max(-max_x, min(max_x, x))
    y = max(0.06, min(0.56, y))
    return x, y


def event_title_specs(rows: list[dict], event_count: int | None = None) -> list[dict]:
    if not rows:
        return []
    count = event_count if event_count is not None else min(12, max(4, len(rows) // 5))
    used = set()
    candidates = []
    for row_index, row in enumerate(rows):
        for title in exact_title_candidates(row["text"]):
            if title in used:
                continue
            used.add(title)
            score = (
                (100 - title_rank(title)) * 100
                + sum(keyword in title for keyword in TITLE_KEYWORDS) * 10
                + max(0, 8 - abs(len(title) - 4))
            )
            candidates.append({"row_index": row_index, "text": title, "score": score})
    selected = []
    for item in sorted(candidates, key=lambda item: (-item["score"], item["row_index"])):
        row = rows[item["row_index"]]
        start = title_start_for_row(row)
        duration = title_duration_for_row(row)
        if any(title_windows_conflict(start, duration, old["start"], old["duration"]) for old in selected):
            continue
        selected.append({**item, "start": start, "duration": duration})
        if len(selected) >= count:
            break
    selected.sort(key=lambda item: item["start"])
    specs = []
    for order, item in enumerate(selected):
        title = item["text"]
        x, y = safe_title_position(order, len(selected), title)
        specs.append({
            "row_index": item["row_index"],
            "text": title,
            "x": x,
            "y": y,
            "start": item["start"],
            "duration": item["duration"],
        })
    return specs


def find_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    roots = [Path.home() / "Documents" / "Codex"]
    for root in roots:
        if root.exists():
            for candidate in root.rglob(f"{name}.exe"):
                return str(candidate)
    raise FileNotFoundError(f"missing {name}; install ffmpeg or provide it on PATH")


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


def grouped_chunks(chunks: list[str], max_chars: int = 80) -> list[dict]:
    groups = []
    current = []
    start_index = 0
    count = 0
    for idx, chunk in enumerate(chunks):
        if current and count + len(chunk) > max_chars:
            groups.append({"start_index": start_index, "chunks": current})
            current = []
            start_index = idx
            count = 0
        current.append(chunk)
        count += len(chunk)
    if current:
        groups.append({"start_index": start_index, "chunks": current})
    return groups


async def generate_voice(chunks: list[str], speaker: str, output_file: Path) -> tuple[float, list[dict]]:
    from universal_tts import generate_voice_with_meta

    output_file.parent.mkdir(parents=True, exist_ok=True)
    chunk_dir = output_file.parent / "voice_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    groups = grouped_chunks(chunks)
    paths = []
    for idx, group in enumerate(groups, start=1):
        chunk_path = chunk_dir / f"voice_{idx:02d}.ogg"
        actual, backend = await generate_voice_with_meta(
            "".join(group["chunks"]),
            str(chunk_path),
            speaker,
            backend="sami",
            allow_fallback=False,
            sami_retries=2,
        )
        if not actual:
            raise RuntimeError(f"TTS failed for chunk {idx}")
        duration = probe_duration(chunk_path)
        if duration <= 0:
            raise RuntimeError(f"TTS chunk is not parseable: {chunk_path}")
        group["raw_duration"] = duration
        paths.append(chunk_path)

    list_file = chunk_dir / "concat.txt"
    list_file.write_text("\n".join(f"file '{str(p)}'" for p in paths), encoding="utf-8")
    raw_wav = output_file.with_name(output_file.stem + "_raw.wav")
    ffmpeg = find_binary("ffmpeg")
    subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(raw_wav)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    shutil.copyfile(raw_wav, output_file)

    total = probe_duration(output_file)
    for group in groups:
        group["duration"] = group["raw_duration"]
    group_sum = sum(g["duration"] for g in groups)
    if total > 0 and group_sum > 0:
        scale = total / group_sum
        for group in groups:
            group["duration"] *= scale
    return total, groups


def subtitle_timings(groups: list[dict], total: float) -> list[dict]:
    rows = []
    cursor = 0.0
    gap = 0.02
    for group in groups:
        weights = [max(4, len(x)) for x in group["chunks"]]
        usable = max(0.01, group["duration"] - gap * max(0, len(weights) - 1))
        unit = usable / sum(weights)
        for text, weight in zip(group["chunks"], weights):
            dur = max(0.5, weight * unit)
            rows.append({"text": text, "start": cursor, "end": min(total, cursor + dur)})
            cursor += dur + gap
    if rows:
        rows[-1]["end"] = min(total, rows[-1]["end"])
    return rows


def load_external_voice(voice_file: Path, voice_groups_file: Path) -> tuple[float, list[dict]]:
    if not voice_file.exists():
        raise FileNotFoundError(f"external voice file not found: {voice_file}")
    if not voice_groups_file.exists():
        raise FileNotFoundError(f"external voice groups file not found: {voice_groups_file}")
    payload = json.loads(voice_groups_file.read_text(encoding="utf-8"))
    groups = payload.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError(f"external voice groups are missing or empty: {voice_groups_file}")
    duration = float(payload.get("duration") or 0.0)
    if duration <= 0:
        duration = probe_duration(voice_file)
    if duration <= 0:
        raise ValueError(f"external voice duration is unavailable: {voice_file}")
    for group in groups:
        if "duration" not in group or "chunks" not in group:
            raise ValueError("external voice groups must include duration and chunks")
    return duration, groups


def voice_for_script(
    chunks: list[str],
    external_voice_file: str | None,
    external_voice_groups_file: str | None,
    speaker: str,
    generated_voice_path: Path,
) -> tuple[Path, float, list[dict]]:
    if external_voice_file or external_voice_groups_file:
        if not external_voice_file or not external_voice_groups_file:
            raise ValueError("pass both --voice-file and --voice-groups-file for external narration")
        voice_path = Path(external_voice_file)
        duration, groups = load_external_voice(voice_path, Path(external_voice_groups_file))
        group_chunks = [chunk for group in groups for chunk in group.get("chunks", [])]
        if group_chunks != chunks:
            raise ValueError("external voice groups do not match confirmed script chunks")
        return voice_path, duration, groups
    duration, groups = asyncio.run(generate_voice(chunks, speaker, generated_voice_path))
    return generated_voice_path, duration, groups


def hex_to_rgb(hex_color: str, default=(1.0, 1.0, 1.0)):
    if not hex_color or not hex_color.startswith("#") or len(hex_color) < 7:
        return default
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))


def text_fill_color(mat: dict) -> tuple | None:
    try:
        content = json.loads(mat.get("content") or "{}")
        style = (content.get("styles") or [{}])[0]
        color = style.get("fill", {}).get("content", {}).get("solid", {}).get("color")
        if isinstance(color, list) and len(color) >= 3:
            return tuple(float(x) for x in color[:3])
    except Exception:
        pass
    return None


def generate_fallback_sfx(out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    def tone(name, pattern):
        path = out_dir / f"{name}.wav"
        if path.exists():
            return path
        samples = []
        sample_rate = 44100
        for freq, dur, volume in pattern:
            for i in range(int(sample_rate * dur)):
                t = i / sample_rate
                fade = min(1.0, i / 200, (int(sample_rate * dur) - i) / 200)
                samples.append(int(math.sin(2 * math.pi * freq * t) * volume * fade * 32767))
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(b"".join(struct.pack("<h", max(-32767, min(32767, x))) for x in samples))
        return path

    return {
        "start": tone("start", [(220, 0.16, 0.45), (110, 0.22, 0.34)]),
        "tech": tone("tech", [(740, 0.05, 0.20), (1110, 0.05, 0.18), (1480, 0.08, 0.14)]),
        "sparkle": tone("sparkle", [(1568, 0.04, 0.24), (2093, 0.05, 0.20), (2637, 0.08, 0.16)]),
        "soft": tone("soft", [(330, 0.05, 0.25), (660, 0.10, 0.16)]),
        "alert": tone("alert", [(220, 0.05, 0.32), (196, 0.06, 0.28), (164, 0.10, 0.24)]),
        "whoosh": tone("whoosh", [(360, 0.04, 0.12), (520, 0.05, 0.16), (780, 0.08, 0.20)]),
        "impact": tone("impact", [(130, 0.06, 0.34), (82, 0.12, 0.28)]),
    }


def media_files(media_dir: Path) -> list[Path]:
    files = [
        p for p in media_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in (VIDEO_EXTS | IMAGE_EXTS)
    ]
    return sorted(files, key=lambda p: (p.suffix.lower() not in VIDEO_EXTS, p.name.lower()))


def sanitize_file_stem(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text, flags=re.UNICODE).strip("_") or "media"


def text_window(rows: list[dict], start: float, end: float) -> str:
    parts = [
        row["text"]
        for row in rows
        if row.get("start", 0) < end + 0.8 and row.get("end", 0) > start - 0.8
    ]
    return "".join(parts) or (rows[0]["text"] if rows else "")


MEDIA_LABEL_KEYWORDS = {
    "opening": ("开局", "开始", "初遇", "首次", "第一次", "见到", "登场", "入口", "地图", "环境", "intro", "opening", "开场"),
    "tutorial": ("新手", "教程", "教学", "关卡", "规则", "目标", "尝试", "修正", "策略", "tutorial"),
    "food": ("食物", "吃", "投喂", "喂食", "拿走", "抢走", "food"),
    "angry": ("生气", "愤怒", "发怒", "暴躁", "情绪", "angry"),
    "sleep": ("睡着", "睡觉", "休息", "sleep"),
    "capture": ("捕捉", "捕获", "抓捕", "抓到", "收服", "capture"),
    "escape": ("逃跑", "逃走", "逃离", "escape"),
    "carry": ("抱走", "抱起", "带走", "搬走", "带离", "carry"),
    "boss": ("BOSS", "Boss", "boss", "首领"),
    "bug": ("BUG", "Bug", "bug", "故障", "异常"),
    "teleport": ("传送", "瞬移"),
    "unstuck": ("脱离", "卡死", "卡住"),
    "system": ("系统", "生态", "机制", "关系", "群落", "世界"),
}

MEDIA_LABEL_WEIGHTS = {
    "opening": 64,
    "tutorial": 62,
    "food": 46,
    "angry": 52,
    "sleep": 42,
    "capture": 38,
    "escape": 48,
    "carry": 58,
    "boss": 44,
    "bug": 44,
    "teleport": 44,
    "unstuck": 48,
    "system": 22,
}


def labels_for_text(text: str) -> set[str]:
    labels = set()
    for label, keywords in MEDIA_LABEL_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            labels.add(label)
    return labels


def score_media_for_text(path: Path, text: str) -> tuple[int, str]:
    name = path.stem
    name_labels = set(media_name_labels(path))
    text_labels = labels_for_text(text)
    matched = name_labels & text_labels
    score = 1 + sum(MEDIA_LABEL_WEIGHTS.get(label, 20) for label in matched)

    if {"sleep", "capture"} <= name_labels and ({"sleep", "capture"} & text_labels):
        score += 28
        matched.add("sleep-capture")
    if ({"sleep", "escape"} & name_labels) and not ({"sleep", "escape"} & text_labels):
        score -= 34
    if {"food", "angry"} <= name_labels and ({"food", "angry"} & text_labels):
        score += 32
        matched.add("food-emotion")
    if {"boss", "bug", "teleport"} & name_labels and not ({"boss", "bug", "teleport"} & text_labels):
        score -= 30
    if "unstuck" in name_labels and "unstuck" not in text_labels:
        score -= 30
    if "system" in text_labels and name_labels & {"opening", "tutorial"}:
        score += 10

    compact_name = re.sub(r"[^\w\u4e00-\u9fff]+", "", name, flags=re.UNICODE)
    compact_text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE)
    for size in (4, 3, 2):
        grams = {compact_name[i:i + size] for i in range(max(0, len(compact_name) - size + 1))}
        grams = {gram for gram in grams if len(gram) == size}
        overlap = [gram for gram in grams if gram in compact_text]
        if overlap:
            score += min(18, len(overlap) * (size + 1))
            matched.add("name-overlap")
            break

    return score, "+".join(sorted(matched)) or "fallback"


def media_name_labels(path: Path) -> list[str]:
    return sorted(labels_for_text(path.stem))


def unrecognized_media_files(files: list[Path]) -> list[Path]:
    return [path for path in files if path.suffix.lower() in VIDEO_EXTS and not media_name_labels(path)]


def media_observation_key(path: Path) -> str:
    return str(path)


def observation_for(path: Path, observations: dict | None) -> dict:
    observations = observations or {}
    return observations.get(media_observation_key(path)) or observations.get(path.name) or {}


def source_start_for_clip(path: Path, context: str, clip_duration: float, observations: dict | None) -> float:
    duration = float(observation_for(path, observations).get("duration") or 0.0)
    if duration <= clip_duration + 1.0:
        return 0.0
    labels = set(media_name_labels(path))
    if "opening" in labels and labels_for_text(context) & {"opening"}:
        return 0.3

    ratio = 0.12
    if labels & {"capture", "food", "carry", "angry", "escape"}:
        ratio = 0.22
    elif "tutorial" in labels:
        ratio = 0.16
    elif labels & {"boss", "bug", "teleport", "unstuck"}:
        ratio = 0.24
    return round(min(max(0.8, duration * ratio), max(0.0, duration - clip_duration - 0.3)), 3)


def build_clip_plan(
    files: list[Path],
    rows: list[dict],
    voice_duration: float,
    observations: dict | None = None,
    target_clip_s: float = 5.0,
) -> list[dict]:
    if not files:
        return []
    minimum = 8 if len(files) > 1 else 1
    clip_count = min(14, max(minimum, int(round(max(1.0, voice_duration) / target_clip_s))))
    clip_duration = voice_duration / clip_count
    usage: dict[Path, int] = {}
    plan = []
    for idx in range(clip_count):
        start = idx * clip_duration
        end = min(voice_duration, start + clip_duration)
        context = text_window(rows, start, end)
        ranked = []
        for path in files:
            score, reason = score_media_for_text(path, context)
            score -= usage.get(path, 0) * 8
            ranked.append((score, reason, path))
        score, reason, path = max(ranked, key=lambda item: (item[0], -files.index(item[2])))
        usage[path] = usage.get(path, 0) + 1
        plan.append({
            "path": path,
            "start": start,
            "duration": max(1.0, end - start - 0.005),
            "source_start": source_start_for_clip(path, context, clip_duration, observations),
            "reason": reason,
            "context": context[:80],
        })
    return plan


def analyze_media_assets(files: list[Path], out_dir: Path, extract_frames: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    observations = {}
    for path in files:
        duration = probe_duration(path) if path.suffix.lower() in VIDEO_EXTS else 0.0
        item = {"duration": duration, "labels": media_name_labels(path), "sample_frames": []}
        if extract_frames and duration > 0:
            for idx, ts in enumerate((max(0.5, duration * 0.18), max(0.5, duration * 0.55)), start=1):
                frame_path = out_dir / f"{sanitize_file_stem(path.stem)}_{idx:02d}.jpg"
                if not frame_path.exists():
                    subprocess.run(
                        [
                            find_binary("ffmpeg"),
                            "-y",
                            "-ss",
                            f"{min(ts, max(0.0, duration - 0.2)):.3f}",
                            "-i",
                            str(path),
                            "-frames:v",
                            "1",
                            "-vf",
                            "scale=480:-1",
                            str(frame_path),
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                if frame_path.exists():
                    item["sample_frames"].append(str(frame_path))
        observations[media_observation_key(path)] = item
    (out_dir / "media_analysis.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
    return observations


def patch_text_content(mat: dict, font_id: str | None, font_path: str | None, size: float, fill: list[float], subtitle: bool, style_source: dict | None = None) -> None:
    content = json.loads(mat.get("content") or "{}")
    text = content.get("text", "")
    style = {
        "fill": {"content": {"render_type": "solid", "solid": {"color": fill}}},
        "size": size,
        "range": [0, len(text)],
    }
    if font_id or font_path:
        style["font"] = {"id": font_id or "", "path": font_path or ""}
    style_source = style_source or {}
    if subtitle or style_source.get("has_shadow"):
        style["useLetterColor"] = True
        style["shadows"] = [{
            "alpha": float(style_source.get("shadow_alpha", 0.8999999761581421)),
            "distance": float(style_source.get("shadow_distance", 4.999999523162842)),
            "diffuse": 0.02500000037252903,
            "angle": -45,
            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}},
        }]
    if not subtitle:
        style["bold"] = True
    content["styles"] = [style]
    content["text"] = text
    mat["content"] = json.dumps(content, ensure_ascii=False, separators=(",", ":"))


def patch_draft(draft_path: Path, profile: dict, speaker: str, voice_path: Path) -> None:
    content_path = draft_path / "draft_content.json"
    data = json.loads(content_path.read_text(encoding="utf-8"))
    set_main_video_track_mute(data)
    subtitle_ids = track_ids(data, {TARGET_TRACKS["subtitle"]})
    title_ids = title_track_ids(data)
    popup_title_colors = popup_title_color_ids(data)
    sub = profile.get("subtitle", {})
    title = profile.get("title", {})

    for mat in data.get("materials", {}).get("texts", []):
        mid = mat.get("id")
        if mid in subtitle_ids:
            color = hex_to_rgb(sub.get("text_color", "#ffffff"))
            patch_text_content(mat, sub.get("font_resource_id"), sub.get("font_path"), float(sub.get("font_size") or 9.0), list(color), True)
            mat.update({
                "type": "subtitle",
                "font_resource_id": sub.get("font_resource_id", mat.get("font_resource_id", "")),
                "font_path": sub.get("font_path", mat.get("font_path", "")),
                "font_size": float(sub.get("font_size") or 9.0),
                "check_flag": 55,
                "background_style": sub.get("background_style", 1),
                "background_color": sub.get("background_color", "#000000"),
                "background_alpha": sub.get("background_alpha", 0.16),
                "background_width": sub.get("background_width", 0.0),
                "background_height": sub.get("background_height", 0.0),
                "has_shadow": sub.get("has_shadow", True),
                "shadow_alpha": sub.get("shadow_alpha", 0.9),
                "shadow_color": sub.get("shadow_color", "#000000"),
                "shadow_distance": sub.get("shadow_distance", 5.0),
                "shadow_smoothing": sub.get("shadow_smoothing", 0.45),
                "border_width": sub.get("border_width", 0.08),
                "line_spacing": sub.get("line_spacing", 0.02),
                "layer_weight": 1,
            })
        elif mid in title_ids:
            color = popup_title_colors.get(mid)
            if color is None and title.get("preserve_existing_color"):
                color = text_fill_color(mat)
            color = color or hex_to_rgb(title.get("text_color", "#ffde00"), (1.0, 0.87, 0.0))
            patch_text_content(mat, title.get("font_resource_id"), title.get("font_path"), float(title.get("font_size") or 15.0), list(color), False, title)
            mat.update({
                "type": "text",
                "font_resource_id": title.get("font_resource_id", mat.get("font_resource_id", "")),
                "font_path": title.get("font_path", mat.get("font_path", "")),
                "border_color": title.get("border_color", "#000000"),
                "border_width": title.get("border_width", 0.08),
                "has_shadow": title.get("has_shadow", True),
                "shadow_alpha": title.get("shadow_alpha", 0.9),
                "shadow_color": title.get("shadow_color", "#000000"),
                "shadow_distance": title.get("shadow_distance", 5.0),
                "shadow_smoothing": title.get("shadow_smoothing", 0.45),
            })

    for mat in data.get("materials", {}).get("audios", []):
        path = mat.get("path", "")
        if os.path.normpath(path) == os.path.normpath(str(voice_path)):
            mat.update({
                "type": "text_to_audio",
                "tone_speaker": speaker,
                "tone_platform": profile.get("audio", {}).get("tts", {}).get("tone_platform", "sami"),
                "resource_id": profile.get("audio", {}).get("tts", {}).get("resource_id", ""),
                "tts_generate_scene": "audio_panel",
            })
        bgm = profile.get("audio", {}).get("bgm", {})
        if bgm.get("path") and os.path.normpath(path) == os.path.normpath(bgm["path"]):
            mat.update({k: v for k, v in bgm.items() if k in {"name", "music_id", "category_id"} and v})

    content_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def track_ids(data: dict, names: set[str]) -> set[str]:
    ids = set()
    for track in data.get("tracks", []):
        if track.get("name") in names:
            for seg in track.get("segments", []):
                if seg.get("material_id"):
                    ids.add(seg["material_id"])
    return ids


def title_track_ids(data: dict) -> set[str]:
    ids = set()
    for track in data.get("tracks", []):
        if is_title_track_name(track.get("name")):
            for seg in track.get("segments", []):
                if seg.get("material_id"):
                    ids.add(seg["material_id"])
    return ids


def popup_title_color_ids(data: dict) -> dict[str, tuple[float, float, float]]:
    segments = []
    for track in data.get("tracks", []):
        if not is_title_track_name(track.get("name")):
            continue
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            if mid:
                start = seg.get("target_timerange", {}).get("start", 0)
                segments.append((start, mid))
    colors = {}
    for index, (_, mid) in enumerate(sorted(segments)):
        colors[mid] = title_color_for_index(index)
    return colors


def set_main_video_track_mute(data: dict, mute: bool = DEFAULT_MUTE_MAIN_VIDEO_TRACK) -> None:
    data.setdefault("config", {})["video_mute"] = False
    for track in data.get("tracks", []):
        if track.get("name") == TARGET_TRACKS["video"]:
            track["attribute"] = int(bool(mute))
            track.setdefault("flag", 0)


def add_motion(seg, draft, duration: float, mode: int):
    try:
        from pyJianYingDraft.keyframe import KeyframeProperty as KP
        scale_end = 1.025 + (mode % 3) * 0.018
        seg.add_keyframe(KP.uniform_scale, 0, 1.0)
        seg.add_keyframe(KP.uniform_scale, f"{duration:.3f}s", scale_end)
        if mode % 4 == 1:
            seg.add_keyframe(KP.position_x, 0, -0.025)
            seg.add_keyframe(KP.position_x, f"{duration:.3f}s", 0.025)
        elif mode % 4 == 2:
            seg.add_keyframe(KP.position_x, 0, 0.025)
            seg.add_keyframe(KP.position_x, f"{duration:.3f}s", -0.025)
    except Exception:
        pass


def build(args) -> dict:
    skill_root = add_jianying_skill_path(args.jianying_skill)
    from jy_wrapper import JyProject, draft

    fallback_bundle = load_default_fallbacks(args.fallback_profile)
    profile = sanitize_profile(
        apply_default_fallbacks(load_profile(args.style_profile, args.template_draft, args.jy_install), args.fallback_profile)
    )
    script_text = read_script(args)
    chunks = split_subtitles(script_text)
    speaker = (
        args.speaker
        or profile.get("audio", {}).get("tts", {}).get("tone_speaker")
        or default_tts_speaker(fallback_bundle)
    )
    if not speaker and not args.voice_file:
        raise ValueError("No TTS speaker found in template or fallbacks; pass --speaker.")
    if not speaker:
        speaker = args.voice_provider or "external_voice"

    project = JyProject(args.draft_name, width=args.width, height=args.height, overwrite=True)
    temp_dir = Path(project.root) / project.name / "temp_assets"
    generated_voice_path = temp_dir / VOICE_WAV_NAME
    voice_path, voice_duration, voice_groups = voice_for_script(
        chunks,
        args.voice_file,
        args.voice_groups_file,
        speaker,
        generated_voice_path,
    )
    rows = subtitle_timings(voice_groups, voice_duration)

    voice = project.add_audio_safe(str(voice_path), start_time="0s", duration=f"{voice_duration:.3f}s", track_name=TARGET_TRACKS["voice"])
    if voice:
        voice.volume = args.voice_volume
        duration_us = int(voice_duration * 1_000_000)
        voice.duration = duration_us
        voice.source_timerange.duration = duration_us
        voice.material_instance.duration = duration_us

    files = media_files(Path(args.media_dir))
    if not files:
        raise FileNotFoundError(f"no media files found in {args.media_dir}")
    unknown_files = unrecognized_media_files(files)
    if unknown_files and not args.analyze_frames:
        names = ", ".join(path.name for path in unknown_files)
        raise ValueError(
            "Cannot infer scene labels from these media filenames: "
            f"{names}. Rename them with descriptive scene/action words, or rerun with --analyze-frames after the user confirms frame analysis."
        )
    observations = analyze_media_assets(files, temp_dir / "media_analysis", extract_frames=args.analyze_frames)
    clip_plan = build_clip_plan(files, rows, voice_duration, observations=observations)
    plan_json = [
        {
            **{k: v for k, v in item.items() if k != "path"},
            "path": str(item["path"]),
            "name": item["path"].name,
        }
        for item in clip_plan
    ]
    media_plan_path = temp_dir / "media_plan.json"
    media_plan_path.write_text(json.dumps(plan_json, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(media_plan_path, out_dir / "media_plan.json")
    for idx, item in enumerate(clip_plan):
        path = item["path"]
        dur = item["duration"]
        seg = project.add_media_safe(
            str(path),
            start_time=f"{item['start']:.3f}s",
            duration=f"{dur:.3f}s",
            track_name=TARGET_TRACKS["video"],
            source_start=f"{item['source_start']:.3f}s",
        )
        if seg:
            seg.volume = args.source_volume
            add_motion(seg, draft, dur, idx)

    total_duration = voice_duration
    sub = profile.get("subtitle", {})
    sub_y = (sub.get("transform") or {}).get("y", -0.85)
    for row in rows:
        project.add_text_simple(
            row["text"],
            start_time=f"{row['start']:.3f}s",
            duration=f"{max(0.35, row['end'] - row['start']):.3f}s",
            track_name=TARGET_TRACKS["subtitle"],
            style=draft.TextStyle(size=float(sub.get("font_size") or 9.0), color=hex_to_rgb(sub.get("text_color", "#ffffff")), align=1, auto_wrapping=False, max_line_width=0.92),
            background=draft.TextBackground(color=sub.get("background_color", "#000000"), style=int(sub.get("background_style", 1)), alpha=float(sub.get("background_alpha", 0.16)), width=0.0, height=0.0),
            shadow=draft.TextShadow(color=(0, 0, 0), alpha=float(sub.get("shadow_alpha", 0.9)), distance=float(sub.get("shadow_distance", 5.0)), angle=-45.0, diffuse=float(sub.get("shadow_smoothing", 0.45))),
            clip_settings=draft.ClipSettings(transform_y=float(sub_y)),
        )

    fallback_sfx = generate_fallback_sfx(temp_dir / "fallback_sfx")
    title_style = profile.get("title", {})
    title_specs = event_title_specs(rows)
    sfx_names = list(fallback_sfx)
    for n, spec in enumerate(title_specs):
        phrase = spec["text"]
        x, y = spec["x"], spec["y"]
        start = float(spec["start"])
        duration = float(spec["duration"])
        track = title_track_name(n)
        color = title_color_for_index(n)
        project.add_text_simple(
            phrase,
            start_time=f"{start:.3f}s",
            duration=f"{duration:.3f}s",
            track_name=track,
            style=draft.TextStyle(size=float(title_style.get("font_size") or 15.0), bold=True, color=color, align=1, auto_wrapping=True, max_line_width=0.5),
            border=draft.TextBorder(color=(0, 0, 0), alpha=1.0, width=8.0),
            clip_settings=draft.ClipSettings(transform_x=x, transform_y=y),
            anim_in=ANIMS[n % len(ANIMS)],
            anim_in_duration="0.50s",
            anim_out="渐隐",
            anim_out_duration="0.30s",
        )
        sfx_path = fallback_sfx[sfx_names[n % len(sfx_names)]]
        seg = project.add_audio_safe(str(sfx_path), start_time=f"{max(0, start):.3f}s", duration="0.60s", track_name=TARGET_TRACKS["sfx"])
        if seg:
            seg.volume = 0.45 + (n % 4) * 0.08

    bgm = profile.get("audio", {}).get("bgm", {})
    if not (bgm.get("path") and Path(bgm["path"]).exists()):
        fallback_bgm = (fallback_bundle.get("bgm") or {})
        resolved = resolve_asset_path(fallback_bgm.get("path"))
        if resolved:
            bgm = {**fallback_bgm, "path": resolved}
    if bgm.get("path") and Path(bgm["path"]).exists():
        seg = project.add_audio_safe(bgm["path"], start_time="0s", duration=f"{total_duration:.3f}s", track_name=TARGET_TRACKS["bgm"])
        if seg:
            seg.volume = args.bgm_volume

    result = project.save()
    draft_path = Path(result["draft_path"])
    patch_draft(draft_path, profile, speaker, voice_path)
    return {"status": "SUCCESS", "draft_path": str(draft_path), "duration": total_duration, "subtitle_rows": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template-draft")
    parser.add_argument("--style-profile")
    parser.add_argument("--fallback-profile")
    parser.add_argument("--media-dir", required=True)
    parser.add_argument("--script-file")
    parser.add_argument("--script")
    parser.add_argument("--output-dir", help="Copy media_plan.json and build metadata here (outside the skill directory).")
    parser.add_argument("--draft-name", required=True)
    parser.add_argument(
        "--target-duration",
        type=float,
        default=0.0,
        help="Optional rough script-length hint for the agent only. TTS is never time-stretched to match this.",
    )
    parser.add_argument("--speaker")
    parser.add_argument("--voice-file", help="Confirmed externally generated narration audio, such as Fish Audio output.")
    parser.add_argument("--voice-groups-file", help="Timing/chunk groups for --voice-file.")
    parser.add_argument("--voice-provider", default="jianying_tts", help="Voice provider label for handoff metadata.")
    parser.add_argument("--jianying-skill")
    parser.add_argument("--jy-install")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--voice-volume", type=float, default=1.48)
    parser.add_argument("--bgm-volume", type=float, default=0.40)
    parser.add_argument("--source-volume", type=float, default=DEFAULT_SOURCE_VOLUME)
    parser.add_argument("--analyze-frames", action="store_true", help="Extract sample frames only when the user explicitly approves visual frame analysis.")
    args = parser.parse_args()
    print(json.dumps(build(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
