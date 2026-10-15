"""Explicit account-switch recovery retains paid intent and unrelated state."""
import json
import tempfile
import unittest
from pathlib import Path

import cache_state
from retire_apify_recheck import retire


class RetireRecheckTests(unittest.TestCase):
    def test_encrypted_recovery_preserves_backup_and_every_unrelated_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"
            data.mkdir()
            pending = data / "post_recheck_run-details.json"
            original = b'{"id":"oldRun","consumed":false,"usernames":["POST"]}'
            pending.write_bytes(original)
            unrelated = {"post_rechecks.json": b'{"123":{"misses":1}}',
                         "apify_plan.json": b'{"complete":false}',
                         "posts/123/post.json": b'{"caption":"saved"}',
                         "post_extractions/123.json": b'{"ocr":"saved"}'}
            for name, content in unrelated.items():
                path = data / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            archive = root / "state.enc"
            restored = root / "restored"
            cache_state.encrypt(data, archive, bytes(32))
            cache_state.decrypt(archive, restored, bytes(32))
            backup = retire(restored, "oldRun")
            self.assertEqual(original, backup.read_bytes())
            self.assertFalse((restored / pending.name).exists())
            self.assertEqual(backup, retire(restored, "oldRun"))
            cache_state.encrypt(restored, archive, bytes(32))
            final = root / "final"
            cache_state.decrypt(archive, final, bytes(32))
            self.assertEqual(original, (final / backup.name).read_bytes())
            self.assertFalse((final / pending.name).exists())
            for name, content in unrelated.items():
                self.assertEqual(content, (final / name).read_bytes())

    def test_wrong_id_consumed_run_and_existing_backup_leave_pending_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary)
            pending = data / "post_recheck_run-details.json"
            for saved, requested in (({"id": "oldRun", "consumed": False}, "different"),
                                     ({"id": "oldRun", "consumed": True}, "oldRun"),
                                     ({"starting": True, "consumed": False}, "oldRun")):
                with self.subTest(saved=saved):
                    original = json.dumps(saved).encode()
                    pending.write_bytes(original)
                    with self.assertRaises(ValueError):
                        retire(data, requested)
                    self.assertEqual(original, pending.read_bytes())
            pending.write_text('{"id":"oldRun","consumed":false}')
            backup = data / "post_recheck_run-details.retired-oldRun.json"
            backup.write_bytes(b"previous backup")
            with self.assertRaises(ValueError):
                retire(data, "oldRun")
            self.assertTrue(pending.exists())
            self.assertEqual(b"previous backup", backup.read_bytes())

    def test_invalid_ids_cannot_escape_the_data_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            for run_id in ("", "../oldRun", "old/Run", "old Run"):
                with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                    retire(Path(temporary), run_id)
