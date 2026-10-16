"""Recording duration must come from matching, finite video metadata."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "media_duration", Path(__file__).resolve().parents[2] / "scripts/media_duration.py"
)
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)
VIDEO = "fasttrack01"


class MediaDurationTests(unittest.TestCase):
    def test_only_the_requested_recording_has_a_duration(self):
        self.assertEqual(media.verified({"id": VIDEO, "duration": 1536}, VIDEO)["duration"], 1536)
        self.assertIn("error", media.verified({"id": "slowtrack01", "duration": 1536}, VIDEO))
        for value in (None, 0, -1, True, "1536", float("inf"), float("nan")):
            with self.subTest(value=value):
                self.assertIn("error", media.verified({"id": VIDEO, "duration": value}, VIDEO))

    def test_current_and_upcoming_streams_have_no_finite_duration(self):
        for flags in ({"is_live": True}, {"live_status": "is_upcoming"}, {"live_status": "is_live"}):
            result = media.verified({"id": VIDEO, "duration": 1536, **flags}, VIDEO)
            self.assertEqual(result, {"id": VIDEO, "duration": 0, "live": True})
        self.assertEqual(media.verified({"id": VIDEO, "duration": 1536, "live_status": "was_live"}, VIDEO)["duration"], 1536)

    def test_cached_duration_survives_an_offline_lookup(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_STATE_HOME": directory}):
            cached = Path(directory) / f"nonchalant/media-duration/{VIDEO}.json"
            cached.parent.mkdir(parents=True)
            cached.write_text(json.dumps({"id": VIDEO, "duration": 333, "fetched_at": time.time()}))
            with patch.object(media, "extract", side_effect=AssertionError("A verified cached recording must not need network")):
                self.assertEqual(media.duration(VIDEO)["duration"], 333)

    def test_expired_and_invalid_caches_require_fresh_metadata(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_STATE_HOME": directory}):
            cached = Path(directory) / f"nonchalant/media-duration/{VIDEO}.json"
            cached.parent.mkdir(parents=True)
            for entry in ({"id": VIDEO, "duration": 111, "fetched_at": time.time() - 86401},
                          {"id": "slowtrack01", "duration": 111, "fetched_at": time.time()},
                          {"id": VIDEO, "duration": -1, "fetched_at": time.time()}):
                cached.write_text(json.dumps(entry))
                with patch.object(media, "extract", return_value={"id": VIDEO, "duration": 333, "live": False}) as lookup:
                    self.assertEqual(media.duration(VIDEO)["duration"], 333)
                    lookup.assert_called_once_with(VIDEO)
                self.assertEqual(json.loads(cached.read_text())["duration"], 333)

    def test_invalid_ids_and_missing_dependencies_do_not_guess(self):
        with patch.object(media, "extract") as lookup:
            for value in ("", "../fasttrack01", VIDEO + "?token=private", "https://youtube.com"):
                self.assertIn("error", media.duration(value))
            lookup.assert_not_called()
        with patch.object(media.shutil, "which", return_value=None):
            self.assertEqual(media.extract(VIDEO)["error"], "yt_dlp_missing")
