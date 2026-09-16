from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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
