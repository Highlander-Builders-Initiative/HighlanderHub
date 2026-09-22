from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

import db  # noqa: E402


class SelectQuery:
    def __init__(self) -> None:
        self.table_name = None
        self.columns = None
        self.ids = None

    def table(self, name):
        self.table_name = name
        return self

    def select(self, columns):
        self.columns = columns
        return self

    def in_(self, column, values):
        self.ids = (column, values)
        return self

    def execute(self):
        return types.SimpleNamespace(data=[{"id": "ig_published"}])


class DbTests(unittest.TestCase):
    def test_deleted_event_ids_read_all_ordered_pages(self) -> None:
        for count in (0, 1000, 1003):
            with self.subTest(count=count):
                rows = [{"event_id": f"ig_{index:04d}"} for index in range(count)]
                query = Mock()
                query.table.return_value = query
                query.select.return_value = query
                query.order.return_value = query
                bounds = [0, 999]

                def select_range(start, end):
                    bounds[:] = [start, end]
                    return query

                query.range.side_effect = select_range
                query.execute.side_effect = lambda: types.SimpleNamespace(
                    data=rows[bounds[0]:bounds[1] + 1][:1000])
                with patch.object(db, "client", return_value=query):
                    deleted = db.get_deleted_event_ids()
                self.assertEqual({row["event_id"] for row in rows}, deleted)
                expected = [call(offset, offset + 999) for offset in range(0, count + 1, 1000)]
                self.assertEqual(expected, query.range.call_args_list)
                self.assertEqual([call("event_id")] * len(expected), query.order.call_args_list)
                query.table.assert_called_with("deleted_events")
                query.select.assert_called_with("event_id")

    def test_deleted_event_page_failure_does_not_return_partial_protection(self) -> None:
        query = Mock()
        query.table.return_value = query
        query.select.return_value = query
        query.order.return_value = query
        query.range.return_value = query
        query.execute.side_effect = [
            types.SimpleNamespace(data=[{"event_id": f"ig_{i}"} for i in range(1000)]),
            RuntimeError("database unavailable"),
        ]
        with patch.object(db, "client", return_value=query):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                db.get_deleted_event_ids()

    def test_get_event_rows_by_ids_reads_only_requested_stored_rows(self) -> None:
        query = SelectQuery()

        with patch.object(db, "client", return_value=query):
            rows = db.get_event_rows_by_ids(
                ["ig_published", "ig_suppressed", "ig_published"]
            )

        self.assertEqual([{"id": "ig_published"}], rows)
        self.assertEqual("events", query.table_name)
        self.assertEqual("*", query.columns)
        self.assertEqual(("id", ["ig_published", "ig_suppressed"]), query.ids)


if __name__ == "__main__":
    unittest.main()
