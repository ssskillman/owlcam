import importlib.util
import json
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
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
                "pressureHpa": None,
                "sampledAt": None,
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
                    "pressureHpa": 1001.8,
                    "sampledAt": "2026-08-30T02:29:00Z",
                },
            )

        self.assertEqual(payload["climate"]["sensor"], "bme280")
        self.assertEqual(payload["climate"]["temperatureC"], 12.4)
        self.assertEqual(payload["climate"]["humidityPercent"], 63.2)
        self.assertEqual(payload["climate"]["pressureHpa"], 1001.8)
        self.assertEqual(payload["climate"]["sampledAt"], "2026-08-30T02:29:00Z")
        self.assertTrue(payload["climate"]["connected"])
        # CPU die temperature stays a separate metric from nest air.
        self.assertEqual(payload["temperatureC"], 50.0)

    def test_read_climate_returns_a_copy_of_the_cache(self):
        diagnostics.set_climate_cache(diagnostics.DISCONNECTED_CLIMATE)
        sample = diagnostics.read_climate()
        self.assertEqual(sample, diagnostics.DISCONNECTED_CLIMATE)
        sample["connected"] = True
        self.assertFalse(diagnostics.read_climate()["connected"])

    @patch.object(diagnostics, "read_bme280")
    def test_poll_climate_once_maps_sensor_reading(self, read_bme280):
        read_bme280.return_value = {
            "temperature_c": 26.05,
            "temperature_f": 78.89,
            "humidity_pct": 40.55,
            "pressure_hpa": 1001.82,
        }
        try:
            diagnostics._poll_climate_once()
            climate = diagnostics.read_climate()
            self.assertTrue(climate["connected"])
            self.assertEqual(climate["temperatureC"], 26.1)
            self.assertEqual(climate["humidityPercent"], 40.5)
            self.assertEqual(climate["pressureHpa"], 1001.8)
            self.assertTrue(climate["sampledAt"].endswith("Z"))
        finally:
            diagnostics.set_climate_cache(diagnostics.DISCONNECTED_CLIMATE)


class DiagnosticsHistoryTests(unittest.TestCase):
    def test_history_store_persists_numeric_trends_and_prunes_old_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostics-history.json"
            now = datetime(2026, 9, 24, 13, 0, tzinfo=UTC)
            store = diagnostics.HistoryStore(
                path,
                retention=timedelta(hours=24),
                clock=lambda: now,
            )
            recent = dict(DiagnosticsHTTPTests.PAYLOAD)
            recent["sampledAt"] = "2026-09-24T12:59:00Z"
            recent["climate"] = {
                "connected": True,
                "sensor": "bme280",
                "temperatureC": 20.4,
                "humidityPercent": 56.5,
                "pressureHpa": 1006.6,
                "sampledAt": "2026-09-24T12:59:00Z",
            }
            old = dict(recent)
            old["sampledAt"] = "2026-09-23T12:00:00Z"

            store.add(old)
            store.add(recent)

            self.assertEqual(
                store.samples(),
                [
                    {
                        "sampledAt": "2026-09-24T12:59:00Z",
                        "habitatTemperatureC": 20.4,
                        "humidityPercent": 56.5,
                        "pressureHpa": 1006.6,
                        "temperatureC": 54.5,
                        "memoryAvailableGiB": 1.4,
                        "load1": 0.56,
                        "stableProcessCount": 3,
                    }
                ],
            )
            self.assertEqual(
                diagnostics.HistoryStore(
                    path,
                    retention=timedelta(hours=24),
                    clock=lambda: now,
                ).samples(),
                store.samples(),
            )

    def test_history_store_keeps_weeks_but_can_still_serve_one_day(self):
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 9, 24, 13, 0, tzinfo=UTC)
            store = diagnostics.HistoryStore(
                Path(directory) / "diagnostics-history.json",
                clock=lambda: now,
            )
            climate = {
                "connected": True,
                "sensor": "bme280",
                "temperatureC": 20.4,
                "humidityPercent": 56.5,
                "pressureHpa": 1006.6,
                "sampledAt": "2026-09-24T12:59:00Z",
            }
            recent = dict(DiagnosticsHTTPTests.PAYLOAD)
            recent["sampledAt"] = "2026-09-24T12:59:00Z"
            recent["climate"] = climate
            last_week = dict(recent)
            last_week["sampledAt"] = "2026-09-10T12:59:00Z"
            ancient = dict(recent)
            ancient["sampledAt"] = "2026-08-01T12:59:00Z"

            store.add(ancient)
            store.add(last_week)
            store.add(recent)

            sampled_at = [sample["sampledAt"] for sample in store.samples()]
            self.assertEqual(
                sampled_at,
                ["2026-09-10T12:59:00Z", "2026-09-24T12:59:00Z"],
            )
            self.assertEqual(
                [sample["sampledAt"] for sample in store.samples(hours=24)],
                ["2026-09-24T12:59:00Z"],
            )

    def test_disconnected_climate_is_recorded_as_missing_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            store = diagnostics.HistoryStore(
                Path(directory) / "history.json",
                clock=lambda: datetime(2026, 8, 30, 3, 0, tzinfo=UTC),
            )
            store.add(DiagnosticsHTTPTests.PAYLOAD)

            sample = store.samples()[0]

        self.assertIsNone(sample["habitatTemperatureC"])
        self.assertIsNone(sample["humidityPercent"])
        self.assertIsNone(sample["pressureHpa"])


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
            "pressureHpa": None,
            "sampledAt": None,
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

    def test_history_response_is_bounded_cache_free_json(self):
        sample = {
            "sampledAt": "2026-08-30T02:30:00Z",
            "temperatureC": 54.5,
        }
        with patch.object(
            diagnostics,
            "history_payload",
            return_value={"samples": [sample], "sampleIntervalSeconds": 60},
        ):
            request = Request(
                f"{self.url}/diagnostics/history?hours=24",
                headers={"Origin": self.ORIGIN},
            )
            with urlopen(request) as response:
                payload = json.load(response)

        self.assertEqual(payload["samples"], [sample])
        self.assertEqual(payload["sampleIntervalSeconds"], 60)

    def test_history_rejects_an_unbounded_window(self):
        request = Request(
            f"{self.url}/history?hours=1000",
            headers={"Origin": self.ORIGIN},
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def test_history_serves_the_retained_month(self):
        sample = {
            "sampledAt": "2026-08-30T02:30:00Z",
            "temperatureC": 54.5,
        }
        with patch.object(
            diagnostics,
            "history_payload",
            return_value={"samples": [sample], "sampleIntervalSeconds": 300},
        ):
            request = Request(
                f"{self.url}/diagnostics/history?hours=720",
                headers={"Origin": self.ORIGIN},
            )
            with urlopen(request) as response:
                payload = json.load(response)

        self.assertEqual(payload["samples"], [sample])


if __name__ == "__main__":
    unittest.main()
