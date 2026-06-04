import unittest

from skill_paths import looks_like_bgm_audio, looks_like_voiceover_audio, sanitize_profile


class AudioClassificationTests(unittest.TestCase):
    def test_voiceover_name_is_not_bgm(self):
        mat = {"path": r"F:\demo\工具配音1.mp3", "name": "工具配音1.mp3", "music_id": "x", "type": "music"}
        self.assertTrue(looks_like_voiceover_audio(mat))
        self.assertFalse(looks_like_bgm_audio(mat))

    def test_background_music_name_is_bgm(self):
        mat = {"path": r"C:\cache\happy_bgm.mp3", "name": "轻快背景音乐", "music_id": "abc"}
        self.assertFalse(looks_like_voiceover_audio(mat))
        self.assertTrue(looks_like_bgm_audio(mat))

    def test_sanitize_drops_voiceover_bgm(self):
        profile = {
            "audio": {
                "bgm": {"path": r"F:\demo\工具配音1.mp3", "name": "工具配音1.mp3"},
                "sound_effects": [],
            }
        }
        cleaned = sanitize_profile(profile)
        self.assertEqual(cleaned.get("audio", {}).get("bgm"), {})


if __name__ == "__main__":
    unittest.main()
