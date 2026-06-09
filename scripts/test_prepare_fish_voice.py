import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prepare_fish_voice


class PrepareFishVoiceTests(unittest.TestCase):
    def test_split_paragraphs_preserves_long_form_generation_units(self):
        text = "第一段要完整生成，不按字幕短句拆。\n\n第二段也保持连续语气。里面可以有逗号，也可以有短句。"

        paragraphs = prepare_fish_voice.split_paragraphs(text)

        self.assertEqual(paragraphs, ["第一段要完整生成，不按字幕短句拆。", "第二段也保持连续语气。里面可以有逗号，也可以有短句。"])

    def test_build_voice_groups_maps_subtitles_inside_paragraph_duration(self):
        paragraphs = ["第一段很短。", "第二段要拆成字幕，但是语音是一整段。"]
        paragraph_durations = [2.0, 6.0]

        groups = prepare_fish_voice.build_voice_groups(paragraphs, paragraph_durations, max_subtitle_chars=8)

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["chunks"], ["第一段很短。"])
        self.assertGreater(len(groups[1]["chunks"]), 1)
        self.assertAlmostEqual(groups[0]["duration"], 2.0)
        self.assertAlmostEqual(groups[1]["duration"], 6.0)

    def test_write_profile_does_not_persist_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            profile_path = output_dir / "fish_voice_profile.json"

            prepare_fish_voice.write_fish_profile(
                profile_path,
                {
                    "provider": "fish_audio",
                    "model": "s2-pro",
                    "api_key": "secret-value",
                    "voice_sample": "C:/voice.wav",
                },
            )

            text = profile_path.read_text(encoding="utf-8")
            data = json.loads(text)
            self.assertNotIn("secret-value", text)
            self.assertNotIn("api_key", data)
            self.assertEqual(data["provider"], "fish_audio")


if __name__ == "__main__":
    unittest.main()
