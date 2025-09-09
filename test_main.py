import unittest
from unittest.mock import patch, MagicMock, Mock
import tkinter as tk
from io import BytesIO
from PIL import Image
from main import MP3EditorApp
from pathlib import Path


def make_dummy_png_bytes():
    """1x1 ピクセルのダミーPNGを返す"""
    img = Image.new("RGB", (1, 1), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestMP3EditorApp(unittest.TestCase):

    def setUp(self):
        # Tkインスタンス作成（withdrawで表示を抑止）
        self.root = tk.Tk()
        self.root.withdraw()
        with patch("main.MP3Editor"):
            self.app = MP3EditorApp(self.root)

    def tearDown(self):
        self.root.destroy()

    @patch("main.threading.Thread")
    @patch("main.filedialog.askopenfilename", return_value="test.mp3")
    @patch("main.MP3Editor")
    def test_select_file(self, mock_editor, mock_fd, mock_thread):
        self.app.select_file()
        self.assertEqual(str(self.app.file_path), "test.mp3")
        mock_editor.assert_called_with(self.app.file_path)
        mock_thread.assert_called_once()

    def test_update_metadata_display_with_cover(self):
        dummy_bytes = make_dummy_png_bytes()
        self.app.mp3_editor.metadata = {"title": "t", "album": "a", "artist": "r"}
        self.app.mp3_editor.cover_data = dummy_bytes

        with patch("main.messagebox.showinfo") as mock_info:
            self.app.update_metadata_display()
            mock_info.assert_called_once()

        self.assertEqual(self.app.title_entry.get(), "t")
        self.assertEqual(self.app.album_entry.get(), "a")
        self.assertEqual(self.app.artist_entry.get(), "r")
        self.assertIsNotNone(self.app.cover_image)

    @patch("main.requests.get")
    def test_download_cover_from_url_success(self, mock_get):
        dummy_bytes = make_dummy_png_bytes()
        mock_response = Mock()
        mock_response.content = dummy_bytes
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        self.app.cover_url_entry.insert(0, "http://example.com/cover.png")
        with patch.object(self.app, "update_cover") as mock_update:
            self.app.download_cover_from_url()
            mock_update.assert_called_once()

    @patch("main.requests.get", side_effect=Exception("fail"))
    @patch("main.messagebox.showerror")
    def test_download_cover_from_url_fail(self, mock_error, mock_get):
        self.app.cover_url_entry.insert(0, "http://bad.url")
        self.app.download_cover_from_url()
        mock_error.assert_called_once()

    @patch("main.messagebox.showwarning")
    def test_save_metadata_without_file(self, mock_warn):
        self.app.file_path = None
        self.app.save_metadata()
        mock_warn.assert_called_once()

    @patch("main.Image.open")
    @patch("main.messagebox.showinfo")
    def test_save_cover_image_success(self, mock_info, mock_open):
        self.app.file_path = Path("dummy.mp3")
        self.app.mp3_editor.metadata = {"album": "testalbum"}
        self.app.cover_data = make_dummy_png_bytes()

        img_mock = MagicMock()
        mock_open.return_value = img_mock

        self.app.save_cover_image()
        img_mock.save.assert_called_once()
        mock_info.assert_called_once()

    @patch("main.messagebox.showwarning")
    def test_save_cover_image_without_cover(self, mock_warn):
        self.app.cover_data = None
        self.app.save_cover_image()
        mock_warn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
