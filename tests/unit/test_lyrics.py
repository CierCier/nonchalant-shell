import unittest
from unittest.mock import patch

from scripts import lyrics


class LyricsTests(unittest.TestCase):
    def test_youtube_artist_title_overrides_the_upload_channel(self):
        self.assertEqual(lyrics.clean(
            "EllaLangleyVEVO", "Ella Langley - Choosin' Texas (Official Video)",
            "https://www.youtube.com/watch?v=nUsrYVxrDwI",
        ), ("Ella Langley", "Choosin' Texas"))

    def test_youtube_label_is_not_treated_as_the_artist(self):
        self.assertEqual(lyrics.clean(
            "T-Series", '"Kudi Gujarat Di" Song | Sweetiee Weds NRI | Cast',
            "https://www.youtube.com/watch?v=example",
        ), ("", "Kudi Gujarat Di"))

    def test_song_is_preserved_when_it_is_part_of_the_actual_title(self):
        self.assertEqual(lyrics.clean(
            "EltonJohnVEVO", "Elton John - Your Song (Official Music Video)",
            "https://www.youtube.com/watch?v=example",
        ), ("Elton John", "Your Song"))

    def test_topic_channels_keep_the_performer_without_a_title_prefix(self):
        self.assertEqual(lyrics.clean(
            "Ella Langley - Topic", "Choosin' Texas", "https://music.youtube.com/watch?v=example",
        ), ("Ella Langley", "Choosin' Texas"))

    def test_native_metadata_and_non_youtube_pages_keep_the_artist(self):
        for url in ("", "https://youtube.com.example.org/watch?v=example"):
            self.assertEqual(lyrics.clean("Artist", "Home - Live", url), ("Artist", "Home - Live"))

    def test_youtube_prefers_the_video_recording_over_album_timestamps(self):
        album = {
            "trackName": "Choosin' Texas", "artistName": "Ella Langley", "duration": 232,
            "syncedLyrics": "[00:01]Album words",
        }
        video = {**album, "duration": 422, "syncedLyrics": "[00:12]Video words"}
        with patch.object(lyrics, "ask", side_effect=[None, [album, video]]):
            result = lyrics.lookup("Ella Langley", "Choosin' Texas", "", 421, video=True)
        self.assertEqual(result["syncedLyrics"], "[00:12]Video words")

    def test_different_video_length_falls_back_to_words_without_wrong_timestamps(self):
        song = {
            "trackName": "Kudi Gujarat Di (From Sweetiee Weds Nri)",
            "artistName": "Jasbir Jassi", "duration": 222,
            "syncedLyrics": "[00:01]First\n[00:02]Last",
        }
        with patch.object(lyrics, "ask", return_value=[song]):
            result = lyrics.parse(lyrics.lookup("", "Kudi Gujarat Di", "", 140, video=True))
        self.assertFalse(result["synced"])
        self.assertEqual([line["text"] for line in result["lines"]], ["First", "Last"])

    def test_unknown_channel_does_not_choose_between_equally_matching_artists(self):
        first = {
            "trackName": "Home", "artistName": "First Artist", "duration": 200,
            "syncedLyrics": "[00:01]First words",
        }
        second = {**first, "artistName": "Second Artist"}
        with patch.object(lyrics, "ask", return_value=[first, second]):
            self.assertIsNone(lyrics.lookup("", "Home", "", 200, video=True))

    def test_native_lookup_still_rejects_a_different_recording_duration(self):
        song = {
            "trackName": "Home", "artistName": "Artist", "duration": 300,
            "syncedLyrics": "[00:01]Wrong recording",
        }
        with patch.object(lyrics, "ask", side_effect=[None, [song], [song]]):
            self.assertIsNone(lyrics.lookup("Artist", "Home", "", 200))

    def test_exact_recording_beats_other_artists_and_live_versions(self):
        original = {
            "trackName": "Home", "artistName": "The Original", "duration": 200,
            "plainLyrics": "The original words",
        }
        other_artist = {
            "trackName": "Home", "artistName": "Another Artist", "duration": 200,
            "syncedLyrics": "[00:01]Another artist's words",
        }
        live_version = {
            "trackName": "Home Live", "artistName": "The Original", "duration": 202,
            "syncedLyrics": "[00:01]The live version's words",
        }
        with patch.object(lyrics, "ask", side_effect=[original, [other_artist, live_version], []]):
            result = lyrics.lookup("The Original", "Home", "Album", 200)
        self.assertEqual(result["plainLyrics"], "The original words")

    def test_unrelated_timed_hit_does_not_stop_the_remaining_search(self):
        other_artist = {
            "trackName": "Home", "artistName": "Another Artist", "duration": 200,
            "syncedLyrics": "[00:01]Wrong words",
        }
        original = {
            "trackName": "Home", "artistName": "The Original", "duration": 200,
            "syncedLyrics": "[00:01]Right words",
        }
        with patch.object(lyrics, "ask", side_effect=[None, [other_artist], [original]]):
            result = lyrics.lookup("The Original", "Home", "Album", 200)
        self.assertEqual(result["syncedLyrics"], "[00:01]Right words")

    def test_unsearchable_title_does_not_match_arbitrary_results(self):
        with patch.object(lyrics, "ask") as ask:
            result = lyrics.lookup("The Original", "!!!", "Album", 200)
        self.assertIsNone(result)
        ask.assert_not_called()

    def test_multiple_timestamps_are_sorted_and_silent_lines_preserved(self):
        result = lyrics.parse({
            "syncedLyrics": "[00:20.00][00:40.50]Later\n[00:05.25]Earlier\n[00:10.00]",
        })
        self.assertEqual(result["lines"], [
            {"t": 5.25, "text": "Earlier"},
            {"t": 10.0, "text": ""},
            {"t": 20.0, "text": "Later"},
            {"t": 40.5, "text": "Later"},
        ])
        self.assertTrue(result["synced"])

    def test_plain_lyrics_keep_stanza_breaks_when_timed_text_has_no_timestamps(self):
        result = lyrics.parse({"syncedLyrics": "[ar:Artist]", "plainLyrics": "First\n\nLast"})
        self.assertEqual(result["lines"], [
            {"t": -1, "text": "First"}, {"t": -1, "text": ""}, {"t": -1, "text": "Last"},
        ])
        self.assertFalse(result["synced"])

    def test_instrumental_track_has_no_lyric_lines(self):
        self.assertEqual(lyrics.parse({"instrumental": True, "plainLyrics": "Ignored"}), {
            "available": True, "synced": False, "instrumental": True, "lines": [],
        })


if __name__ == "__main__":
    unittest.main()
