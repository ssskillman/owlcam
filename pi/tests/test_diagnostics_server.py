import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "diagnostics_server.py"
SPEC = importlib.util.spec_from_file_location("owlcam_diagnostics", MODULE_PATH)
diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(diagnostics)


class DiagnosticsCollectionTests(unittest.TestCase):
    def test_collects_only_allowlisted_host_health_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "proc"
            proc.mkdir()
            (proc / "meminfo").write_text(
                "MemTotal:        1945600 kB\nMemAvailable:    1468006 kB\n"
            )
            (proc / "loadavg").write_text("0.56 0.53 0.48 1/150 42\n")
            thermal = root / "temp"
            thermal.write_text("54500\n")

            for pid, name in enumerate(("mediamtx", "rpicam-vid", "ffmpeg"), 1):
                process = proc / str(pid)
                process.mkdir()
                (process / "comm").write_text(f"{name}\n")

            payload = diagnostics.collect_diagnostics(
                proc_root=proc,
                thermal_path=thermal,
                climate_reader=lambda: diagnostics.DISCONNECTED_CLIMATE,
            )

        self.assertEqual(payload["temperatureC"], 54.5)
        self.assertEqual(payload["memoryAvailableGiB"], 1.4)
        self.assertEqual(payload["load1"], 0.56)
        self.assertEqual(
            payload["processes"],
            {"mediamtx": True, "camera": True, "ffmpeg": True},
        )
        self.assertTrue(payload["allProcessesStable"])
        self.assertEqual(
            payload["climate"],
            {
                "connected": False,
                "sensor": None,
                "temperatureC": None,
                "humidityPercent": None,
            },
        )
        self.assertTrue(payload["sampledAt"].endswith("Z"))
        self.assertNotIn("pid", json.dumps(payload).lower())
        self.assertNotIn("command", json.dumps(payload).lower())

    def test_includes_habitat_climate_when_a_sensor_is_present(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "proc"
            proc.mkdir()
            (proc / "meminfo").write_text("MemAvailable:    1468006 kB\n")
            (proc / "loadavg").write_text("0.10 0.10 0.10 1/150 42\n")
            thermal = root / "temp"
            thermal.write_text("50000\n")
            for pid, name in enumerate(("mediamtx", "rpicam-vid", "ffmpeg"), 1):
                process = proc / str(pid)
                process.mkdir()
                (process / "comm").write_text(f"{name}\n")

            payload = diagnostics.collect_diagnostics(
                proc_root=proc,
                thermal_path=thermal,
                climate_reader=lambda: {
                    "connected": True,
                    "sensor": "bme280",
                    "temperatureC": 12.4,
                    "humidityPercent": 63.2,
                },
            )

        self.assertEqual(payload["climate"]["sensor"], "bme280")
        self.assertEqual(payload["climate"]["temperatureC"], 12.4)
        self.assertEqual(payload["climate"]["humidityPercent"], 63.2)
        self.assertTrue(payload["climate"]["connected"])
        # CPU die temperature stays a separate metric from nest air.
        self.assertEqual(payload["temperatureC"], 50.0)

    def test_read_climate_without_a_bus_is_disconnected(self):
        sample = diagnostics.read_climate(bus_path=Path("/no/such/i2c"))
        self.assertEqual(sample, diagnostics.DISCONNECTED_CLIMATE)

    def test_bme280_temperature_matches_bosch_datasheet_example(self):
        # Bosch BME280 datasheet compensation example (temperature only).
        temperature_c, _humidity, t_fine = diagnostics.compensate_bme280(
            {
                "dig_T1": 27504,
                "dig_T2": 26435,
                "dig_T3": -1000,
                "dig_H1": 75,
                "dig_H2": 0,
                "dig_H3": 0,
                "dig_H4": 0,
                "dig_H5": 0,
                "dig_H6": 0,
            },
            adc_t=519888,
            adc_h=0,
        )
        self.assertAlmostEqual(temperature_c, 25.08, places=2)
        self.assertIsInstance(t_fine, int)


class DiagnosticsHTTPTests(unittest.TestCase):
    ORIGIN = "https://carver-owlcam-72343.web.app"
    PAYLOAD = {
        "temperatureC": 54.5,
        "memoryAvailableGiB": 1.4,
        "load1": 0.56,
        "processes": {"mediamtx": True, "camera": True, "ffmpeg": True},
        "allProcessesStable": True,
        "climate": {
            "connected": False,
            "sensor": None,
            "temperatureC": None,
            "humidityPercent": None,
        },
        "sampledAt": "2026-08-30T02:30:00Z",
    }

    def setUp(self):
        self.server = diagnostics.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            diagnostics.DiagnosticsHandler,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @patch.object(diagnostics, "collect_diagnostics", return_value=PAYLOAD)
    def test_health_response_is_private_cache_free_json(self, _collect):
        request = Request(
            f"{self.url}/diagnostics",
            headers={"Origin": self.ORIGIN},
        )
        with urlopen(request) as response:
            payload = json.load(response)
            headers = response.headers

        self.assertEqual(payload, self.PAYLOAD)
        self.assertEqual(headers["Access-Control-Allow-Origin"], self.ORIGIN)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers.get_content_type(), "application/json")

    def test_private_network_preflight_allows_only_the_site_origin(self):
        request = Request(
            f"{self.url}/diagnostics",
            method="OPTIONS",
            headers={
                "Origin": self.ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Private-Network": "true",
            },
        )
        with urlopen(request) as response:
            headers = response.headers

        self.assertEqual(response.status, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], self.ORIGIN)
        self.assertEqual(headers["Access-Control-Allow-Methods"], "GET")
        self.assertEqual(headers["Access-Control-Allow-Private-Network"], "true")

        blocked = Request(
            f"{self.url}/diagnostics",
            headers={"Origin": "https://attacker.example"},
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(blocked)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
