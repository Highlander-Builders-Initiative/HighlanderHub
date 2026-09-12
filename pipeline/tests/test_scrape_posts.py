"""Post collection: activation boundaries, pinned prefixes, and restart recovery."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import post_archive
import scrape_posts


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text)


class FakePost:
    """The parts of instaloader's Post that the collector reads."""

    def __init__(self, media_id, posted_at, *, caption="Flyer", images=1,
                 video=False, shortcode=None, owner="acm.ucr"):
        self.mediaid = media_id
        self.date_utc = instant(posted_at).astimezone(timezone.utc).replace(tzinfo=None)
        self.caption = caption
        self.caption_mentions = []
        self.shortcode = shortcode or f"C{media_id}"
        self.owner_username = owner
        self.owner_id = 42
        self.is_video = video and images == 1
        self.typename = ("GraphVideo" if video and images == 1
                         else "GraphSidecar" if images > 1 else "GraphImage")
        self._images = images
        self._video = video
        self.url = f"https://cdn.example/v/t51/{media_id}_0_n.jpg?oh=sig&oe=1&stp=x"

    def get_sidecar_nodes(self):
        for index in range(self._images):
            is_video = self._video and index == self._images - 1
            yield SimpleNamespace(
                is_video=is_video,
                display_url=f"https://cdn.example/v/t51/{self.mediaid}_{index}_n.jpg?oh=s{index}&oe=9",
                video_url=None,
            )


class PostArchiveTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for module, target, value in (
            (post_archive, "POSTS_DIR", self.root / "posts"),
            (scrape_posts, "POST_CHECKPOINTS_FILE", self.root / "post_checkpoints.json"),
        ):
            patcher = patch.object(module, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        remote = patch.object(scrape_posts, "write_remote_posts", Mock())
        self.remote_writes = remote.start()
        self.addCleanup(remote.stop)

    def scan(self, posts, checkpoint, now="2026-09-11T12:00:00+00:00"):
        profile = SimpleNamespace(get_posts=lambda: iter(posts))
        with patch.object(scrape_posts.instaloader.Profile, "from_username", return_value=profile):
            return scrape_posts.scan_account(
                Mock(), {"handle": "acm.ucr"}, checkpoint, instant(now)
            )


class MediaIdentityTests(unittest.TestCase):
    def test_signature_changes_do_not_change_media_identity(self):
        first = "https://cdn.example/v/t51/12345_0_n.jpg?stp=dst-jpg&oh=abc&oe=68F1&_nc_gid=x"
        second = "https://other.cdn.example/v/t51/12345_0_n.jpg?stp=other&oh=zzz&oe=9999"
        self.assertEqual(post_archive.media_key(first), post_archive.media_key(second))
        self.assertEqual("12345_0_n", post_archive.media_key(first))

    def test_different_media_keep_different_identities(self):
        self.assertNotEqual(
            post_archive.media_key("https://cdn.example/v/t51/12345_0_n.jpg?oh=a"),
            post_archive.media_key("https://cdn.example/v/t51/12345_1_n.jpg?oh=a"),
        )


class ActivationBoundaryTests(PostArchiveTests):
    def test_posts_published_before_activation_are_never_imported(self):
        checkpoint = {"activated_at": "2026-09-10T00:00:00+00:00"}
        result = self.scan([
            FakePost("300", "2026-09-11T09:00:00+00:00"),
            FakePost("200", "2026-09-09T09:00:00+00:00"),
        ], checkpoint)
        self.assertEqual(["300"], result.media_ids)
        self.assertFalse((self.root / "posts" / "acm.ucr" / "200.json").exists())

    def test_an_activated_account_never_looks_behind_its_activation(self):
        # The single invariant the whole feature rests on: whatever the
        # checkpoint says, a scan cannot reach back past activation.
        for through in (None, "2026-09-11T00:00:00+00:00", "2020-01-01T00:00:00+00:00"):
            checkpoint = {"activated_at": "2026-09-10T00:00:00+00:00"}
            if through:
                checkpoint["scanned_through"] = through
            with self.subTest(scanned_through=through):
                self.assertGreaterEqual(
                    scrape_posts.scan_boundary(checkpoint, instant("2026-09-11T12:00:00+00:00")),
                    instant("2026-09-10T00:00:00+00:00"),
                )

    def test_a_post_published_exactly_at_activation_is_collected(self):
        checkpoint = {"activated_at": "2026-09-10T00:00:00+00:00"}
        result = self.scan([FakePost("250", "2026-09-10T00:00:00+00:00")], checkpoint)
        self.assertEqual(["250"], result.media_ids)

    def test_an_old_post_pinned_above_new_ones_does_not_end_the_scan(self):
        # Instagram renders pinned posts first regardless of age, and
        # `Post.is_pinned` is unreliable — the first entries must not be read
        # as "the feed is now older than the boundary".
        checkpoint = {"activated_at": "2026-09-01T00:00:00+00:00",
                      "scanned_through": "2026-09-10T00:00:00+00:00"}
        result = self.scan([
            FakePost("100", "2026-01-04T09:00:00+00:00"),   # pinned, ancient
            FakePost("101", "2026-01-03T09:00:00+00:00"),   # pinned, ancient
            FakePost("900", "2026-09-11T09:00:00+00:00"),   # genuinely new
            FakePost("899", "2026-09-08T09:00:00+00:00"),   # inside the overlap
            FakePost("500", "2026-02-01T09:00:00+00:00"),   # older than boundary
        ], checkpoint)
        self.assertEqual(["900", "899"], result.media_ids)
        self.assertTrue(result.complete)

    def test_a_pinned_post_inside_the_overlap_is_collected_normally(self):
        # Being in the pinned prefix only stops an entry from ending the scan;
        # it never excludes the entry itself.
        checkpoint = {"activated_at": "2026-09-01T00:00:00+00:00",
                      "scanned_through": "2026-09-11T00:00:00+00:00"}
        result = self.scan([
            FakePost("100", "2026-09-06T09:00:00+00:00"),   # pinned, still in window
            FakePost("900", "2026-09-11T09:00:00+00:00"),
        ], checkpoint)
        self.assertEqual({"100", "900"}, set(result.media_ids))


class OverlapAndCheckpointTests(PostArchiveTests):
    def test_discovery_rewalks_a_seven_day_overlap_bounded_by_activation(self):
        boundary = scrape_posts.scan_boundary(
            {"activated_at": "2026-01-01T00:00:00+00:00",
             "scanned_through": "2026-09-11T00:00:00+00:00"},
            instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertEqual(instant("2026-09-04T00:00:00+00:00"), boundary)

    def test_the_overlap_never_reaches_behind_activation(self):
        boundary = scrape_posts.scan_boundary(
            {"activated_at": "2026-09-09T00:00:00+00:00",
             "scanned_through": "2026-09-11T00:00:00+00:00"},
            instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertEqual(instant("2026-09-09T00:00:00+00:00"), boundary)

    def test_an_interrupted_scan_keeps_its_items_and_retains_the_checkpoint(self):
        def explode():
            yield FakePost("900", "2026-09-11T09:00:00+00:00")
            raise scrape_posts.ConnectionException("page 2 timed out")

        checkpoint = {"activated_at": "2026-09-01T00:00:00+00:00",
                      "scanned_through": "2026-09-10T00:00:00+00:00"}
        profile = SimpleNamespace(get_posts=explode)
        with patch.object(scrape_posts.instaloader.Profile, "from_username", return_value=profile):
            with self.assertRaises(scrape_posts.ConnectionException):
                scrape_posts.scan_account(Mock(), {"handle": "acm.ucr"}, checkpoint,
                                          instant("2026-09-11T12:00:00+00:00"))
        # The item collected before the failure survives on disk...
        self.assertTrue((self.root / "posts" / "acm.ucr" / "900.json").exists())
        # ...and the checkpoint did not advance, so the rest is retried.
        self.assertEqual("2026-09-10T00:00:00+00:00", checkpoint["scanned_through"])

    def test_a_scan_that_stops_early_is_reported_incomplete(self):
        posts = [FakePost(str(900 - n), f"2026-09-{11 - n % 10:02d}T09:00:00+00:00")
                 for n in range(scrape_posts.MAX_POSTS_PER_ACCOUNT + 5)]
        result = self.scan(posts, {"activated_at": "2026-01-01T00:00:00+00:00"})
        self.assertFalse(result.complete)
        self.assertEqual(scrape_posts.MAX_POSTS_PER_ACCOUNT, result.scanned)

    def test_durable_write_failure_prevents_the_checkpoint_from_advancing(self):
        self.remote_writes.side_effect = RuntimeError("supabase unavailable")
        with self.assertRaises(RuntimeError):
            self.scan([FakePost("900", "2026-09-11T09:00:00+00:00")],
                      {"activated_at": "2026-09-01T00:00:00+00:00"})


class RestartRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        patcher = patch.object(scrape_posts, "POST_CHECKPOINTS_FILE",
                               self.root / "post_checkpoints.json")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_lost_local_cache_recovers_activation_instead_of_resetting_it(self):
        original = "2026-06-01T00:00:00+00:00"
        remote = {"acm.ucr": {"handle": "acm.ucr", "activated_at": original,
                              "scanned_through": "2026-09-10T00:00:00+00:00"}}
        claim = Mock(return_value={})
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value=remote), \
             patch.object(scrape_posts, "_claim_remote_activation", claim):
            resolved = scrape_posts.resolve_checkpoints(["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        self.assertEqual(original, resolved["acm.ucr"]["activated_at"])
        # Nothing was re-activated, so no history can re-enter the feed.
        claim.assert_called_once_with([])

    def test_a_new_account_activates_once_and_keeps_the_stored_boundary(self):
        stored = {"acm.ucr": {"activated_at": "2026-09-01T00:00:00+00:00"}}
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value={}), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value=stored):
            resolved = scrape_posts.resolve_checkpoints(["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        # The durable row already held an earlier activation; the claim did not
        # move it, and the run adopts what the store actually has.
        self.assertEqual("2026-09-01T00:00:00+00:00", resolved["acm.ucr"]["activated_at"])

    def test_a_pilot_run_keeps_the_checkpoints_of_accounts_it_did_not_touch(self):
        # `--handle acm.ucr` resolves one account. The file is a keyed store, so
        # the other clubs' activation boundaries have to survive the write —
        # losing one re-admits a back catalogue or silently skips an interval.
        seeded = {
            "acm.ucr": {"activated_at": "2026-06-01T00:00:00+00:00",
                        "scanned_through": "2026-09-10T00:00:00+00:00"},
            "ieee.ucr": {"activated_at": "2026-05-01T00:00:00+00:00",
                         "scanned_through": "2026-09-10T00:00:00+00:00"},
        }
        scrape_posts.write_local_checkpoints(seeded)
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value={}), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value={}):
            resolved = scrape_posts.resolve_checkpoints(
                ["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        # The run itself only carries the account it was asked for.
        self.assertEqual(["acm.ucr"], sorted(resolved))
        self.assertEqual(seeded, scrape_posts.load_local_checkpoints())

    def test_the_resume_point_is_the_older_of_local_and_remote_progress(self):
        scrape_posts.write_local_checkpoints({"acm.ucr": {
            "activated_at": "2026-06-01T00:00:00+00:00",
            "scanned_through": "2026-09-11T00:00:00+00:00"}})
        remote = {"acm.ucr": {"handle": "acm.ucr", "activated_at": "2026-06-01T00:00:00+00:00",
                              "scanned_through": "2026-09-05T00:00:00+00:00"}}
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value=remote), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value={}):
            resolved = scrape_posts.resolve_checkpoints(["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        self.assertEqual("2026-09-05T00:00:00+00:00", resolved["acm.ucr"]["scanned_through"])


class FakeMirror:
    """The `instagram_posts` reads an archive restore actually makes."""

    def __init__(self, rows):
        self.rows = sorted(rows, key=lambda row: str(row["media_id"]))
        self.ranges: list[tuple[int, int]] = []
        self.id_requests: list[list[str]] = []
        self._selected: list[str] = []
        self._page: list[dict] = []

    def __call__(self):  # stands in for db.client()
        return self

    def table(self, name):
        assert name == "instagram_posts", name
        return self

    def select(self, columns):
        self._selected = [column.strip() for column in columns.split(",")]
        return self

    def order(self, field):
        return self

    def range(self, start, end):
        # PostgREST ranges are inclusive on both ends.
        self.ranges.append((start, end))
        self._page = self.rows[start:end + 1]
        return self

    def in_(self, field, values):
        self.id_requests.append(list(values))
        wanted = {str(value) for value in values}
        self._page = [row for row in self.rows if str(row[field]) in wanted]
        return self

    def execute(self):
        page, self._page = self._page, []
        return SimpleNamespace(data=[
            {column: row.get(column) for column in self._selected} for row in page])


class ArchiveRestoreTests(unittest.TestCase):
    """A lost `data/` directory comes back from the durable mirror."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        patcher = patch.object(post_archive, "POSTS_DIR", self.root / "posts")
        patcher.start()
        self.addCleanup(patcher.stop)

    def mirror_row(self, media_id="700", *, caption="Flyer", handle="acm.ucr",
                   first_seen="2026-09-01T00:00:00+00:00"):
        """One `instagram_posts` row, built by the collector's own serializer."""
        record = scrape_posts.serialize_post(
            FakePost(media_id, "2026-09-02T09:00:00+00:00", caption=caption, owner=handle),
            handle, seen_at=instant("2026-09-02T12:00:00+00:00"))
        return {"media_id": media_id, "handle": handle,
                "first_seen_at": first_seen, "record": record}

    def hydrate(self, client):
        with patch.dict(sys.modules, {"db": SimpleNamespace(client=client)}):
            return post_archive.hydrate_local_posts()

    def test_a_lost_archive_is_restored_from_the_mirror(self):
        mirror = FakeMirror([self.mirror_row("700"),
                             self.mirror_row("800", caption="Bake sale")])
        self.assertEqual(2, self.hydrate(mirror))
        saved = {record["media_id"]: record for record in post_archive.iter_local_posts()}
        self.assertEqual({"700", "800"}, set(saved))
        self.assertEqual("Bake sale", saved["800"]["caption"])
        # The durable first-seen survives: a restored post is not newly found.
        self.assertEqual("2026-09-01T00:00:00+00:00", saved["700"]["first_seen_at"])

    def test_a_restored_post_is_not_rediscovered_as_new(self):
        # The whole point of restoring: the next scan sees the post it already
        # collected, so it costs no OCR, no model call, and no "discovered".
        row = self.mirror_row("700")
        self.hydrate(FakeMirror([row]))
        rescanned = dict(row["record"], fetched_at="2026-09-11T12:00:00+00:00")
        self.assertEqual("unchanged", post_archive.write_post(rescanned))

    def test_a_post_already_on_disk_is_never_overwritten(self):
        # The local file was written before the mirror row it produced, so it is
        # at least as fresh — a stale mirror must not undo a caption correction.
        post_archive.write_post(
            self.mirror_row("700", caption="Study jam is cancelled")["record"])
        mirror = FakeMirror([self.mirror_row("700", caption="Study jam")])
        self.assertEqual(0, self.hydrate(mirror))
        # Nothing was even fetched, so an intact archive costs one request.
        self.assertEqual([], mirror.id_requests)
        saved = next(iter(post_archive.iter_local_posts()))
        self.assertEqual("Study jam is cancelled", saved["caption"])

    def test_a_corrupt_local_file_counts_as_absent_and_is_replaced(self):
        path = post_archive.post_path("acm.ucr", "700")
        path.parent.mkdir(parents=True)
        path.write_text("{ truncated")
        self.assertEqual(1, self.hydrate(FakeMirror([self.mirror_row("700")])))
        self.assertEqual("Flyer", post_archive.read_json(path)["caption"])

    def test_mirrored_identifiers_never_become_paths_outside_the_archive(self):
        for value in ("..", ".", "../../escaped", "a/b", "", None):
            with self.subTest(value=value):
                self.assertEqual("", post_archive._path_token(value))
        rows = [self.mirror_row("../../escaped"), self.mirror_row("700", handle="../..")]
        self.assertEqual(0, self.hydrate(FakeMirror(rows)))
        self.assertFalse((self.root / "posts").exists())

    def test_an_unreadable_mirror_costs_coverage_not_the_run(self):
        for failure in (RuntimeError("supabase unavailable"),
                        SystemExit("Supabase env missing")):
            with self.subTest(failure=type(failure).__name__):
                def explode():
                    raise failure

                self.assertEqual(0, self.hydrate(explode))

    def test_a_mirror_larger_than_one_page_is_walked_completely(self):
        mirror = FakeMirror([self.mirror_row(str(media_id))
                             for media_id in (700, 800, 900)])
        with patch.object(post_archive, "RESTORE_PAGE", 2):
            self.assertEqual(3, self.hydrate(mirror))
        # An inclusive-range off-by-one here would silently skip a post.
        self.assertEqual([(0, 1), (2, 3)], mirror.ranges)
        self.assertEqual(3, len(list(post_archive.iter_local_posts())))


class CollectionRunTests(PostArchiveTests):
    """The collector entrypoint end to end, with Instagram mocked out."""

    def run_main(self, accounts, posts_by_handle, *, refresh=None):
        def profile(_context, handle):
            return SimpleNamespace(get_posts=lambda: iter(posts_by_handle.get(handle, [])))

        loader = Mock()
        with patch.object(scrape_posts.instaloader, "Instaloader", return_value=loader), \
             patch.object(scrape_posts.instaloader.Profile, "from_username", side_effect=profile), \
             patch.object(scrape_posts, "_login"), \
             patch.object(scrape_posts, "_attach_http_error_logger"), \
             patch.object(scrape_posts, "_persist_rotated_session"), \
             patch.object(scrape_posts, "_load_scrape_accounts", return_value=accounts), \
             patch.object(scrape_posts, "_load_remote_checkpoints", return_value={}), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value={}), \
             patch.object(scrape_posts, "_write_remote_checkpoints"), \
             patch.object(scrape_posts, "refresh_candidates", return_value=refresh or {}), \
             patch.object(scrape_posts, "_sleep_between_accounts"), \
             patch.object(scrape_posts, "hydrate_local_posts") as hydrate, \
             patch.object(scrape_posts, "ensure_post_dirs"):
            scrape_posts.main()
        self.hydrated = hydrate

    def test_a_first_run_activates_accounts_and_imports_nothing_older(self):
        accounts = [{"handle": "acm.ucr"}, {"handle": "ieee.ucr"}]
        posts = {
            "acm.ucr": [FakePost("900", "2026-09-11T09:00:00+00:00")],
            "ieee.ucr": [FakePost("800", "2020-01-01T09:00:00+00:00")],
        }
        self.run_main(accounts, posts)
        saved = sorted(path.stem for path in (self.root / "posts").glob("*/*.json"))
        # Activation happens at "now", so nothing published before this run
        # enters the archive — not even a club's whole back catalogue.
        self.assertEqual([], saved)
        checkpoints = scrape_posts.load_local_checkpoints()
        self.assertEqual({"acm.ucr", "ieee.ucr"}, set(checkpoints))
        self.assertTrue(all(entry["activated_at"] for entry in checkpoints.values()))

    def test_collection_restores_the_archive_before_judging_what_is_new(self):
        # Discovery, the refresh pass, and the extraction that follows all read
        # the archive, so the restore has to happen before any of them looks.
        self.run_main([{"handle": "acm.ucr"}], {})
        self.hydrated.assert_called_once_with()

    def test_a_later_run_collects_what_was_published_after_activation(self):
        scrape_posts.write_local_checkpoints({"acm.ucr": {
            "activated_at": "2026-09-01T00:00:00+00:00",
            "scanned_through": "2026-09-10T00:00:00+00:00"}})
        self.run_main([{"handle": "acm.ucr"}],
                      {"acm.ucr": [FakePost("900", "2026-09-11T09:00:00+00:00")]})
        self.assertTrue((self.root / "posts" / "acm.ucr" / "900.json").exists())
        self.assertEqual("complete",
                         scrape_posts.load_local_checkpoints()["acm.ucr"]["last_status"])

    def test_a_rate_limit_stops_collection_and_keeps_every_checkpoint(self):
        scrape_posts.write_local_checkpoints({
            handle: {"activated_at": "2026-09-01T00:00:00+00:00",
                     "scanned_through": "2026-09-10T00:00:00+00:00"}
            for handle in ("acm.ucr", "ieee.ucr")})

        def rate_limited():
            raise scrape_posts.TooManyRequestsException("429 Too Many Requests")

        accounts = [{"handle": "acm.ucr"}, {"handle": "ieee.ucr"}]
        with self.assertRaises(scrape_posts.InstagramPostsBlocked) as raised:
            self.run_main(accounts, {"acm.ucr": _Exploding(rate_limited)})
        self.assertIn("rate limited", str(raised.exception))
        self.assertIn("incomplete", str(raised.exception))
        saved = scrape_posts.load_local_checkpoints()
        # Neither account advanced, so the uncollected interval is retried.
        for handle in ("acm.ucr", "ieee.ucr"):
            self.assertEqual("2026-09-10T00:00:00+00:00", saved[handle]["scanned_through"])

    def test_refreshes_skip_posts_already_fetched_by_discovery(self):
        scrape_posts.write_local_checkpoints({"acm.ucr": {
            "activated_at": "2026-09-01T00:00:00+00:00",
            "scanned_through": "2026-09-10T00:00:00+00:00"}})
        known = {"900": {"media_id": "900", "handle": "acm.ucr", "shortcode": "C900"},
                 "700": {"media_id": "700", "handle": "acm.ucr", "shortcode": "C700"}}
        with patch.object(scrape_posts, "refresh_post") as refresh:
            self.run_main([{"handle": "acm.ucr"}],
                          {"acm.ucr": [FakePost("900", "2026-09-11T09:00:00+00:00")]},
                          refresh=known)
        # 900 came back from discovery this run; only 700 costs a request.
        self.assertEqual(["700"], [call.args[1]["media_id"] for call in refresh.call_args_list])


class _Exploding:
    """A feed whose first page raises, to model a mid-pagination failure."""

    def __init__(self, raise_now):
        self._raise_now = raise_now

    def __iter__(self):
        self._raise_now()
        return iter(())


class RefreshDurabilityTests(PostArchiveTests):
    def test_a_refreshed_post_is_mirrored_durably_not_just_locally(self):
        # A corrected caption that only reached the local archive would be lost
        # on restore, and the stale copy would keep publishing a withdrawn event.
        known = {"media_id": "700", "handle": "acm.ucr", "shortcode": "C700"}
        refreshed = FakePost("700", "2026-09-11T09:00:00+00:00",
                             caption="Study jam is cancelled")
        with patch.object(scrape_posts.instaloader.Post, "from_shortcode", return_value=refreshed):
            scrape_posts.refresh_post(Mock(), known, instant("2026-09-12T12:00:00+00:00"))
        saved = post_archive.read_json(self.root / "posts" / "acm.ucr" / "700.json")
        self.assertEqual("Study jam is cancelled", saved["caption"])
        self.remote_writes.assert_called_once()
        self.assertEqual("Study jam is cancelled",
                         self.remote_writes.call_args.args[0][0]["caption"])


class RefreshEligibilityTests(unittest.TestCase):
    def test_only_posts_backing_an_unfinished_event_stay_eligible(self):
        now = instant("2026-09-11T12:00:00+00:00")
        rows = [{"source_key": "instagram:post:700", "event_ids": ["ig_a"]},
                {"source_key": "instagram:post:800", "event_ids": ["ig_b"]}]
        events = [{"id": "ig_a", "starts_at": "2026-09-20T22:00:00+00:00", "ends_at": None},
                  {"id": "ig_b", "starts_at": "2026-09-01T22:00:00+00:00",
                   "ends_at": "2026-09-02T00:00:00+00:00"}]
        archive = [{"media_id": "700", "handle": "acm.ucr", "shortcode": "C700"},
                   {"media_id": "800", "handle": "acm.ucr", "shortcode": "C800"}]
        client = Mock()
        client.return_value.table.return_value.select.return_value.like.return_value.execute.return_value.data = rows
        with patch.dict(sys.modules, {"db": SimpleNamespace(
                client=client, get_event_rows_by_ids=lambda ids: events)}), \
             patch.object(scrape_posts, "iter_local_posts", return_value=archive):
            eligible = scrape_posts.refresh_candidates(now)
        # The finished event's post is dropped: refreshing it cannot change a
        # listing that is already over.
        self.assertEqual(["700"], sorted(eligible))


class FailureClassificationTests(unittest.TestCase):
    def test_rate_limits_and_challenges_stop_collection(self):
        for exc in (scrape_posts.TooManyRequestsException("429"),
                    scrape_posts.LoginRequiredException("login"),
                    scrape_posts.QueryReturnedForbiddenException("403"),
                    scrape_posts.QueryReturnedBadRequestException("invalid request")):
            with self.subTest(exc=type(exc).__name__):
                self.assertIsNotNone(scrape_posts._classify_failure(exc))

    def test_an_ordinary_connection_error_does_not_stop_collection(self):
        self.assertIsNone(scrape_posts._classify_failure(scrape_posts.ConnectionException("reset")))
        self.assertIsNone(scrape_posts._classify_failure(ValueError("odd payload")))


class SerializationTests(PostArchiveTests):
    def test_carousel_slides_keep_their_order_and_identities(self):
        record = scrape_posts.serialize_post(
            FakePost("700", "2026-09-11T09:00:00+00:00", images=3), "acm.ucr",
            seen_at=instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertEqual([0, 1, 2], [entry["index"] for entry in record["media"]])
        self.assertEqual(["700_0_n", "700_1_n", "700_2_n"],
                         [entry["media_key"] for entry in record["media"]])
        self.assertFalse(record["has_video"])
        self.assertEqual("https://www.instagram.com/p/C700/", record["permalink"])

    def test_a_refreshed_url_alone_is_not_recorded_as_a_change(self):
        post = FakePost("700", "2026-09-11T09:00:00+00:00")
        first = scrape_posts.serialize_post(post, "acm.ucr", seen_at=instant("2026-09-11T12:00:00+00:00"))
        self.assertEqual("new", post_archive.write_post(first))
        later = dict(first, fetched_at="2026-09-12T12:00:00+00:00")
        self.assertEqual("unchanged", post_archive.write_post(later))
        edited = dict(later, caption="Flyer (moved to Tuesday)")
        self.assertEqual("updated", post_archive.write_post(edited))

    def test_a_video_post_is_recorded_as_carrying_video(self):
        record = scrape_posts.serialize_post(
            FakePost("800", "2026-09-11T09:00:00+00:00", video=True), "acm.ucr",
            seen_at=instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertTrue(record["has_video"])
        self.assertTrue(record["media"][0]["is_video"])
        self.assertTrue(record["media"][0]["image_url"])

    def test_a_sidecar_video_keeps_its_cover_frame_url(self):
        record = scrape_posts.serialize_post(
            FakePost("700", "2026-09-11T09:00:00+00:00", images=2, video=True), "acm.ucr",
            seen_at=instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertFalse(record["media"][0]["is_video"])
        self.assertTrue(record["media"][1]["is_video"])
        self.assertTrue(record["media"][1]["image_url"])
        self.assertEqual("700_1_n", record["media"][1]["media_key"])


if __name__ == "__main__":
    unittest.main()
