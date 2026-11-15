import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import event_retention


def _rows(*names):
    return [{"name": name, "bytes": 1_000_000} for name in names]


class RetentionTests(unittest.TestCase):
    def test_dry_run_has_no_writes(self):
        c = Mock()
        c.rpc.return_value.execute.return_value.data = _rows("old.jpg")
        with patch.object(event_retention, "client", return_value=c):
            result = event_retention.main(dry_run=True)
        c.rpc.assert_called_once_with("unused_event_flyers", {"max_rows": event_retention.BATCH_SIZE})
        c.storage.from_.assert_not_called()
        self.assertEqual((1, 0), (result["eligible_flyers"], result["removed_flyers"]))

    def test_storage_failure_keeps_candidates_retryable(self):
        c = Mock()
        c.rpc.return_value.execute.side_effect = [SimpleNamespace(data=50), SimpleNamespace(data=_rows("old.jpg"))]
        c.storage.from_.return_value.remove.side_effect = RuntimeError("storage down")
        with patch.object(event_retention, "client", return_value=c):
            with self.assertRaisesRegex(RuntimeError, "storage down"):
                event_retention.main()
        c.table.assert_not_called()

    def test_partial_removal_stops_and_reports(self):
        c = Mock()
        c.rpc.return_value.execute.side_effect = [SimpleNamespace(data=0), SimpleNamespace(data=_rows("a.jpg", "b.jpg"))]
        c.storage.from_.return_value.remove.return_value = [{"name": "a.jpg"}]
        with patch.object(event_retention, "client", return_value=c):
            with self.assertRaisesRegex(RuntimeError, "1/2"):
                event_retention.main()

    def test_storage_api_deletes_only_the_planned_paths_in_batches(self):
        c = Mock()
        c.rpc.return_value.execute.side_effect = [
            SimpleNamespace(data=2), SimpleNamespace(data=_rows("a.jpg", "b.jpg")),
            SimpleNamespace(data=_rows("c.jpg"))]
        c.storage.from_.return_value.remove.side_effect = lambda names: [{"name": n} for n in names]
        with patch.object(event_retention, "client", return_value=c), \
             patch.object(event_retention, "BATCH_SIZE", 2):
            result = event_retention.main()
        c.storage.from_.assert_called_with("event-flyers")
        self.assertEqual([(["a.jpg", "b.jpg"],), (["c.jpg"],)],
                         [call.args for call in c.storage.from_.return_value.remove.call_args_list])
        # The short second batch shows the backlog is empty; no third listing.
        self.assertEqual(3, c.rpc.call_count)
        self.assertEqual((3, 3, 3.0), (result["eligible_flyers"], result["removed_flyers"], result["removed_mb"]))

    def test_each_run_deletes_at_most_its_budget(self):
        c = Mock()
        c.rpc.return_value.execute.side_effect = [
            SimpleNamespace(data=0), SimpleNamespace(data=_rows("a.jpg", "b.jpg")),
            SimpleNamespace(data=_rows("c.jpg"))]
        c.storage.from_.return_value.remove.side_effect = lambda names: [{"name": n} for n in names]
        with patch.object(event_retention, "client", return_value=c), \
             patch.object(event_retention, "BATCH_SIZE", 2):
            result = event_retention.main(max_flyers=3)
        self.assertEqual([call.args for call in c.rpc.call_args_list][1:],
                         [("unused_event_flyers", {"max_rows": 2}), ("unused_event_flyers", {"max_rows": 1})])
        self.assertEqual(3, result["removed_flyers"])
