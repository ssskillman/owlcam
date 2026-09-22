import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "feed_watcher.py"
SPEC = importlib.util.spec_from_file_location("owlcam_feed_watcher", MODULE_PATH)
watcher = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(watcher)


class FeedWatcherTests(unittest.TestCase):
    def test_outbox_sorted_oldest_first(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            watcher.OUTBOX = root
            a = root / "a.jpg"
            b = root / "b.jpg"
            a.write_bytes(b"jpeg")
            time.sleep(0.02)
            b.write_bytes(b"jpeg")
            os.utime(a, (1, 1))
            os.utime(b, (2, 2))
            names = [path.name for path in watcher.outbox_files()]
            self.assertEqual(names, ["a.jpg", "b.jpg"])

    def test_trim_outbox_drops_oldest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            watcher.OUTBOX = root
            watcher.MAX_OUTBOX = 2
            for name in ("one.jpg", "two.jpg", "three.jpg"):
                (root / name).write_bytes(b"x")
            watcher.trim_outbox()
            remaining = {path.name for path in watcher.outbox_files()}
            self.assertEqual(remaining, {"two.jpg", "three.jpg"})

    @patch("urllib.request.urlopen")
    def test_post_still_moves_to_sent_on_success(self, urlopen):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outbox = root / "outbox"
            sent = root / "sent"
            failed = root / "failed"
            outbox.mkdir()
            sent.mkdir()
            failed.mkdir()
            watcher.OUTBOX = outbox
            watcher.SENT = sent
            watcher.FAILED = failed
            watcher.IDENTIFY_URL = "https://example.test/identify"
            still = outbox / "2026.jpg"
            still.write_bytes(b"jpeg-bytes")

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def read(self):
                    return b'{"results":[{"classification":"barred owl","is_unknown":false,"confidence":0.9}]}'

            urlopen.return_value = FakeResponse()
            done, retry = watcher.post_still(still)
            self.assertTrue(done)
            self.assertFalse(retry)
            self.assertFalse(still.exists())
            self.assertTrue((sent / "2026.jpg").is_file())


if __name__ == "__main__":
    unittest.main()
