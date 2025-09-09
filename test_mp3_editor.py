import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock
from mp3_editor import MP3Editor
from pathlib import Path

class TestMP3EditorLoadMetadata(unittest.TestCase):
    def setUp(self):
        # ダミーのMP3ファイルを作成
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_mp3 = os.path.join(self.temp_dir.name, "test.mp3")
        with open(self.test_mp3, "wb") as f:
            f.write(b"FAKE_MP3_DATA")

        self.editor = MP3Editor(Path(self.test_mp3))

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_load_metadata_with_title(self, mock_run):
        # ffprobe の返り値をモック
        mock_run.return_value = MagicMock(
            stdout=b"Test Title\n",
            stderr=b"",
            returncode=0
        )
        self.editor.load_metadata()
        self.assertEqual(self.editor.metadata["title"], "Test Title")

    @patch("subprocess.run")
    def test_load_metadata_without_title(self, mock_run):
        # タイトルなし
        mock_run.return_value = MagicMock(
            stdout=b"",
            stderr=b"",
            returncode=0
        )
        self.editor.load_metadata()
        # ファイル名がタイトルとして設定される
        self.assertEqual(self.editor.metadata["title"], "test")
    
    @patch("subprocess.run")
    def test_load_metadata_album_and_artist(self, mock_run):
        def side_effect(cmd, stdout, stderr):
            if "format_tags=title" in cmd:
                return MagicMock(stdout=b"Title\n", stderr=b"", returncode=0)
            elif "format_tags=album" in cmd:
                return MagicMock(stdout=b"MyAlbum\n", stderr=b"", returncode=0)
            elif "format_tags=artist" in cmd:
                return MagicMock(stdout=b"MyArtist\n", stderr=b"", returncode=0)
            else:
                return MagicMock(stdout=b"", stderr=b"", returncode=0)

        mock_run.side_effect = side_effect
        self.editor.load_metadata()
        self.assertEqual(self.editor.metadata["title"], "Title")
        self.assertEqual(self.editor.metadata["album"], "MyAlbum")
        self.assertEqual(self.editor.metadata["artist"], "MyArtist")
    
    @patch("subprocess.run")
    def test_load_metadata_with_cover(self, mock_run):
        mock_run.return_value = MagicMock(stdout=b"", stderr=b"", returncode=0)

        cover_path = Path(".temp") / "temp_cover.jpg"
        cover_path.parent.mkdir(exist_ok=True)
        cover_path.write_bytes(b"FAKECOVERDATA")

        self.editor.load_metadata()
        self.assertEqual(self.editor.cover_data, b"FAKECOVERDATA")

    def test_load_metadata_without_file_path(self):
        # file_path が None の場合、load_metadata() は何もしない
        editor = MP3Editor(None)
        try:
            editor.load_metadata()
        except Exception:
            self.fail("load_metadata() raised Exception unexpectedly!")
        # metadata は初期値のまま
        self.assertEqual(editor.metadata["title"], "")
        self.assertEqual(editor.metadata["album"], "")
        self.assertEqual(editor.metadata["artist"], "")
        self.assertIsNone(editor.cover_data)

class TestMP3EditorSetMetadata(unittest.TestCase):
    def setUp(self):
        # ダミーのMP3ファイルを作成
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_mp3 = os.path.join(self.temp_dir.name, "test.mp3")
        with open(self.test_mp3, "wb") as f:
            f.write(b"FAKE_MP3_DATA")

        self.editor = MP3Editor(Path(self.test_mp3))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_set_metadata(self):
        self.editor.set_metadata("Song", "Album", "Artist", b"FAKECOVER")
        self.assertEqual(self.editor.metadata["title"], "Song")
        self.assertEqual(self.editor.metadata["album"], "Album")
        self.assertEqual(self.editor.metadata["artist"], "Artist")
        self.assertEqual(self.editor.cover_data, b"FAKECOVER")

class TestMP3EditorSave(unittest.TestCase):
    def setUp(self):
        # ダミーのMP3ファイルを作成
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_mp3 = os.path.join(self.temp_dir.name, "test.mp3")
        with open(self.test_mp3, "wb") as f:
            f.write(b"FAKE_MP3_DATA")

        self.editor = MP3Editor(Path(self.test_mp3))

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_save_without_cover(self, mock_run):
        # ffmpeg 成功するモック
        mock_run.return_value = MagicMock(returncode=0, stdout=b"5.0", stderr=b"")

        self.editor.set_metadata("NewTitle", "NewAlbum", "NewArtist", None)

        # save() が期待する一時出力ファイルパスを再現
        temp_dir = Path(".temp")
        temp_dir.mkdir(exist_ok=True)
        temp_mp3 = temp_dir / "temp_output.mp3"
        with open(temp_mp3, "wb") as f:
            f.write(b"DUMMY_MP3_DATA")

        try:
            self.editor.save()
        except Exception:
            self.fail("save() raised Exception unexpectedly!")
    
    @patch("subprocess.run")
    def test_save_with_cover(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        fake_cover = b"FAKEJPEGDATA"
        self.editor.set_metadata("SongWithCover", "Album", "Artist", fake_cover)

        temp_dir = Path(".temp")
        temp_dir.mkdir(exist_ok=True)
        temp_mp3 = temp_dir / "temp_output.mp3"
        temp_mp3.write_bytes(b"DUMMY_MP3_DATA")

        self.editor.save()
        self.assertTrue((Path(self.test_mp3).parent / "SongWithCover.mp3").exists())

    @patch("subprocess.run")
    def test_save_fail_ffmpeg(self, mock_run):
        # ffmpeg 失敗するモック
        mock_run.return_value = MagicMock(returncode=1, stderr=b"Some error")
        self.editor.set_metadata("Title", "Album", "Artist", None)
        with self.assertRaises(RuntimeError):
            self.editor.save()
    
    @patch("subprocess.run")
    def test_save_with_cover_ffmpeg_fail(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr=b"cover error")
        self.editor.set_metadata("Title", "Album", "Artist", b"FAKEJPEG")
        with self.assertRaises(RuntimeError):
            self.editor.save()
    
    @patch("subprocess.run")
    def test_save_with_invalid_characters_in_title(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        self.editor.set_metadata('Invalid:/\\Title', 'Album', 'Artist', None)

        temp_dir = Path(".temp")
        temp_dir.mkdir(exist_ok=True)
        temp_mp3 = temp_dir / "temp_output.mp3"
        temp_mp3.write_bytes(b"DUMMY_MP3_DATA")

        self.editor.save()
        self.assertTrue((Path(self.test_mp3).parent / "Invalid___Title.mp3").exists())
    
    def test_save_without_file_path(self):
        self.editor = MP3Editor(None)
        with self.assertRaises(ValueError) as cm:
            self.editor.save()
        self.assertEqual(str(cm.exception), "No MP3 file selected.")


if __name__ == "__main__":
    unittest.main()
