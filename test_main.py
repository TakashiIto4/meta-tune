import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, Mock
import tkinter as tk
from io import BytesIO
from PIL import Image
from main import MP3EditorApp, check_dependencies
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
        with patch("main.MP3Editor"), patch("main.load_history", return_value=[]):
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

    def test_update_metadata_display_clears_cover_from_previous_file(self):
        # 前のファイルにカバー画像があった状態から、カバー画像のない
        # 別のファイルに切り替えた場合、self.cover_dataが残ってはいけない
        # （残っていると保存時に前のファイルのカバー画像が誤って添付される）。
        dummy_bytes = make_dummy_png_bytes()
        self.app.mp3_editor.metadata = {"title": "t1", "album": "a1", "artist": "r1"}
        self.app.mp3_editor.cover_data = dummy_bytes
        with patch("main.messagebox.showinfo"):
            self.app.update_metadata_display()
        self.assertEqual(self.app.cover_data, dummy_bytes)

        self.app.mp3_editor.metadata = {"title": "t2", "album": "a2", "artist": "r2"}
        self.app.mp3_editor.cover_data = None
        with patch("main.messagebox.showinfo"):
            self.app.update_metadata_display()

        self.assertIsNone(self.app.cover_data)

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

    # --- select_file / load: ボタンdisable・例外処理 ---

    @patch("main.threading.Thread")
    @patch("main.filedialog.askopenfilename", return_value="test.mp3")
    @patch("main.MP3Editor")
    def test_select_file_disables_select_button(self, mock_editor, mock_fd, mock_thread):
        self.app.select_file()
        self.assertEqual(str(self.app.select_button["state"]), "disabled")

    def test_load_metadata_in_background_success(self):
        self.app.mp3_editor = MagicMock()
        with patch.object(self.app.root, "after", side_effect=lambda delay, func: func()):
            with patch.object(self.app, "on_load_complete") as mock_complete:
                self.app.load_metadata_in_background()
                mock_complete.assert_called_once()

    def test_load_metadata_in_background_failure(self):
        self.app.mp3_editor = MagicMock()
        self.app.mp3_editor.load_metadata.side_effect = Exception("boom")
        with patch.object(self.app.root, "after", side_effect=lambda delay, func: func()):
            with patch.object(self.app, "on_load_fail") as mock_fail:
                self.app.load_metadata_in_background()
                mock_fail.assert_called_once_with("boom")

    @patch("main.messagebox.showinfo")
    @patch("main.add_to_history", return_value=["test.mp3"])
    def test_on_load_complete_reenables_button_and_updates_history(self, mock_add_history, mock_info):
        self.app.mp3_editor.metadata = {"title": "t", "album": "a", "artist": "r"}
        self.app.mp3_editor.cover_data = None
        self.app.file_path = Path("test.mp3")
        self.app.select_button.config(state="disabled")
        self.app.on_load_complete()
        self.assertEqual(str(self.app.select_button["state"]), "normal")
        mock_add_history.assert_called_once_with(Path("test.mp3"), [])

    @patch("main.messagebox.showerror")
    def test_on_load_fail_reenables_button(self, mock_error):
        self.app.select_button.config(state="disabled")
        self.app.on_load_fail("boom")
        mock_error.assert_called_once()
        self.assertEqual(str(self.app.select_button["state"]), "normal")

    # --- save_metadata: リネーム確認ダイアログ ---

    @patch("main.threading.Thread")
    @patch("main.messagebox.askyesno", return_value=True)
    def test_save_metadata_confirms_rename_when_title_changes(self, mock_ask, mock_thread):
        self.app.file_path = Path("original.mp3")
        self.app.mp3_editor = MagicMock()
        self.app.title_entry.insert(0, "NewTitle")
        self.app.save_metadata()
        mock_ask.assert_called_once()
        _, kwargs = mock_thread.call_args
        self.assertEqual(kwargs["args"], (Path("original.mp3"), True))
        self.assertEqual(str(self.app.save_button["state"]), "disabled")
        self.assertEqual(str(self.app.export_button["state"]), "disabled")

    @patch("main.threading.Thread")
    @patch("main.messagebox.askyesno", return_value=False)
    def test_save_metadata_keeps_original_when_rename_declined(self, mock_ask, mock_thread):
        self.app.file_path = Path("original.mp3")
        self.app.mp3_editor = MagicMock()
        self.app.title_entry.insert(0, "NewTitle")
        self.app.save_metadata()
        _, kwargs = mock_thread.call_args
        self.assertEqual(kwargs["args"], (Path("original.mp3"), False))

    @patch("main.threading.Thread")
    @patch("main.messagebox.askyesno")
    def test_save_metadata_no_confirm_when_title_unchanged(self, mock_ask, mock_thread):
        self.app.file_path = Path("original.mp3")
        self.app.mp3_editor = MagicMock()
        self.app.title_entry.insert(0, "original")
        self.app.save_metadata()
        mock_ask.assert_not_called()

    # --- _save_metadata_thread: 元ファイルの削除 ---

    def test_save_metadata_thread_deletes_original_when_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_path = Path(tmp) / "original.mp3"
            original_path.write_bytes(b"data")
            new_path = Path(tmp) / "new.mp3"
            new_path.write_bytes(b"data2")

            self.app.mp3_editor = MagicMock()
            self.app.mp3_editor.file_path = new_path
            with patch.object(self.app.root, "after", side_effect=lambda delay, func: func()):
                with patch.object(self.app, "on_save_complete") as mock_complete:
                    self.app._save_metadata_thread(original_path, True)

            self.assertFalse(original_path.exists())
            mock_complete.assert_called_once_with(None)

    def test_save_metadata_thread_keeps_original_when_not_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_path = Path(tmp) / "original.mp3"
            original_path.write_bytes(b"data")
            new_path = Path(tmp) / "new.mp3"
            new_path.write_bytes(b"data2")

            self.app.mp3_editor = MagicMock()
            self.app.mp3_editor.file_path = new_path
            with patch.object(self.app.root, "after", side_effect=lambda delay, func: func()):
                with patch.object(self.app, "on_save_complete") as mock_complete:
                    self.app._save_metadata_thread(original_path, False)

            self.assertTrue(original_path.exists())
            mock_complete.assert_called_once_with(None)

    def test_save_metadata_thread_reports_failure(self):
        self.app.mp3_editor = MagicMock()
        self.app.mp3_editor.save.side_effect = RuntimeError("ffmpeg failed")
        with patch.object(self.app.root, "after", side_effect=lambda delay, func: func()):
            with patch.object(self.app, "on_save_fail") as mock_fail:
                self.app._save_metadata_thread(Path("original.mp3"), True)
        mock_fail.assert_called_once_with("ffmpeg failed")

    @patch("main.messagebox.showinfo")
    @patch("main.add_to_history", return_value=["new.mp3"])
    def test_on_save_complete_success(self, mock_add_history, mock_info):
        self.app.mp3_editor = MagicMock()
        self.app.mp3_editor.file_path = Path("new.mp3")
        self.app.save_button.config(state="disabled")
        self.app.export_button.config(state="disabled")
        self.app.on_save_complete()
        self.assertEqual(self.app.file_path, Path("new.mp3"))
        self.assertEqual(str(self.app.save_button["state"]), "normal")
        self.assertEqual(str(self.app.export_button["state"]), "normal")
        mock_info.assert_called_once()
        mock_add_history.assert_called_once_with(Path("new.mp3"), [])

    @patch("main.messagebox.showwarning")
    @patch("main.add_to_history", return_value=[])
    def test_on_save_complete_with_delete_warning(self, mock_add_history, mock_warn):
        self.app.mp3_editor = MagicMock()
        self.app.mp3_editor.file_path = Path("new.mp3")
        self.app.on_save_complete(delete_warning="permission denied")
        mock_warn.assert_called_once()

    @patch("main.messagebox.showerror")
    def test_on_save_fail_reenables_buttons(self, mock_error):
        self.app.save_button.config(state="disabled")
        self.app.export_button.config(state="disabled")
        self.app.on_save_fail("boom")
        mock_error.assert_called_once()
        self.assertEqual(str(self.app.save_button["state"]), "normal")
        self.assertEqual(str(self.app.export_button["state"]), "normal")

    # --- 進捗バー ---

    def test_start_and_stop_progress(self):
        # rootをwithdrawしているためwinfo_ismapped()は常にFalseになる。
        # grid_info()の有無でgrid配置されているかどうかを判定する。
        self.app._start_progress()
        self.assertNotEqual(self.app.progress.grid_info(), {})
        self.app._stop_progress()
        self.assertEqual(self.app.progress.grid_info(), {})

    # --- ドラッグ&ドロップ ---

    def test_on_drop_file_valid_mp3(self):
        with patch.object(self.app, "_load_mp3") as mock_load:
            event = SimpleNamespace(data="C:/music/song.mp3")
            self.app.on_drop_file(event)
            mock_load.assert_called_once_with(Path("C:/music/song.mp3"))

    @patch("main.messagebox.showwarning")
    def test_on_drop_file_invalid_extension(self, mock_warn):
        with patch.object(self.app, "_load_mp3") as mock_load:
            event = SimpleNamespace(data="C:/music/song.txt")
            self.app.on_drop_file(event)
            mock_warn.assert_called_once()
            mock_load.assert_not_called()

    def test_on_drop_cover_valid_image(self):
        with patch.object(self.app, "update_cover") as mock_update:
            event = SimpleNamespace(data="C:/images/cover.png")
            self.app.on_drop_cover(event)
            mock_update.assert_called_once_with(str(Path("C:/images/cover.png")))

    @patch("main.messagebox.showwarning")
    def test_on_drop_cover_invalid_extension(self, mock_warn):
        with patch.object(self.app, "update_cover") as mock_update:
            event = SimpleNamespace(data="C:/images/cover.gif")
            self.app.on_drop_cover(event)
            mock_warn.assert_called_once()
            mock_update.assert_not_called()

    # --- 最近使ったファイル履歴 ---

    def test_refresh_recent_menu_populates_items(self):
        self.app.recent_files = ["a.mp3", "b.mp3"]
        self.app._refresh_recent_menu()
        self.assertEqual(self.app.recent_menu.index("end"), 1)

    def test_refresh_recent_menu_empty_shows_placeholder(self):
        self.app.recent_files = []
        self.app._refresh_recent_menu()
        self.assertEqual(self.app.recent_menu.entrycget(0, "state"), "disabled")

    @patch("main.messagebox.showwarning")
    def test_open_recent_missing_file_removes_from_history(self, mock_warn):
        self.app.recent_files = ["missing.mp3"]
        with patch.object(self.app, "_load_mp3") as mock_load:
            self.app._open_recent("missing.mp3")
            mock_warn.assert_called_once()
            mock_load.assert_not_called()
            self.assertNotIn("missing.mp3", self.app.recent_files)

    def test_open_recent_existing_file_loads_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "song.mp3"
            path.write_bytes(b"data")
            with patch.object(self.app, "_load_mp3") as mock_load:
                self.app._open_recent(str(path))
                mock_load.assert_called_once_with(path)

    @patch("main.add_to_history", return_value=["x.mp3"])
    def test_add_to_history_refreshes_menu(self, mock_add):
        self.app._add_to_history(Path("x.mp3"))
        self.assertEqual(self.app.recent_files, ["x.mp3"])


class TestCheckDependencies(unittest.TestCase):
    @patch("main.shutil.which")
    def test_all_present(self, mock_which):
        mock_which.return_value = "/usr/bin/tool"
        self.assertEqual(check_dependencies(), [])

    @patch("main.shutil.which")
    def test_some_missing(self, mock_which):
        mock_which.side_effect = lambda name: None if name == "ffprobe" else "/usr/bin/ffmpeg"
        self.assertEqual(check_dependencies(), ["ffprobe"])


if __name__ == "__main__":
    unittest.main()
