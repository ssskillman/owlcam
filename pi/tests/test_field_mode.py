import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock


def load_field_mode():
    path = Path(__file__).parents[1] / "scripts" / "field_mode.py"
    spec = importlib.util.spec_from_file_location("field_mode", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


field_mode = load_field_mode()


class FieldModeTests(unittest.TestCase):
    def test_read_disabled_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "field-mode.env"
            config = field_mode.read_field_mode_config(env_path)
            self.assertFalse(config["enabled"])
            self.assertEqual(config["nestBitrate"], field_mode.HOME_BITRATE)

    def test_write_enable_and_disable(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "field-mode.env"
            field_mode.write_field_mode_env(True, env_path)
            self.assertTrue(env_path.is_file())
            config = field_mode.read_field_mode_config(env_path)
            self.assertTrue(config["enabled"])
            self.assertEqual(config["nestBitrate"], field_mode.FIELD_BITRATE)
            field_mode.write_field_mode_env(False, env_path)
            self.assertFalse(env_path.exists())

    def test_apply_stops_usb_and_restarts_nest(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "field-mode.env"
            calls = []

            def run(command, timeout=4):
                calls.append(command)
                result = MagicMock()
                result.returncode = 0
                result.stdout = "inactive\n"
                return result

            payload = field_mode.apply_field_mode(
                True,
                run=run,
                stream_unit="owlcam-stream.service",
                stream_usb_unit="owlcam-stream-usb.service",
                path=env_path,
            )
            self.assertTrue(payload["enabled"])
            self.assertIn(
                ["systemctl", "--user", "stop", "owlcam-stream-usb.service"],
                calls,
            )
            self.assertIn(
                ["systemctl", "--user", "restart", "owlcam-stream.service"],
                calls,
            )


if __name__ == "__main__":
    unittest.main()
