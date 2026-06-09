import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prepare_historical_style


class PrepareHistoricalStyleTests(unittest.TestCase):
    def test_output_paths_keep_history_reference_outside_skill_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = prepare_historical_style.output_paths(Path(tmp))

            self.assertEqual(paths.history_dir, Path(tmp) / "history_scripts")
            self.assertEqual(paths.profile_path, Path(tmp) / "history_scripts" / "writing_style_profile.json")
            self.assertEqual(paths.brief_path, Path(tmp) / "history_scripts" / "narration_brief.md")

    def test_build_writing_style_profile_records_default_imitation_policy(self):
        payload = {
            "source_root_meta": "C:/drafts/root_meta_info.json",
            "jianying_install": "C:/JianyingPro/6.0.0",
            "limit": 2,
            "total_script_chars": 42,
            "empty_script_drafts": ["Empty Draft"],
            "failures": [],
            "drafts": [
                {"draft_name": "Guide One", "script_char_count": 30, "script": "先看这个机制。然后直接操作。"},
                {"draft_name": "Empty Draft", "script_char_count": 0, "script": ""},
            ],
        }
        profile = prepare_historical_style.build_writing_style_profile(
            payload=payload,
            style_analysis="## 风格判断\n- 直接、实用、短句。",
            topic="新游戏生态讲解",
            media_files=[Path("opening_scene.mp4"), Path("system_demo.mp4")],
            extractor_outputs={"data": "data.json", "style": "style.md"},
        )

        self.assertTrue(profile["imitation_policy"]["enabled_by_default"])
        self.assertEqual(profile["imitation_policy"]["content_source"], "topic_and_current_media_filenames")
        self.assertIn("禁止复制历史草稿原句", profile["imitation_policy"]["anti_copy_rules"])
        self.assertEqual(profile["sample"]["draft_count_with_script"], 1)
        self.assertEqual(profile["current_project"]["media_files"], ["opening_scene.mp4", "system_demo.mp4"])

    def test_write_narration_brief_requires_user_confirmation_before_remix(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = {
                "current_project": {
                    "topic": "新游戏生态讲解",
                    "media_files": ["opening_scene.mp4", "system_demo.mp4"],
                },
                "style_analysis": "## 仿写建议\n- 开头先抛痛点。",
                "imitation_policy": {
                    "anti_copy_rules": ["禁止复制历史草稿原句", "禁止复用旧草稿桥段"],
                },
            }
            path = Path(tmp) / "narration_brief.md"

            prepare_historical_style.write_narration_brief(profile, path)

            text = path.read_text(encoding="utf-8")
            self.assertIn("默认参考历史草稿文案风格", text)
            self.assertIn("生成的新文案必须先给用户确认", text)
            self.assertIn("opening_scene.mp4", text)
            self.assertIn("禁止复制历史草稿原句", text)


if __name__ == "__main__":
    unittest.main()
