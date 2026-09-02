from __future__ import annotations

import importlib
import json
import pickle
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import requests


PIPELINE_ROOT = Path(__file__).resolve().parents[1]

if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


class ResolveIdsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fake_dotenv = types.ModuleType("dotenv")
        fake_dotenv.load_dotenv = lambda *args, **kwargs: None  # type: ignore[misc]
        cls._tmpdir = tempfile.TemporaryDirectory()
        accounts_path = Path(cls._tmpdir.name) / "accounts.json"
        fake_config = types.SimpleNamespace(
            ACCOUNTS_FILE=accounts_path,
            SESSION_FILE=None,
        )
        cls._saved_modules = {
            name: sys.modules.get(name) for name in ("config", "resolve_ids", "dotenv")
        }
        sys.modules["dotenv"] = fake_dotenv
        sys.modules["config"] = fake_config
        sys.modules.pop("resolve_ids", None)
        cls.resolve_ids = importlib.import_module("resolve_ids")
        cls.accounts_path = accounts_path

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()
        for name, mod in cls._saved_modules.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    def setUp(self) -> None:
        self.accounts_path.write_text(
            json.dumps(
                {
                    "accounts": [
                        {
                            "handle": "acm_ucr",
                            "label": "ACM @ UCR",
                            "category": "club",
                        },
                        {
                            "handle": "cyber_ucr",
                            "label": "Cyber @ UCR",
                            "category": "club",
                            "instagram_user_id": 38460809748,
                        },
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_parse_user_id_happy_path(self) -> None:
        payload = {"data": {"user": {"username": "acm_ucr", "id": "10839758322"}}}
        self.assertEqual(self.resolve_ids._parse_user_id(payload, "acm_ucr"), 10839758322)

    def test_parse_user_id_mismatch(self) -> None:
        payload = {"data": {"user": {"username": "other", "id": "1"}}}
        with self.assertRaises(self.resolve_ids.ResolveError):
            self.resolve_ids._parse_user_id(payload, "acm_ucr")

    def test_fills_missing_ids(self) -> None:
        accounts = self.resolve_ids.load_accounts(self.accounts_path)

        def fake_fetch(_session, handle: str) -> int:
            return {"acm_ucr": 10839758322, "cyber_ucr": 999}[handle]

        updated, stats = self.resolve_ids.resolve_accounts(
            accounts,
            session=mock.Mock(),
            force=False,
            dry_run=False,
            jitter=False,
            fetch_fn=fake_fetch,
        )
        by_handle = {a["handle"]: a for a in updated}
        self.assertEqual(by_handle["acm_ucr"]["instagram_user_id"], 10839758322)
        self.assertEqual(by_handle["cyber_ucr"]["instagram_user_id"], 38460809748)
        self.assertEqual(stats["filled"], 1)
        self.assertEqual(stats["unchanged"], 1)

    def test_skips_existing_unless_force(self) -> None:
        accounts = self.resolve_ids.load_accounts(self.accounts_path)
        calls: list[str] = []

        def fake_fetch(_session, handle: str) -> int:
            calls.append(handle)
            return 1

        self.resolve_ids.resolve_accounts(
            accounts,
            session=mock.Mock(),
            force=False,
            jitter=False,
            fetch_fn=fake_fetch,
        )
        self.assertEqual(calls, ["acm_ucr"])

        calls.clear()
        self.resolve_ids.resolve_accounts(
            accounts,
            session=mock.Mock(),
            force=True,
            jitter=False,
            fetch_fn=fake_fetch,
        )
        self.assertEqual(sorted(calls), ["acm_ucr", "cyber_ucr"])

    def test_dry_run_does_not_write(self) -> None:
        before = self.accounts_path.read_text(encoding="utf-8")
        accounts = self.resolve_ids.load_accounts(self.accounts_path)

        updated, stats = self.resolve_ids.resolve_accounts(
            accounts,
            session=mock.Mock(),
            dry_run=True,
            jitter=False,
            fetch_fn=lambda _s, _h: 10839758322,
        )
        self.assertEqual(stats["filled"], 1)
        self.assertEqual(updated[0]["instagram_user_id"], 10839758322)
        self.assertEqual(self.accounts_path.read_text(encoding="utf-8"), before)

    def test_failure_preserves_file_contents_on_write_path(self) -> None:
        accounts = self.resolve_ids.load_accounts(self.accounts_path)

        def boom(_session, handle: str) -> int:
            raise self.resolve_ids.ResolveError("profile not found (404)")

        updated, stats = self.resolve_ids.resolve_accounts(
            accounts,
            session=mock.Mock(),
            jitter=False,
            fetch_fn=boom,
        )
        self.assertEqual(stats["failed"], 1)
        self.assertNotIn("instagram_user_id", updated[0])
        # Existing ID untouched
        self.assertEqual(updated[1]["instagram_user_id"], 38460809748)

    def test_write_accounts_atomic_roundtrip(self) -> None:
        accounts = [
            {
                "handle": "acm_ucr",
                "label": "ACM @ UCR",
                "category": "club",
                "instagram_user_id": 10839758322,
            }
        ]
        self.resolve_ids.write_accounts(self.accounts_path, accounts)
        loaded = self.resolve_ids.load_accounts(self.accounts_path)
        self.assertEqual(loaded, accounts)

    def _write_session_file(self, cookies: dict[str, str]) -> Path:
        path = Path(self._tmpdir.name) / "session-test"
        with path.open("wb") as fh:
            pickle.dump(cookies, fh)
        return path

    def test_attach_ig_session_copies_cookies_and_csrf_header(self) -> None:
        session_file = self._write_session_file(
            {
                "sessionid": "sess-abc",
                "csrftoken": "csrf-xyz",
                "ds_user_id": "123",
            }
        )
        session = requests.Session()
        self.resolve_ids.attach_ig_session(session, session_file)
        self.assertEqual(session.cookies.get("sessionid"), "sess-abc")
        self.assertEqual(session.cookies.get("ds_user_id"), "123")
        self.assertEqual(session.headers["x-csrftoken"], "csrf-xyz")

    def test_attach_ig_session_requires_session_file(self) -> None:
        session = requests.Session()
        with self.assertRaises(SystemExit):
            self.resolve_ids.attach_ig_session(session, None)

    def test_attach_ig_session_requires_sessionid_cookie(self) -> None:
        session_file = self._write_session_file({"csrftoken": "csrf-xyz"})
        session = requests.Session()
        with self.assertRaises(SystemExit):
            self.resolve_ids.attach_ig_session(session, session_file)

    def test_parse_search_user_id_exact_match(self) -> None:
        payload = {
            "users": [
                {"user": {"username": "other", "pk": "1"}},
                {"user": {"username": "aart.ucr", "pk": "615000"}},
            ]
        }
        self.assertEqual(
            self.resolve_ids._parse_search_user_id(payload, "aart.ucr"), 615000
        )

    def test_parse_search_user_id_no_match(self) -> None:
        payload = {"users": [{"user": {"username": "other", "pk": "1"}}]}
        with self.assertRaises(self.resolve_ids.ResolveError):
            self.resolve_ids._parse_search_user_id(payload, "aart.ucr")

    def test_fetch_user_id_falls_back_to_search_on_400(self) -> None:
        session = mock.Mock()
        profile_resp = mock.Mock(
            status_code=400,
            text='{"message":"Asset asset://laser.provider/ig_business_category_subvertical has been deleted.","status":"fail"}',
        )
        search_resp = mock.Mock(status_code=200)
        search_resp.json.return_value = {
            "users": [{"user": {"username": "aart.ucr", "pk": "615000"}}]
        }
        session.get.side_effect = [profile_resp, search_resp]
        self.assertEqual(self.resolve_ids.fetch_user_id(session, "aart.ucr"), 615000)
        self.assertEqual(session.get.call_count, 2)

    def test_fetch_user_id_falls_back_to_search_when_profile_omits_id(self) -> None:
        session = mock.Mock()
        profile_resp = mock.Mock(status_code=200)
        profile_resp.json.return_value = {
            "data": {"user": {"username": "activemindsucr"}}
        }
        search_resp = mock.Mock(status_code=200)
        search_resp.json.return_value = {
            "users": [{"user": {"username": "activemindsucr", "pk": "222"}}]
        }
        session.get.side_effect = [profile_resp, search_resp]
        self.assertEqual(self.resolve_ids.fetch_user_id(session, "activemindsucr"), 222)

    def test_fetch_user_id_does_not_search_on_404(self) -> None:
        session = mock.Mock()
        session.get.return_value = mock.Mock(status_code=404, text="")
        with self.assertRaises(self.resolve_ids.ResolveError) as ctx:
            self.resolve_ids.fetch_user_id(session, "abhinaya.ucr")
        self.assertIn("404", str(ctx.exception))
        self.assertEqual(session.get.call_count, 1)

    def test_checkpoint_writes_filled_id_immediately(self) -> None:
        accounts = self.resolve_ids.load_accounts(self.accounts_path)

        def fake_fetch(_session, handle: str) -> int:
            return 10839758322

        self.resolve_ids.resolve_accounts(
            accounts,
            session=mock.Mock(),
            jitter=False,
            fetch_fn=fake_fetch,
            checkpoint_path=self.accounts_path,
        )
        loaded = self.resolve_ids.load_accounts(self.accounts_path)
        self.assertEqual(loaded[0]["instagram_user_id"], 10839758322)
        self.assertEqual(loaded[1]["instagram_user_id"], 38460809748)


if __name__ == "__main__":
    unittest.main()
