import argparse
import csv
import ctypes
import json
import os
import pathlib
import re
import sys
import datetime as dt


DEC_SYMBOL = "?decrypt@EncryptUtils@lvve@@QEAA?AV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@AEBV34@0AEA_N@Z"
PUNCTUATION = "，。！？；：、…,.!?;:"
FINAL_PUNCTUATION = "。！？.!?"


class _StringData(ctypes.Union):
    _fields_ = [("small", ctypes.c_char * 16), ("ptr", ctypes.c_void_p)]


class MsvcString(ctypes.Structure):
    _fields_ = [
        ("data", _StringData),
        ("size", ctypes.c_ulonglong),
        ("capacity", ctypes.c_ulonglong),
    ]


def make_msvc_string(payload):
    storage = ctypes.create_string_buffer(payload + b"\0")
    value = MsvcString()
    value.size = len(payload)
    if len(payload) < 16:
        value.capacity = 15
        ctypes.memset(ctypes.addressof(value.data), 0, 16)
        ctypes.memmove(ctypes.addressof(value.data), payload, len(payload))
    else:
        value.capacity = len(payload)
        value.data.ptr = ctypes.cast(storage, ctypes.c_void_p).value
    return value, storage


def take_msvc_string(value):
    if value.size > (1 << 34):
        raise RuntimeError(f"refusing suspicious output size: {value.size}")
    if value.capacity < 16:
        return bytes(value.data.small[: value.size])
    if not value.data.ptr:
        return b""
    return ctypes.string_at(value.data.ptr, value.size)


def decrypt_bytes(install_dir, encrypted):
    dll_path = pathlib.Path(install_dir) / "videoeditor.dll"
    if not dll_path.exists():
        raise FileNotFoundError(f"videoeditor.dll not found: {dll_path}")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetErrorMode(0x0001 | 0x8000)
    kernel32.SetDefaultDllDirectories.argtypes = [ctypes.c_uint32]
    kernel32.SetDefaultDllDirectories.restype = ctypes.c_bool
    kernel32.AddDllDirectory.argtypes = [ctypes.c_wchar_p]
    kernel32.AddDllDirectory.restype = ctypes.c_void_p
    kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p

    load_dll_dir = 0x00000100
    load_app_dir = 0x00000200
    load_user_dirs = 0x00000400
    load_system32 = 0x00000800

    kernel32.SetDefaultDllDirectories(load_app_dir | load_system32 | load_user_dirs)
    kernel32.AddDllDirectory(str(dll_path.parent))
    handle = kernel32.LoadLibraryExW(
        str(dll_path),
        None,
        load_dll_dir | load_app_dir | load_user_dirs | load_system32,
    )
    if not handle:
        raise OSError(f"LoadLibraryExW failed gle={ctypes.get_last_error()} path={dll_path}")

    dll = ctypes.WinDLL(str(dll_path), handle=handle)
    decrypt = getattr(dll, DEC_SYMBOL)
    decrypt.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(MsvcString),
        ctypes.POINTER(MsvcString),
        ctypes.POINTER(MsvcString),
        ctypes.POINTER(ctypes.c_bool),
    ]
    decrypt.restype = ctypes.POINTER(MsvcString)

    in_s, in_storage = make_msvc_string(encrypted)
    param_s, param_storage = make_msvc_string(b"{}")
    ret_s = MsvcString()
    ok = ctypes.c_bool(False)

    decrypt(None, ctypes.byref(ret_s), ctypes.byref(in_s), ctypes.byref(param_s), ctypes.byref(ok))
    plain = take_msvc_string(ret_s)
    if not ok.value or not plain:
        raise RuntimeError("decrypt failed")
    return plain


def default_root_meta():
    local_app_data = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home() / "AppData/Local"))
    return local_app_data / "JianyingPro/User Data/Projects/com.lveditor.draft/root_meta_info.json"


