"""
Unit & integration tests for upscale.py, batch_upscale.py, and launcher.py.
Run: python -m pytest test_upscale.py -v
     python -m unittest test_upscale.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Ensure project root is importable ────────────────────────────────────────
REPO = Path(__file__).parent
sys.path.insert(0, str(REPO))

import upscale
import batch_upscale


# ─────────────────────────────────────────────────────────────────────────────
# upscale._parse_time
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTime(unittest.TestCase):

    def test_zero(self):
        self.assertAlmostEqual(upscale._parse_time("0", "0", "0"), 0.0)

    def test_seconds_only(self):
        self.assertAlmostEqual(upscale._parse_time("0", "0", "30.5"), 30.5)

    def test_minutes_and_seconds(self):
        self.assertAlmostEqual(upscale._parse_time("0", "2", "15.0"), 135.0)

    def test_hours_minutes_seconds(self):
        self.assertAlmostEqual(upscale._parse_time("1", "30", "0"), 5400.0)

    def test_fractional_seconds(self):
        self.assertAlmostEqual(upscale._parse_time("0", "0", "1.5"), 1.5)


# ─────────────────────────────────────────────────────────────────────────────
# upscale.resolve_target
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveTarget(unittest.TestCase):

    def _call(self, w, h, target):
        return upscale.resolve_target(w, h, target)

    # preset names
    def test_480p(self):
        tw, th, scale = self._call(640, 360, "480p")
        self.assertEqual((tw, th), (854, 480))

    def test_720p(self):
        tw, th, scale = self._call(640, 360, "720p")
        self.assertEqual((tw, th), (1280, 720))

    def test_1080p(self):
        tw, th, scale = self._call(640, 360, "1080p")
        self.assertEqual((tw, th), (1920, 1080))

    def test_1440p(self):
        tw, th, scale = self._call(1280, 720, "1440p")
        self.assertEqual((tw, th), (2560, 1440))

    def test_4k(self):
        tw, th, scale = self._call(1280, 720, "4k")
        self.assertEqual((tw, th), (3840, 2160))

    def test_case_insensitive(self):
        tw, th, _ = self._call(640, 360, "1080P")
        self.assertEqual((tw, th), (1920, 1080))

    # WxH literal
    def test_wxh_format(self):
        tw, th, _ = self._call(640, 360, "1920x1080")
        self.assertEqual((tw, th), (1920, 1080))

    def test_wxh_lowercase_x(self):
        tw, th, _ = self._call(320, 240, "640x480")
        self.assertEqual((tw, th), (640, 480))

    # scale factor
    def test_scale_correct_for_1080p_from_360p(self):
        _, _, scale = self._call(640, 360, "1080p")
        self.assertAlmostEqual(scale, 3.0, places=1)

    def test_scale_uses_max_axis(self):
        # portrait: height is limiting dimension
        _, _, scale = self._call(360, 640, "1080p")
        self.assertGreater(scale, 1.5)

    # invalid input
    def test_invalid_preset_raises(self):
        with self.assertRaises(ValueError):
            self._call(640, 360, "8k")

    def test_invalid_format_raises(self):
        with self.assertRaises((ValueError, Exception)):
            self._call(640, 360, "badformat")


# ─────────────────────────────────────────────────────────────────────────────
# upscale._cleanup
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanup(unittest.TestCase):

    def test_deletes_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        self.assertTrue(Path(path).exists())
        upscale._cleanup(path)
        self.assertFalse(Path(path).exists())

    def test_nonexistent_file_no_error(self):
        upscale._cleanup("/nonexistent/path/file.mp4")

    def test_empty_path_no_error(self):
        upscale._cleanup("")


# ─────────────────────────────────────────────────────────────────────────────
# upscale.find_ffmpeg
# ─────────────────────────────────────────────────────────────────────────────

class TestFindFfmpeg(unittest.TestCase):

    def test_returns_string_or_none(self):
        result = upscale.find_ffmpeg()
        self.assertIsInstance(result, (str, type(None)))

    def test_found_path_is_executable(self):
        result = upscale.find_ffmpeg()
        if result is not None:
            self.assertTrue(Path(result).exists(), f"ffmpeg path does not exist: {result}")

    def test_returns_ffmpeg_when_on_path(self):
        import shutil
        shutil_found = shutil.which("ffmpeg")
        result = upscale.find_ffmpeg()
        if shutil_found:
            self.assertIsNotNone(result)


# ─────────────────────────────────────────────────────────────────────────────
# upscale._check_nvenc  (new)
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckNvenc(unittest.TestCase):

    @patch("upscale.subprocess.run")
    def test_returns_true_when_nvenc_present(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=" V..... h264_nvenc           NVIDIA NVENC H.264 encoder")
        self.assertTrue(upscale._check_nvenc("ffmpeg"))

    @patch("upscale.subprocess.run")
    def test_returns_false_when_nvenc_absent(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=" V..... libx264              libx264 H.264 / AVC / MPEG-4 AVC")
        self.assertFalse(upscale._check_nvenc("ffmpeg"))

    @patch("upscale.subprocess.run")
    def test_returns_false_on_subprocess_exception(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ffmpeg not found")
        self.assertFalse(upscale._check_nvenc("nonexistent_ffmpeg"))

    @patch("upscale.subprocess.run")
    def test_returns_false_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10)
        self.assertFalse(upscale._check_nvenc("ffmpeg"))


# ─────────────────────────────────────────────────────────────────────────────
# upscale._encoder_args  (new)
# ─────────────────────────────────────────────────────────────────────────────

class TestEncoderArgs(unittest.TestCase):

    def test_nvenc_contains_h264_nvenc(self):
        args = upscale._encoder_args(True)
        self.assertIn("h264_nvenc", args)

    def test_nvenc_does_not_contain_libx264(self):
        args = upscale._encoder_args(True)
        self.assertNotIn("libx264", args)

    def test_cpu_contains_libx264(self):
        args = upscale._encoder_args(False)
        self.assertIn("libx264", args)

    def test_cpu_does_not_contain_h264_nvenc(self):
        args = upscale._encoder_args(False)
        self.assertNotIn("h264_nvenc", args)

    def test_returns_list(self):
        self.assertIsInstance(upscale._encoder_args(True),  list)
        self.assertIsInstance(upscale._encoder_args(False), list)

    def test_nvenc_codec_flag_position(self):
        # -c:v must immediately precede the codec name
        args = upscale._encoder_args(True)
        idx = args.index("-c:v")
        self.assertEqual(args[idx + 1], "h264_nvenc")

    def test_cpu_codec_flag_position(self):
        args = upscale._encoder_args(False)
        idx = args.index("-c:v")
        self.assertEqual(args[idx + 1], "libx264")


# ─────────────────────────────────────────────────────────────────────────────
# upscale._auto_tile_size  (new)
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoTileSize(unittest.TestCase):

    def test_cpu_always_returns_256(self):
        self.assertEqual(upscale._auto_tile_size(False), 256)

    def test_gpu_returns_valid_int(self):
        result = upscale._auto_tile_size(True)
        self.assertIsInstance(result, int)
        self.assertIn(result, [0, 256, 512, 768])

    def _patched(self, vram_bytes):
        """Call _auto_tile_size(True) with a mocked torch reporting vram_bytes."""
        mock_torch = MagicMock()
        mock_torch.cuda.get_device_properties.return_value.total_memory = vram_bytes
        with patch.dict(sys.modules, {"torch": mock_torch}):
            return upscale._auto_tile_size(True)

    def test_vram_above_10gb_returns_0(self):
        self.assertEqual(self._patched(11 * 1024 ** 3), 0)

    def test_vram_exactly_10gb_returns_0(self):
        self.assertEqual(self._patched(10 * 1024 ** 3), 0)

    def test_vram_8gb_returns_768(self):
        self.assertEqual(self._patched(8 * 1024 ** 3), 768)

    def test_vram_6gb_returns_512(self):
        self.assertEqual(self._patched(6 * 1024 ** 3), 512)

    def test_vram_4gb_returns_256(self):
        self.assertEqual(self._patched(4 * 1024 ** 3), 256)

    def test_exception_falls_back_to_512(self):
        mock_torch = MagicMock()
        mock_torch.cuda.get_device_properties.side_effect = RuntimeError("no GPU")
        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = upscale._auto_tile_size(True)
        self.assertEqual(result, 512)


# ─────────────────────────────────────────────────────────────────────────────
# upscale._upscale_frames_threaded  (new — skip without opencv)
# ─────────────────────────────────────────────────────────────────────────────

_HAS_CV2 = True
try:
    import cv2 as _cv2
    import numpy as _np
except ImportError:
    _HAS_CV2 = False


@unittest.skipUnless(_HAS_CV2, "opencv-python not installed — skipping threaded tests")
class TestUpscaleFramesThreaded(unittest.TestCase):

    def _write_dummy_frames(self, dir_path: Path, count: int = 4):
        """Write tiny 8×8 black PNG files; returns sorted list of Paths."""
        frames = []
        for i in range(count):
            p = dir_path / f"{i + 1:08d}.png"
            _cv2.imwrite(str(p), _np.zeros((8, 8, 3), dtype=_np.uint8))
            frames.append(p)
        return frames

    def _passthrough_upsampler(self):
        m = MagicMock()
        m.enhance.side_effect = lambda img, outscale: (img, None)
        return m

    def test_returns_correct_processed_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
            in_dir.mkdir(); out_dir.mkdir()
            frames = self._write_dummy_frames(in_dir, 4)
            result = upscale._upscale_frames_threaded(
                self._passthrough_upsampler(), frames, out_dir,
                scale=1, total_frames=10, processed_offset=0, t0_ai=time.time(),
            )
            self.assertEqual(result, 4)

    def test_offset_is_added_to_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
            in_dir.mkdir(); out_dir.mkdir()
            frames = self._write_dummy_frames(in_dir, 3)
            result = upscale._upscale_frames_threaded(
                self._passthrough_upsampler(), frames, out_dir,
                scale=1, total_frames=10, processed_offset=5, t0_ai=time.time(),
            )
            self.assertEqual(result, 8)  # 5 offset + 3 frames

    def test_output_files_created_for_every_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
            in_dir.mkdir(); out_dir.mkdir()
            frames = self._write_dummy_frames(in_dir, 5)
            upscale._upscale_frames_threaded(
                self._passthrough_upsampler(), frames, out_dir,
                scale=1, total_frames=5, processed_offset=0, t0_ai=time.time(),
            )
            out_files = sorted(out_dir.glob("*.png"))
            self.assertEqual(len(out_files), 5)

    def test_output_filenames_match_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
            in_dir.mkdir(); out_dir.mkdir()
            frames = self._write_dummy_frames(in_dir, 3)
            upscale._upscale_frames_threaded(
                self._passthrough_upsampler(), frames, out_dir,
                scale=1, total_frames=3, processed_offset=0, t0_ai=time.time(),
            )
            in_names  = {f.name for f in frames}
            out_names = {f.name for f in out_dir.glob("*.png")}
            self.assertEqual(in_names, out_names)

    def test_empty_frame_list_returns_offset_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            result = upscale._upscale_frames_threaded(
                self._passthrough_upsampler(), [], out_dir,
                scale=1, total_frames=0, processed_offset=7, t0_ai=time.time(),
            )
            self.assertEqual(result, 7)

    def test_enhance_called_once_per_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
            in_dir.mkdir(); out_dir.mkdir()
            frames = self._write_dummy_frames(in_dir, 4)
            upsampler = self._passthrough_upsampler()
            upscale._upscale_frames_threaded(
                upsampler, frames, out_dir,
                scale=1, total_frames=4, processed_offset=0, t0_ai=time.time(),
            )
            self.assertEqual(upsampler.enhance.call_count, 4)


# ─────────────────────────────────────────────────────────────────────────────
# batch_upscale.fmt_time
# ─────────────────────────────────────────────────────────────────────────────

class TestFmtTime(unittest.TestCase):

    def test_zero(self):
        self.assertEqual(batch_upscale.fmt_time(0), "00:00")

    def test_seconds_only(self):
        self.assertEqual(batch_upscale.fmt_time(45), "00:45")

    def test_one_minute(self):
        self.assertEqual(batch_upscale.fmt_time(60), "01:00")

    def test_minutes_and_seconds(self):
        self.assertEqual(batch_upscale.fmt_time(90), "01:30")

    def test_one_hour(self):
        self.assertEqual(batch_upscale.fmt_time(3600), "01:00:00")

    def test_hours_minutes_seconds(self):
        self.assertEqual(batch_upscale.fmt_time(3661), "01:01:01")

    def test_float_input_truncates(self):
        self.assertEqual(batch_upscale.fmt_time(90.9), "01:30")


# ─────────────────────────────────────────────────────────────────────────────
# launcher._fmt_eta  (new)
# ─────────────────────────────────────────────────────────────────────────────

from launcher import _fmt_eta as _launcher_fmt_eta


class TestFmtEta(unittest.TestCase):

    def test_zero(self):
        self.assertEqual(_launcher_fmt_eta(0), "00:00")

    def test_seconds_only(self):
        self.assertEqual(_launcher_fmt_eta(45), "00:45")

    def test_minutes_and_seconds(self):
        self.assertEqual(_launcher_fmt_eta(90), "01:30")

    def test_one_hour(self):
        self.assertEqual(_launcher_fmt_eta(3600), "01:00:00")

    def test_hours_minutes_seconds(self):
        self.assertEqual(_launcher_fmt_eta(3723), "01:02:03")

    def test_negative_clamps_to_zero(self):
        self.assertEqual(_launcher_fmt_eta(-99), "00:00")

    def test_float_truncates(self):
        self.assertEqual(_launcher_fmt_eta(59.9), "00:59")


# ─────────────────────────────────────────────────────────────────────────────
# launcher.LANGS — translation dict integrity  (new)
# ─────────────────────────────────────────────────────────────────────────────

from launcher import LANGS as _LANGS
import re as _re


class TestLangStructure(unittest.TestCase):

    def test_exactly_two_languages(self):
        self.assertEqual(set(_LANGS.keys()), {"zh", "en"})

    def test_both_languages_have_identical_keys(self):
        zh_keys = set(_LANGS["zh"].keys())
        en_keys = set(_LANGS["en"].keys())
        self.assertEqual(zh_keys, en_keys,
                         f"Missing in EN: {zh_keys - en_keys}  "
                         f"Missing in ZH: {en_keys - zh_keys}")

    def test_no_empty_translations(self):
        for lang, data in _LANGS.items():
            for key, val in data.items():
                self.assertNotEqual(
                    val.strip(), "",
                    f"Empty translation in '{lang}': key='{key}'",
                )

    def test_format_placeholders_match_between_languages(self):
        ph_re = _re.compile(r"\{(\w+)\}")
        for key in _LANGS["zh"]:
            zh_phs = set(ph_re.findall(_LANGS["zh"][key]))
            en_phs = set(ph_re.findall(_LANGS["en"][key]))
            self.assertEqual(
                zh_phs, en_phs,
                f"Placeholder mismatch for key '{key}': ZH={zh_phs} EN={en_phs}",
            )

    def test_lang_btn_values_differ(self):
        # Each lang's button shows the *other* language name
        self.assertNotEqual(_LANGS["zh"]["lang_btn"], _LANGS["en"]["lang_btn"])

    def test_all_values_are_strings(self):
        for lang, data in _LANGS.items():
            for key, val in data.items():
                self.assertIsInstance(
                    val, str,
                    f"Non-string value in '{lang}': key='{key}' type={type(val)}",
                )


# ─────────────────────────────────────────────────────────────────────────────
# upscale.get_video_info  (integration — requires ffprobe + test_clip.mp4)
# ─────────────────────────────────────────────────────────────────────────────

TEST_CLIP = REPO / "test_clip.mp4"


@unittest.skipUnless(TEST_CLIP.exists(), "test_clip.mp4 not found — skipping integration tests")
class TestGetVideoInfo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ffmpeg  = upscale.find_ffmpeg()
        cls.ffprobe = str(Path(cls.ffmpeg).parent / "ffprobe.exe") if cls.ffmpeg else None

    @unittest.skipIf(not upscale.find_ffmpeg(), "ffprobe not available")
    def test_returns_four_values(self):
        w, h, fps, dur = upscale.get_video_info(self.ffprobe, str(TEST_CLIP))
        self.assertIsNotNone(w)
        self.assertIsNotNone(h)
        self.assertIsNotNone(fps)
        self.assertIsNotNone(dur)

    @unittest.skipIf(not upscale.find_ffmpeg(), "ffprobe not available")
    def test_resolution_is_positive(self):
        w, h, fps, dur = upscale.get_video_info(self.ffprobe, str(TEST_CLIP))
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    @unittest.skipIf(not upscale.find_ffmpeg(), "ffprobe not available")
    def test_fps_is_reasonable(self):
        _, _, fps, _ = upscale.get_video_info(self.ffprobe, str(TEST_CLIP))
        self.assertGreater(fps, 0)
        self.assertLessEqual(fps, 120)

    @unittest.skipIf(not upscale.find_ffmpeg(), "ffprobe not available")
    def test_duration_matches_clip(self):
        _, _, _, dur = upscale.get_video_info(self.ffprobe, str(TEST_CLIP))
        self.assertAlmostEqual(dur, 5.0, delta=1.0)

    @unittest.skipIf(not upscale.find_ffmpeg(), "ffprobe not available")
    def test_known_source_resolution(self):
        w, h, _, _ = upscale.get_video_info(self.ffprobe, str(TEST_CLIP))
        self.assertEqual(w, 640)
        self.assertEqual(h, 360)


# ─────────────────────────────────────────────────────────────────────────────
# upscale.upscale_simple  (integration — runs actual FFmpeg)
# ─────────────────────────────────────────────────────────────────────────────

@unittest.skipUnless(TEST_CLIP.exists(), "test_clip.mp4 not found — skipping integration tests")
@unittest.skipUnless(upscale.find_ffmpeg(), "ffmpeg not available — skipping integration tests")
class TestUpscaleSimple(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ffmpeg  = upscale.find_ffmpeg()
        cls.ffprobe = str(Path(cls.ffmpeg).parent / "ffprobe.exe")

    def test_output_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "out_simple.mp4")
            upscale.upscale_simple(str(TEST_CLIP), out, 1280, 720, self.ffmpeg, self.ffprobe)
            self.assertTrue(Path(out).exists())
            self.assertGreater(Path(out).stat().st_size, 0)

    def test_output_resolution_matches_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "out_720p.mp4")
            upscale.upscale_simple(str(TEST_CLIP), out, 1280, 720, self.ffmpeg, self.ffprobe)
            w, h, _, _ = upscale.get_video_info(self.ffprobe, out)
            self.assertEqual(w, 1280)
            self.assertEqual(h, 720)

    def test_cleanup_on_nonexistent_output(self):
        upscale._cleanup("/no/such/file.mp4")

    def test_invalid_input_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "out.mp4")
            with self.assertRaises(Exception):
                upscale.upscale_simple("/nonexistent.mp4", out, 1280, 720,
                                       self.ffmpeg, self.ffprobe)


# ─────────────────────────────────────────────────────────────────────────────
# batch_upscale.process_file  (mocked subprocess)
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessFile(unittest.TestCase):

    def _make_args(self, mode="simple", target="1080p", model="RealESRGAN_x4plus"):
        args = MagicMock()
        args.mode   = mode
        args.target = target
        args.model  = model
        return args

    @patch("batch_upscale.subprocess.run")
    def test_success_returns_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = batch_upscale.process_file(Path("in.mp4"), Path("out.mp4"),
                                            self._make_args())
        self.assertTrue(result)

    @patch("batch_upscale.subprocess.run")
    def test_failure_returns_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = batch_upscale.process_file(Path("in.mp4"), Path("out.mp4"),
                                            self._make_args())
        self.assertFalse(result)

    @patch("batch_upscale.subprocess.run")
    def test_simple_mode_no_model_arg(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        batch_upscale.process_file(Path("in.mp4"), Path("out.mp4"),
                                   self._make_args(mode="simple"))
        cmd = mock_run.call_args[0][0]
        self.assertNotIn("--model", cmd)

    @patch("batch_upscale.subprocess.run")
    def test_ai_mode_includes_model_arg(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        batch_upscale.process_file(Path("in.mp4"), Path("out.mp4"),
                                   self._make_args(mode="ai", model="RealESRGAN_x2plus"))
        cmd = mock_run.call_args[0][0]
        self.assertIn("--model", cmd)
        self.assertIn("RealESRGAN_x2plus", cmd)

    @patch("batch_upscale.subprocess.run")
    def test_target_forwarded_correctly(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        batch_upscale.process_file(Path("in.mp4"), Path("out.mp4"),
                                   self._make_args(target="4k"))
        cmd = mock_run.call_args[0][0]
        idx = cmd.index("--target")
        self.assertEqual(cmd[idx + 1], "4k")


if __name__ == "__main__":
    unittest.main(verbosity=2)
