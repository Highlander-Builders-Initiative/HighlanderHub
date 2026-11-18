import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import project_usage  # noqa: E402

MB = 1024 * 1024


class ProjectUsageTests(unittest.TestCase):
    def test_room_under_both_limits_reports_shares(self):
        report = project_usage.check({"database_bytes": 83 * MB, "storage_bytes": 36 * MB,
                                      "storage_files": 210})
        self.assertEqual({"database_mb": 83.0, "database_share": 0.166, "storage_mb": 36.0,
                          "storage_share": 0.035, "storage_files": 210}, report)

    def test_either_quota_near_its_limit_fails_the_stage(self):
        for usage, name in (({"database_bytes": 400 * MB, "storage_bytes": 0}, "database"),
                            ({"database_bytes": 0, "storage_bytes": 820 * MB}, "storage")):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, name):
                project_usage.check({**usage, "storage_files": 1})

    def test_reads_sizes_through_the_rpc(self):
        client = MagicMock()
        client.rpc.return_value.execute.return_value.data = [
            {"database_bytes": MB, "storage_bytes": MB, "storage_files": 1}]
        with patch("db.client", return_value=client):
            self.assertEqual(1.0, project_usage.main()["storage_mb"])
        client.rpc.assert_called_once_with("project_usage")
        client.rpc.return_value.execute.return_value.data = []
        with patch("db.client", return_value=client), self.assertRaises(RuntimeError):
            project_usage.main()


if __name__ == "__main__":
    unittest.main()
