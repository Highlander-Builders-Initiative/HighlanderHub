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


class DeleteQuery:
    def __init__(self) -> None:
        self.table_name = None
        self.ids = None
        self.lock_filter = None

    def table(self, name):
        self.table_name = name
        return self

    def delete(self):
        return self

    def in_(self, column, values):
        self.ids = (column, values)
        return self

    def eq(self, column, value):
        self.lock_filter = (column, value)
        return self

    def execute(self):
        return types.SimpleNamespace(data=[{"id": "ig_stale_20260602T1900Z"}])


class DbTests(unittest.TestCase):
    def test_delete_unlocked_event_rows_by_ids_filters_locked_rows_atomically(
        self,
    ) -> None:
        query = DeleteQuery()

        with patch.object(db, "client", return_value=query):
            deleted = db.delete_unlocked_event_rows_by_ids(
                ["ig_locked_20260601T1900Z", "ig_stale_20260602T1900Z"]
            )

        self.assertEqual(1, deleted)
        self.assertEqual("events", query.table_name)
        self.assertEqual(
            (
                "id",
                ["ig_locked_20260601T1900Z", "ig_stale_20260602T1900Z"],
            ),
            query.ids,
        )
        self.assertEqual(("is_locked", False), query.lock_filter)


if __name__ == "__main__":
    unittest.main()
