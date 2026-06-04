import json
import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PROJECT_TERMS = [
    "伊莫",
    "Aniimo",
    "拿走伊莫",
    "抱走伊莫",
    "BOSS传送BUG",
    "脱离卡死",
    "捕捉睡着伊莫",
    "锐眼测试",
    "PySpace",
    "FishAudio",
]
FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"Users/11709", re.I),
    re.compile(r"Users\\11709", re.I),
    re.compile(r"F:/PySpace", re.I),
]
PRODUCTION_FILES = [
    SKILL_ROOT / "SKILL.md",
    SKILL_ROOT / "scripts" / "remix_draft.py",
    SKILL_ROOT / "scripts" / "analyze_template_style.py",
    SKILL_ROOT / "defaults" / "default_fallbacks.json",
]
TEST_FILES = [
    SKILL_ROOT / "scripts" / "test_remix_media_plan.py",
    SKILL_ROOT / "scripts" / "test_remix_title_events.py",
]


class SkillDecouplingTests(unittest.TestCase):
    def test_production_files_do_not_embed_project_specific_terms(self):
        hits = []
        for path in PRODUCTION_FILES:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_PROJECT_TERMS:
                if term in text:
                    hits.append(f"{path.name}:{term}")
        self.assertEqual(hits, [])

    def test_defaults_json_has_no_machine_absolute_paths(self):
        text = (SKILL_ROOT / "defaults" / "default_fallbacks.json").read_text(encoding="utf-8")
        data = json.loads(text)
        blob = json.dumps(data, ensure_ascii=False)
        for pattern in FORBIDDEN_PATH_PATTERNS:
            self.assertIsNone(pattern.search(blob), f"found forbidden path pattern in default_fallbacks.json: {pattern.pattern}")
        for key in ("font_path", "path"):
            self._assert_no_windows_abs(data, key)

    def _assert_no_windows_abs(self, node, key: str) -> None:
        if isinstance(node, dict):
            for k, value in node.items():
                if k == key and isinstance(value, str) and re.match(r"^[A-Za-z]:[\\/]", value):
                    self.fail(f"absolute path in defaults: {value}")
                self._assert_no_windows_abs(value, key)
        elif isinstance(node, list):
            for item in node:
                self._assert_no_windows_abs(item, key)

    def test_tests_use_neutral_fixture_terms(self):
        hits = []
        for path in TEST_FILES:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_PROJECT_TERMS:
                if term in text:
                    hits.append(f"{path.name}:{term}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
