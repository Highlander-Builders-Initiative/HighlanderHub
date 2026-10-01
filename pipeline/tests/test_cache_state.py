"""Private Actions cache integrity and safe recovery."""
import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import cache_state


class CacheStateTests(unittest.TestCase):
    def test_round_trip_retains_paid_intent_and_failed_run_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            (source / "apify_runs").mkdir(parents=True)
            (source / "apify_runs/pending.json").write_text('{"consumed":false,"id":"paid-run"}')
            (source / "run.log").write_text("private diagnostic")
            archive = root / "state.enc"
            cache_state.encrypt(source, archive, bytes(32))
            self.assertNotIn(b"paid-run", archive.read_bytes())
            self.assertNotIn(b"private diagnostic", archive.read_bytes())
            destination = root / "restored"
            cache_state.decrypt(archive, destination, bytes(32))
            self.assertEqual((destination / "apify_runs/pending.json").read_bytes(),
                             (source / "apify_runs/pending.json").read_bytes())
            self.assertEqual((destination / "run.log").read_text(), "private diagnostic")
            for invalid in (bytes([1]) * 32,):
                with self.assertRaises(InvalidTag):
                    cache_state.decrypt(archive, destination, invalid)
            payload = bytearray(archive.read_bytes())
            payload[-1] ^= 1
            archive.write_bytes(payload)
            with self.assertRaises(InvalidTag):
                cache_state.decrypt(archive, destination, bytes(32))
            self.assertEqual((destination / "run.log").read_text(), "private diagnostic")

    def test_traversal_and_links_do_not_modify_existing_state(self):
        for name, kind in (("../outside", tarfile.REGTYPE),
                           ("/absolute", tarfile.REGTYPE),
                           ("link", tarfile.SYMTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                data = io.BytesIO()
                with tarfile.open(fileobj=data, mode="w:gz") as tar:
                    info = tarfile.TarInfo(name)
                    info.type = kind
                    tar.addfile(info)
                nonce = os.urandom(12)
                archive = root / "state.enc"
                archive.write_bytes(cache_state.FORMAT + nonce + AESGCM(bytes(32)).encrypt(
                    nonce, data.getvalue(), cache_state.FORMAT))
                with self.assertRaises(ValueError):
                    cache_state.decrypt(archive, root / "restored", bytes(32))
                self.assertFalse((root / "restored").exists())
                self.assertFalse((root / "outside").exists())

    def test_key_is_required_and_must_be_random_byte_hex_encoding(self):
        for value in ("", "placeholder", "g" * 64):
            with patch.dict(os.environ, {"PIPELINE_CACHE_KEY": value}):
                with self.assertRaises(ValueError):
                    cache_state.cache_key()
        with patch.dict(os.environ, {"PIPELINE_CACHE_KEY": "ab" * 32}):
            self.assertEqual(cache_state.cache_key(), bytes.fromhex("ab" * 32))

    def test_symlink_source_and_destination_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "run.log").write_text("private")
            (source / "link").symlink_to(root / "outside")
            archive = root / "state.enc"
            with self.assertRaises(ValueError):
                cache_state.encrypt(source, archive, bytes(32))
            (source / "link").unlink()
            cache_state.encrypt(source, archive, bytes(32))
            (root / "outside").mkdir()
            (root / "restored").symlink_to(root / "outside", target_is_directory=True)
            with self.assertRaises(ValueError):
                cache_state.decrypt(archive, root / "restored", bytes(32))
            self.assertFalse((root / "outside/run.log").exists())
