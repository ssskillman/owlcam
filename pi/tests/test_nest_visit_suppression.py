import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "nest_visit_suppression.py"
SPEC = importlib.util.spec_from_file_location("nest_visit_suppression", MODULE_PATH)
suppression = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(suppression)


class SuppressionStoreTests(unittest.TestCase):
    def test_suppress_and_list(self):
        with patch.object(suppression, "suppression_path") as path:
            target = Path(self.id())
            path.return_value = target
            suppression.suppress_visit(9)
            suppression.suppress_visit(3)
            self.assertEqual(suppression.load_suppressed_ids(), {3, 9})
            payload = suppression.list_suppressed_payload()
            self.assertEqual(payload["visitIds"], [3, 9])
            suppression.unsuppress_visit(3)
            self.assertEqual(suppression.load_suppressed_ids(), {9})

    def test_save_writes_json(self):
        with patch.object(suppression, "suppression_path") as path:
            target = Path(self.id()) / "suppressed.json"
            path.return_value = target
            suppression.suppress_visit(12)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["visitIds"], [12])


if __name__ == "__main__":
    unittest.main()
