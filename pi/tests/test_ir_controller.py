import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import ir_controller as ir  # noqa: E402


class IrControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OWLCAM_IR_MOCK_GPIO"] = "1"

    def test_startup_forces_gpio_low(self) -> None:
        gpio = ir.MockGpioBackend(23)
        config = ir.IrConfig(gpio=23, mode=ir.IrMode.OFF)
        controller = ir.IRController(config=config, gpio=gpio, clock=lambda: 0.0)
        self.assertEqual(gpio.read_output(), 0)
        controller.cleanup()

    def test_auto_pulse_extends_timeout(self) -> None:
        gpio = ir.MockGpioBackend(23)
        now = [100.0]
        config = ir.IrConfig(
            gpio=23,
            mode=ir.IrMode.AUTO,
            auto_timeout_seconds=20,
            max_continuous_on_seconds=60,
        )
        controller = ir.IRController(config=config, gpio=gpio, clock=lambda: now[0])
        controller.set_mode(ir.IrMode.AUTO)
        controller.pulse(reason="motion")
        self.assertEqual(gpio.read_output(), 1)
        now[0] = 115.0
        controller.pulse(reason="motion")
        now[0] = 119.0
        controller.tick()
        self.assertEqual(gpio.read_output(), 1)
        now[0] = 136.0
        controller.tick()
        self.assertEqual(gpio.read_output(), 0)
        controller.cleanup()

    def test_thermal_cutoff_and_cooldown(self) -> None:
        gpio = ir.MockGpioBackend(23)
        now = [0.0]
        config = ir.IrConfig(
            gpio=23,
            mode=ir.IrMode.MANUAL_ON,
            max_continuous_on_seconds=10,
            cooldown_seconds=5,
        )
        controller = ir.IRController(config=config, gpio=gpio, clock=lambda: now[0])
        controller.set_mode(ir.IrMode.MANUAL_ON)
        self.assertEqual(gpio.read_output(), 1)
        now[0] = 11.0
        controller.tick()
        self.assertEqual(gpio.read_output(), 0)
        controller.set_mode(ir.IrMode.AUTO)
        controller.pulse(reason="motion")
        self.assertEqual(gpio.read_output(), 0)
        now[0] = 16.0
        controller.set_mode(ir.IrMode.AUTO)
        controller.pulse(reason="motion")
        self.assertEqual(gpio.read_output(), 1)
        controller.cleanup()


class DarknessTests(unittest.TestCase):
    def test_simulate_dark(self) -> None:
        config = ir.IrConfig(simulate_dark=True)
        self.assertTrue(ir.is_dark_now(config))

    def test_midday_is_not_dark(self) -> None:
        config = ir.IrConfig(
            simulate_dark=False,
            latitude=35.7796,
            longitude=-78.6382,
            timezone="America/New_York",
        )
        tz = ZoneInfo("America/New_York")
        noon = datetime(2026, 6, 21, 12, 0, tzinfo=tz)
        self.assertFalse(ir.is_dark_now(config, noon))


if __name__ == "__main__":
    unittest.main()
