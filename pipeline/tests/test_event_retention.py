import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import event_retention


class RetentionTests(unittest.TestCase):
    def test_dry_run_has_no_writes(self):
        c = Mock()
        c.rpc.return_value.execute.return_value.data = [{"name": "old.jpg", "bytes": 42}]
        with patch.object(event_retention, "client", return_value=c):
            result = event_retention.main(dry_run=True)
        c.rpc.assert_called_once_with("old_event_flyers")
        c.storage.from_.assert_not_called()
        self.assertEqual(0, result["removed_flyers"])

    def test_storage_failure_keeps_candidates_retryable(self):
        c = Mock()
        c.rpc.return_value.execute.side_effect = [SimpleNamespace(data=50),
            SimpleNamespace(data=[{"name": "old.jpg", "bytes": 42}])]
        c.storage.from_.return_value.remove.side_effect = RuntimeError("storage down")
        with patch.object(event_retention, "client", return_value=c):
            with self.assertRaisesRegex(RuntimeError, "storage down"):
                event_retention.main()
        c.table.assert_not_called()

    def test_storage_api_deletes_only_the_planned_paths(self):
        c = Mock()
        c.rpc.return_value.execute.side_effect = [SimpleNamespace(data=2),
            SimpleNamespace(data=[{"name": "old.jpg", "bytes": 42}])]
        c.storage.from_.return_value.remove.return_value = [{"name": "old.jpg"}]
        with patch.object(event_retention, "client", return_value=c):
            result = event_retention.main()
        c.storage.from_.assert_called_once_with("event-flyers")
        c.storage.from_.return_value.remove.assert_called_once_with(["old.jpg"])
        self.assertEqual(1, result["removed_flyers"])
