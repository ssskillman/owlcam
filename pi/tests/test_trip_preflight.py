import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


def load_trip_preflight():
    scripts = Path(__file__).parents[1] / "scripts"
    path = scripts / "trip_preflight.py"
    spec = importlib.util.spec_from_file_location("trip_preflight", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


trip_preflight = load_trip_preflight()


class TripPreflightTests(unittest.TestCase):
    def test_upload_hint_when_local_hls_fails(self):
        hint = trip_preflight.upload_hint_mbps(4.5, False)
        self.assertIn("Fix local HLS", hint)

    def test_estimate_upload_sums_active_streams(self):
        estimate = trip_preflight.estimate_upload_mbps(
            nest_active=True,
            usb_active=True,
            nest_bitrate=2_500_000,
        )
        self.assertGreater(estimate, 4)

    @patch.object(trip_preflight, "probe_local_hls")
    def test_collect_preflight_shapes_payload(self, probe):
        probe.return_value = {
            "path": "owl",
            "ok": True,
            "httpCode": 200,
            "latencyMs": 12,
            "note": None,
        }

        def run(command, timeout=4):
            result = MagicMock()
            result.returncode = 0
            if "tailscale" in command:
                result.stdout = '{"AllowFunnel":{"node":true}}'
            else:
                result.stdout = "active\n"
            return result

        payload = trip_preflight.collect_preflight(
            run=run,
            wifi_connection=lambda: "GuestWiFi",
            service_state=lambda _unit: "active",
            stream_unit="owlcam-stream.service",
            stream_usb_unit="owlcam-stream-usb.service",
        )
        self.assertEqual(payload["wifiConnection"], "GuestWiFi")
        self.assertEqual(payload["tailscaleExposure"], "public")
        self.assertTrue(payload["localHls"]["ok"])
        self.assertIn("uploadHint", payload)


if __name__ == "__main__":
    unittest.main()
