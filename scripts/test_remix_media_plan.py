import unittest
from pathlib import Path

import remix_draft


class MediaPlanTests(unittest.TestCase):
    def test_clip_plan_uses_named_media_that_matches_narration(self):
        files = [
            Path("intro_scene.mp4"),
            Path("carry_subject.mp4"),
            Path("food_reaction.mp4"),
            Path("food_reaction_angry.mp4"),
            Path("sleep_capture_escape.mp4"),
            Path("tutorial_rules.mp4"),
            Path("debug_teleport.mp4"),
            Path("unstuck_recovery.mp4"),
        ]
        rows = [
            {"text": "第一次打开产品，先别急着下结论。", "start": 0.0, "end": 4.0},
            {"text": "入门区会先教你看懂界面。", "start": 4.0, "end": 8.0},
            {"text": "教程会把规则拆成轻量步骤。", "start": 8.0, "end": 12.0},
            {"text": "如果趁它休息操作，可能直接触发逃离。", "start": 12.0, "end": 16.0},
            {"text": "也可能因为拿走资源而生气。", "start": 16.0, "end": 20.0},
            {"text": "你可以带走它，也可能被反馈打断节奏。", "start": 20.0, "end": 24.0},
            {"text": "慢慢形成自己的操作策略。", "start": 24.0, "end": 28.0},
        ]
        observations = {str(path): {"duration": 30.0} for path in files}

        plan = remix_draft.build_clip_plan(files, rows, 28.0, observations=observations, target_clip_s=4.0)
        names = [item["path"].name for item in plan]

        self.assertEqual(names[0], "intro_scene.mp4")
        self.assertIn("tutorial_rules.mp4", names)
        self.assertIn("sleep_capture_escape.mp4", names)
        self.assertIn("food_reaction_angry.mp4", names)
        self.assertIn("carry_subject.mp4", names)

    def test_non_opening_clips_use_nonzero_source_start_when_duration_allows(self):
        files = [Path("sleep_capture_escape.mp4")]
        rows = [{"text": "如果趁它休息操作，可能直接触发逃离。", "start": 0.0, "end": 5.0}]
        observations = {str(files[0]): {"duration": 30.0}}

        plan = remix_draft.build_clip_plan(files, rows, 5.0, observations=observations, target_clip_s=5.0)

        self.assertGreater(plan[0]["source_start"], 0.0)

    def test_generic_capture_word_does_not_steal_opening_clip(self):
        files = [Path("intro_scene.mp4"), Path("sleep_capture_escape.mp4")]
        rows = [
            {"text": "第一次打开产品，先别急着下结论。", "start": 0.0, "end": 2.0},
            {"text": "你靠近、观察、尝试，每一步都会触发不同反应。", "start": 2.0, "end": 5.0},
        ]
        observations = {str(path): {"duration": 30.0} for path in files}

        plan = remix_draft.build_clip_plan(files, rows, 40.0, observations=observations, target_clip_s=5.0)

        self.assertEqual(plan[0]["path"].name, "intro_scene.mp4")

    def test_default_media_analysis_does_not_extract_frames(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            files = [Path("intro_scene.mp4")]
            observations = remix_draft.analyze_media_assets(files, out_dir, extract_frames=False)

            self.assertEqual(observations[str(files[0])]["sample_frames"], [])
            self.assertFalse(any(out_dir.glob("*.jpg")))

    def test_unrecognized_media_names_are_reported_before_frame_analysis(self):
        files = [Path("random001.mp4"), Path("intro_scene.mp4")]

        unknown = remix_draft.unrecognized_media_files(files)

        self.assertEqual(unknown, [Path("random001.mp4")])

    def test_debug_clips_are_not_generic_system_fallbacks(self):
        files = [Path("intro_scene.mp4"), Path("tutorial_rules.mp4"), Path("debug_teleport.mp4"), Path("unstuck_recovery.mp4")]
        rows = [
            {"text": "如果后续加入更多模块和关系，", "start": 0.0, "end": 3.0},
            {"text": "会变成真正可探索的系统。", "start": 3.0, "end": 6.0},
        ]
        observations = {str(path): {"duration": 30.0} for path in files}

        plan = remix_draft.build_clip_plan(files, rows, 40.0, observations=observations, target_clip_s=5.0)
        names = {item["path"].name for item in plan[:2]}

        self.assertNotIn("debug_teleport.mp4", names)
        self.assertNotIn("unstuck_recovery.mp4", names)


if __name__ == "__main__":
    unittest.main()
