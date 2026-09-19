import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "bme280_raw.py"
SPEC = importlib.util.spec_from_file_location("bme280_raw", MODULE_PATH)
bme280_raw = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(bme280_raw)


class Bme280RawTests(unittest.TestCase):
    def test_run_i2c_retries_then_raises(self):
        with patch.object(bme280_raw.subprocess, "run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "Remote I/O error"
            with self.assertRaises(RuntimeError) as error:
                bme280_raw.run_i2c(["w1@0x76", "0xd0", "r1"], retries=3, delay=0)
        self.assertIn("3 attempts", str(error.exception))
        self.assertEqual(run.call_count, 3)

    @patch.object(bme280_raw, "read_reg")
    @patch.object(bme280_raw, "write_reg")
    def test_read_bme280_rejects_invalid_temperature_adc(
        self, _write_reg, mock_read_reg
    ):
        cal1 = [0] * 26
        cal1[25] = 75
        cal2 = [0] * 7

        def read_side_effect(register, length=1):
            if register == 0xF3 and length == 1:
                return [0x00]
            if register == 0xD0:
                return [0x60]
            if register == 0x88 and length == 26:
                return cal1
            if register == 0xE1 and length == 7:
                return cal2
            if register == 0xF7 and length == 8:
                return [0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00]
            raise AssertionError(f"unexpected read_reg({register}, {length})")

        mock_read_reg.side_effect = read_side_effect

        with self.assertRaises(RuntimeError):
            bme280_raw.read_bme280()


if __name__ == "__main__":
    unittest.main()
