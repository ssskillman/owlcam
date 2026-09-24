import importlib.util
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "capture_audio.py"
SPEC = importlib.util.spec_from_file_location("owlcam_capture_audio", MODULE_PATH)
capture = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(capture)


def _write_silence_wav(path: Path, frames: int = 4800) -> None:
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(4)
        handle.setframerate(48000)
        handle.writeframes(b"\x00" * (frames * 4))


def _write_tone_wav(path: Path, frames: int = 4800) -> None:
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(4)
        handle.setframerate(48000)
        sample = (2**20).to_bytes(4, "little", signed=True)
        handle.writeframes(sample * frames)


class WavStatsTests(unittest.TestCase):
    def test_all_zero_wav_is_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "silent.wav"
            _write_silence_wav(path)
            stats = capture.wav_stats(path)
            self.assertTrue(stats["all_zero"])
            self.assertFalse(stats["clipped"])
            self.assertEqual(stats["peak"], 0)

    def test_nonzero_wav_is_not_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            _write_tone_wav(path)
            stats = capture.wav_stats(path)
            self.assertFalse(stats["all_zero"])
            self.assertGreater(stats["peak"], 0)


class CaptureAudioTests(unittest.TestCase):
    def test_missing_arecord_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.wav"
            with patch.object(capture.shutil, "which", return_value=None):
                with self.assertRaises(SystemExit) as error:
                    capture.main(["--duration", "1", "--output", str(output)])
            self.assertNotEqual(error.exception.code, 0)
            self.assertFalse(output.exists())

    def test_arecord_failure_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.wav"
            failed = subprocess.CompletedProcess(
                args=["arecord"],
                returncode=1,
                stdout=b"",
                stderr=b"arecord: No such file or directory",
            )
            with patch.object(capture.shutil, "which", return_value="/usr/bin/arecord"):
                with patch.object(capture.subprocess, "run", return_value=failed):
                    with self.assertRaises(SystemExit) as error:
                        capture.main(["--duration", "1", "--output", str(output)])
            self.assertNotEqual(error.exception.code, 0)

    def test_successful_arecord_keeps_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "out.wav"

            def fake_run(args, check=False, capture_output=False, text=False):
                del check, capture_output, text
                _write_tone_wav(Path(args[-1]))
                return subprocess.CompletedProcess(args, 0, b"", b"")

            with patch.object(capture.shutil, "which", return_value="/usr/bin/arecord"):
                with patch.object(capture.subprocess, "run", side_effect=fake_run):
                    capture.main(["--duration", "1", "--output", str(output)])
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 44)


if __name__ == "__main__":
    unittest.main()