def candidate_install_dirs():
    candidates = []
    local_app_data = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home() / "AppData/Local"))
    candidates.extend(local_app_data.glob("JianyingPro/Apps/*"))
    candidates.extend(local_app_data.glob("JianyingPro/*"))
    for root in [pathlib.Path("C:/Program Files"), pathlib.Path("C:/Program Files (x86)"), pathlib.Path("D:/"), pathlib.Path("F:/")]:
        if root.exists():
            candidates.extend(root.glob("JianyingPro/*"))
            candidates.extend(root.glob("CapCut/*"))
            direct = root / "JianyingPro"
            if direct.exists():
                candidates.extend(direct.glob("*"))
    return [path for path in candidates if (path / "videoeditor.dll").exists()]


def find_jy_install(explicit):
    if explicit:
        path = pathlib.Path(explicit)
        if (path / "videoeditor.dll").exists():
            return path
        raise FileNotFoundError(f"--jy-install does not contain videoeditor.dll: {path}")
    candidates = sorted(candidate_install_dirs(), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def is_plain_json(path):
    return pathlib.Path(path).read_bytes()[:64].lstrip().startswith((b"{", b"["))


def load_draft_json(path, install_dir):
    path = pathlib.Path(path)
    raw = path.read_bytes()
    if raw[:64].lstrip().startswith((b"{", b"[")):
        return json.loads(raw.decode("utf-8"))
    if not install_dir:
        raise RuntimeError("draft is encrypted and no videoeditor.dll install dir was found")
    return json.loads(decrypt_bytes(install_dir, raw).decode("utf-8"))


def fmt_modified(microseconds):
    if not microseconds:
        return ""
    return dt.datetime.fromtimestamp(microseconds / 1_000_000).strftime("%Y-%m-%d %H:%M:%S")


def fmt_time(microseconds):
    total_ms = round(int(microseconds or 0) / 1000)
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    seconds = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"
    return f"{minutes:02d}:{seconds:02d}.{ms:03d}"


def load_text(material):
    if not material:
        return ""
    raw = material.get("content")
    value = ""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            value = parsed.get("text") or parsed.get("content") or "" if isinstance(parsed, dict) else str(parsed)
        except Exception:
            value = raw
    elif isinstance(raw, dict):
        value = raw.get("text") or raw.get("content") or ""
    if not value:
        for key in ["words", "current_words", "text"]:
            maybe = material.get(key)
            if isinstance(maybe, str) and maybe.strip():
                value = maybe
                break
    value = str(value).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"<[^>]+>", "", value)
    return value.strip()


def segment_material_ids(segment):
    ids = []
    if segment.get("material_id"):
        ids.append(segment["material_id"])
    for material_id in segment.get("material_ids") or []:
        if material_id not in ids:
            ids.append(material_id)
    return ids


def collect_segment_text(segment, texts, text_templates):
    pieces = []
    sources = []
    for material_id in segment_material_ids(segment):
        direct = load_text(texts.get(material_id))
        if direct:
            pieces.append(direct)
            sources.append("texts")
        template = text_templates.get(material_id)
        if template:
            for info in template.get("text_info_resources") or []:
                nested = load_text(texts.get(info.get("text_material_id")))
                if nested:
                    pieces.append(nested)
                    sources.append("text_templates->texts")
    deduped = []
    for piece in pieces:
        if piece not in deduped:
            deduped.append(piece)
    return " / ".join(deduped).strip(), "+".join(sorted(set(sources)))


def extract_text_tracks(data):
    materials = data.get("materials", {})
    texts = {item.get("id"): item for item in materials.get("texts", []) if item.get("id")}
    text_templates = {
        item.get("id"): item for item in materials.get("text_templates", []) if item.get("id")
    }
    tracks = []
    for track_index, track in enumerate(data.get("tracks", [])):
        if track.get("type") != "text":
            continue
        rows = []
        for segment_index, segment in enumerate(track.get("segments", [])):
            text, source = collect_segment_text(segment, texts, text_templates)
            if not text:
                continue
            target = segment.get("target_timerange") or {}
            rows.append(
                {
                    "track_index": track_index,
                    "segment_index": segment_index,
                    "start_us": int(target.get("start") or 0),
                    "duration_us": int(target.get("duration") or 0),
                    "start": fmt_time(target.get("start") or 0),
                    "duration": fmt_time(target.get("duration") or 0),
                    "source": source,
                    "text": text,
                }
            )
        rows.sort(key=lambda row: (row["start_us"], row["segment_index"]))
        tracks.append(
            {
                "track_index": track_index,
                "track_id": track.get("id"),
                "segment_count": len(track.get("segments", [])),
                "text_row_count": len(rows),
                "total_chars": sum(len(row["text"]) for row in rows),
                "rows": rows,
            }
        )
    return tracks


