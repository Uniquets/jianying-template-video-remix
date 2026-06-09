import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import remix_draft


class RemixExternalVoiceTests(unittest.TestCase):
    def test_load_external_voice_groups_reads_duration_and_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            voice = root / "narration_full.wav"
            voice.write_bytes(b"fake")
            groups_path = root / "voice_groups.json"
            groups_path.write_text(
                json.dumps(
                    {
                        "duration": 9.0,
                        "groups": [
                            {"start_index": 0, "chunks": ["第一句", "第二句"], "duration": 4.0},
                            {"start_index": 2, "chunks": ["第三句"], "duration": 5.0},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            duration, groups = remix_draft.load_external_voice(voice, groups_path)

            self.assertEqual(duration, 9.0)
            self.assertEqual(groups[0]["chunks"], ["第一句", "第二句"])
            self.assertEqual(groups[1]["duration"], 5.0)

    def test_external_voice_groups_must_match_confirmed_script_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            voice = root / "narration_full.wav"
            voice.write_bytes(b"fake")
            groups_path = root / "voice_groups.json"
            groups_path.write_text(
                json.dumps({"duration": 3.0, "groups": [{"start_index": 0, "chunks": ["旧文案"], "duration": 3.0}]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "external voice groups do not match confirmed script"):
                remix_draft.voice_for_script(["新文案"], voice, groups_path, "ignored", root / "unused.wav")


if __name__ == "__main__":
    unittest.main()