QUESTION_ENDINGS = ("吗", "呢", "么", "怎么办", "为什么", "是什么", "怎么做", "怎么选", "哪一个", "哪里", "多少", "有没有")
STRONG_ENDINGS = ("了", "吧", "啦", "哦", "噢", "即可", "就行", "的人", "的问题", "的机会", "机会", "的技巧", "的工具", "的玩法")
COMMA_STARTERS = ("然后", "接着", "同时", "另外", "而且", "并且", "但是", "不过", "所以", "因为", "如果", "那么", "这里", "这个", "这些", "也就是", "首先", "最后", "细心", "点击")
LINK_ENDINGS = ("的", "和", "与", "及", "以及", "跟", "在", "到", "从", "把", "被", "对", "给", "用", "为", "叫", "是", "能", "会", "可以", "需要", "拥有", "提高", "增加", "选择", "来到", "找到", "打开", "获取", "获得", "提供", "属于", "通过", "利用", "消耗")
LIST_MARKERS = ("第一", "第二", "第三", "第四", "第五", "第一个", "第二个", "第三个", "第四个", "第五个")


def clean_piece(text):
    text = str(text or "").strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n+", "，", text)
    text = re.sub(r"\s+", "", text)
    return text.strip()


def has_punctuation(text):
    return any(char in PUNCTUATION for char in text)


def ends_with_punctuation(text):
    return bool(text) and text[-1] in PUNCTUATION


def normalize_punctuation(text):
    text = text.replace(",", "，").replace("?", "？").replace("!", "！").replace(";", "；")
    text = re.sub(r"([，。！？；：、])\1+", r"\1", text)
    text = re.sub(r"，([。！？；])", r"\1", text)
    text = re.sub(r"\s+", "", text)
    return text


def choose_punctuation(piece, next_piece, current_sentence_len):
    if not next_piece:
        return "" if ends_with_punctuation(piece) else "。"
    if ends_with_punctuation(piece):
        return ""
    if piece.endswith(QUESTION_ENDINGS):
        return "？"
    if piece in LIST_MARKERS:
        return "，"
    if piece.endswith(LINK_ENDINGS) and current_sentence_len <= 48:
        return ""
    if len(piece) <= 8 and next_piece.startswith(("是", "分别", "包括", "选择", "可以", "能", "会")):
        return "，"
    if next_piece.startswith(COMMA_STARTERS):
        return "。" if current_sentence_len >= 28 or piece.endswith(STRONG_ENDINGS) else "，"
    if piece.endswith(STRONG_ENDINGS) and current_sentence_len >= 22:
        return "。"
    if current_sentence_len >= 42:
        return "。"
    return "，"


def fix_boundaries(text):
    replacements = {
        "机会细心": "机会。细心",
        "功能点击": "功能，点击",
        "开荒首先": "开荒。首先",
        "特点第一个": "特点。第一个",
        "特点第二个": "特点。第二个",
        "特点第三个": "特点。第三个",
        "记录功能点击": "记录功能，点击",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def restore_script(rows):
    pieces = [clean_piece(row.get("text", "")) for row in rows]
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        return ""
    punctuated_ratio = sum(1 for piece in pieces if has_punctuation(piece)) / max(len(pieces), 1)
    output = []
    current_sentence_len = 0
    paragraph_chars = 0
    for index, piece in enumerate(pieces):
        next_piece = pieces[index + 1] if index + 1 < len(pieces) else ""
        piece = normalize_punctuation(piece)
        current_sentence_len += len(piece)
        punct = choose_punctuation(piece, next_piece, current_sentence_len)
        if punctuated_ratio >= 0.35 and ends_with_punctuation(piece):
            punct = ""
        output.append(piece + punct)
        if punct in FINAL_PUNCTUATION or piece.endswith(FINAL_PUNCTUATION):
            current_sentence_len = 0
        paragraph_chars += len(piece)
        if output[-1][-1:] in FINAL_PUNCTUATION and paragraph_chars >= 140 and next_piece:
            output.append("\n\n")
            paragraph_chars = 0
    script = fix_boundaries(normalize_punctuation("".join(output)))
    if script and script[-1] not in FINAL_PUNCTUATION:
        script += "。"
    return re.sub(r"\n{3,}", "\n\n", script)


def recent_drafts(root_meta, limit):
    meta = json.loads(pathlib.Path(root_meta).read_text(encoding="utf-8"))
    items = []
    for item in meta.get("all_draft_store", []):
        draft_json = item.get("draft_json_file")
        if item.get("tm_draft_removed") or not draft_json:
            continue
        if not pathlib.Path(draft_json).exists():
            continue
        items.append(item)
    items.sort(key=lambda item: item.get("tm_draft_modified") or 0, reverse=True)
    return items[:limit]


def top_terms(scripts, limit=30):
    text = "\n".join(scripts)
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,8}", text)
    stop = {"这个", "一个", "就是", "我们", "可以", "然后", "直接", "这里", "视频", "大家", "如果", "因为", "以及", "时候", "首先", "最后", "进行", "获得", "获取"}
    counts = {}
    for token in tokens:
        if token in stop:
            continue
        counts[token] = counts.get(token, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def analyze_style(drafts):
    scripts = [draft["script"] for draft in drafts if draft["script"]]
    if not scripts:
        return "未解析到足够文案，暂不能做风格分析。"
    all_text = "\n".join(scripts)
    sentence_count = len(re.findall(r"[。！？]", all_text)) or 1
    char_count = len(all_text)
    question_count = all_text.count("？")
    list_count = sum(all_text.count(marker) for marker in LIST_MARKERS)
    avg_sentence = round(char_count / sentence_count, 1)
    starts = [script[:60].replace("\n", "") for script in scripts[:8]]
    terms = top_terms(scripts, 20)
    lines = [
        "# 文案风格分析",
        "",
        f"- 样本篇数：{len(scripts)}",
        f"- 总字数：{char_count}",
        f"- 平均句长：约 {avg_sentence} 字/句",
        f"- 问句数量：{question_count}",
        f"- 序号/步骤提示出现次数：{list_count}",
        "",
        "## 常见开头",
        "",
    ]
    for start in starts:
        lines.append(f"- {start}")
    lines.extend(
        [
            "",
            "## 高频表达",
            "",
            "、".join(f"{term}({count})" for term, count in terms) or "无",
            "",
            "## 风格判断",
            "",
            "- 偏短视频口播体，常用问题、提醒、攻略、步骤、收益点做开场。",
            "- 喜欢把复杂流程拆成可执行步骤，常见结构是痛点开头 -> 工具/路线/机制解释 -> 具体操作 -> 收益总结。",
            "- 语气直接，偏实用攻略和游戏资讯，频繁使用“直接”“首先”“这个视频”“小伙伴”等口播连接词。",
            "- 句子通常较短，适合切成字幕；信息密度较高，名词、地点、道具和数值会连续出现。",
            "",
            "## 仿写建议",
            "",
            "- 开头先抛痛点或强提醒，不要铺垫太久。",
            "- 每段只讲一个操作或一个判断标准。",
            "- 多用“首先/然后/接着/最后”串联步骤。",
            "- 保留具体地点、道具、数值和收益，让文案看起来像可执行攻略。",
        ]
    )
    return "\n".join(lines)


def write_outputs(output_dir, payload):
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"jianying_draft_texts_{stamp}"
    json_path = output_dir / f"{base}_data.json"
    md_path = output_dir / f"{base}_full_scripts.md"
    txt_path = output_dir / f"{base}_full_scripts.txt"
    csv_path = output_dir / f"{base}_scripts.csv"
    style_path = output_dir / f"{base}_style_analysis.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# 剪映草稿完整文案",
        "",
        f"- 生成时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 提取规则：{payload['rule']}",
        f"- 成功草稿：{len(payload['drafts'])}",
        f"- 失败草稿：{len(payload['failures'])}",
        "",
    ]
    txt = []
    for draft in payload["drafts"]:
        header = f"{draft['rank']:02d}. {draft['draft_name']}"
        md.extend(
            [
                f"## {header}",
                "",
                f"- 修改时间：{draft['modified']}",
                f"- 选中轨道：`{draft['selected_track_index']}`",
                f"- 字幕条数：{draft['subtitle_row_count']}",
                "",
                draft["script"] or "（未解析到可还原的字幕文案）",
                "",
            ]
        )
        txt.extend([f"===== {header} =====", draft["script"] or "（未解析到可还原的字幕文案）", ""])
    md_path.write_text("\n".join(md), encoding="utf-8")
    txt_path.write_text("\n".join(txt), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "draft_name", "modified", "selected_track_index", "subtitle_row_count", "script_char_count", "script"])
        for draft in payload["drafts"]:
            writer.writerow([draft["rank"], draft["draft_name"], draft["modified"], draft["selected_track_index"], draft["subtitle_row_count"], draft["script_char_count"], draft["script"]])

    style_path.write_text(analyze_style(payload["drafts"]), encoding="utf-8")
    return {
        "json": str(json_path),
        "md": str(md_path),
        "txt": str(txt_path),
        "csv": str(csv_path),
        "style": str(style_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Extract restored scripts from Jianying draft history.")
    parser.add_argument("--limit", type=int, default=20, help="Number of latest drafts to extract. Default: 20.")
    parser.add_argument("--root-meta", default=str(default_root_meta()), help="Path to root_meta_info.json.")
    parser.add_argument("--jy-install", default=None, help="Jianying install version folder containing videoeditor.dll.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for generated files.")
    args = parser.parse_args()

    root_meta = pathlib.Path(args.root_meta)
    if not root_meta.exists():
        raise FileNotFoundError(f"root_meta_info.json not found: {root_meta}")
    install_dir = find_jy_install(args.jy_install)

    drafts = []
    failures = []
    for rank, item in enumerate(recent_drafts(root_meta, args.limit), 1):
        try:
            data = load_draft_json(item["draft_json_file"], install_dir)
            tracks = extract_text_tracks(data)
            selected = max(tracks, key=lambda track: (track["text_row_count"], track["total_chars"]), default=None)
            rows = selected["rows"] if selected else []
            script = restore_script(rows)
            draft = {
                "rank": rank,
                "draft_id": item.get("draft_id"),
                "draft_name": item.get("draft_name"),
                "modified": fmt_modified(item.get("tm_draft_modified") or 0),
                "duration_seconds": round((item.get("tm_duration") or data.get("duration") or 0) / 1_000_000, 3),
                "draft_json_file": item.get("draft_json_file"),
                "selected_track_index": selected["track_index"] if selected else None,
                "subtitle_row_count": len(rows),
                "script_char_count": len(script),
                "script": script,
                "track_summary": [
                    {
                        "track_index": track["track_index"],
                        "segment_count": track["segment_count"],
                        "text_row_count": track["text_row_count"],
                        "total_chars": track["total_chars"],
                    }
                    for track in tracks
                ],
            }
            drafts.append(draft)
            print(f"{rank:02d} ok {draft['draft_name']} rows={draft['subtitle_row_count']}")
        except Exception as exc:
            failures.append({"rank": rank, "draft_name": item.get("draft_name"), "draft_json_file": item.get("draft_json_file"), "error": repr(exc)})
            print(f"{rank:02d} failed {item.get('draft_name')}: {exc}", file=sys.stderr)

    payload = {
        "source_root_meta": str(root_meta),
        "jianying_install": str(install_dir) if install_dir else "",
        "limit": args.limit,
        "rule": "choose the readable text track with the largest text row count, restore punctuation without rewriting",
        "drafts": drafts,
        "failures": failures,
        "total_script_chars": sum(draft["script_char_count"] for draft in drafts),
        "empty_script_drafts": [draft["draft_name"] for draft in drafts if not draft["script"]],
    }
    paths = write_outputs(pathlib.Path(args.output_dir), payload)
    print(json.dumps({"paths": paths, "drafts": len(drafts), "failures": len(failures), "empty_script_drafts": payload["empty_script_drafts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
