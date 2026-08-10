import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from io import BytesIO
import requests
import threading
import os
import shutil
import sys
from pathlib import Path
from mp3_editor import MP3Editor, sanitize_filename
from history import load_history, add_to_history

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False


def check_dependencies() -> list[str]:
    missing = []
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            missing.append(tool)
    return missing


class MP3EditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MetaTune")
        script_dir = Path(__file__).resolve().parent
        icon_path = os.path.join(script_dir, "music.ico")
        self.root.iconbitmap(icon_path)
        self.file_path: Path | None = None
        self.mp3_editor = MP3Editor()
        self.cover_data: bytes | None = None
        self.status_var = tk.StringVar(value="Ready")
        self.recent_files: list[str] = load_history()

        # メインフレーム
        main_frame = ttk.Frame(root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")

        # ウィンドウ全体がリサイズ可能になるよう設定
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        # フレーム内の列ごとのリサイズ設定
        main_frame.columnconfigure(0, weight=0)  # ラベル列は固定
        main_frame.columnconfigure(1, weight=1)  # 入力欄列が伸縮する

        # ファイル選択
        self.select_button = ttk.Button(main_frame, text="Select MP3 File", command=self.select_file)
        self.select_button.grid(row=0, column=1, pady=5)

        # メタデータ入力
        self._add_labeled_entry(main_frame, "Title:", 1)
        self._add_labeled_entry(main_frame, "Album:", 2)
        self._add_labeled_entry(main_frame, "Artist:", 3)

        # カバー画像
        self.cover_label = ttk.Label(main_frame, text="No Cover Image", relief="solid", width=50, anchor="center")
        self.cover_label.grid(row=4, column=1, pady=5)

        # 画像操作
        ttk.Button(main_frame, text="Select Local Image", command=self.select_cover_local).grid(row=5, column=1, pady=5)
        ttk.Label(main_frame, text="Cover URL:").grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.cover_url_entry = ttk.Entry(main_frame, width=50)
        self.cover_url_entry.grid(row=6, column=1, sticky="ew", pady=5)
        ttk.Button(main_frame, text="Download from URL", command=self.download_cover_from_url).grid(
            row=6, column=2, pady=5
        )

        # メタデータ保存
        self.save_button = ttk.Button(main_frame, text="Save Metadata", command=self.save_metadata)
        self.save_button.grid(row=8, column=1, pady=10)
        self.export_button = ttk.Button(main_frame, text="Export Cover", command=self.save_cover_image)
        self.export_button.grid(row=8, column=2, pady=10)

        # ステータスバー
        status_bar = ttk.Label(root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.grid(row=1, column=0, sticky="ew")

        # 進捗バー（処理中のみ表示）
        self.progress = ttk.Progressbar(root, mode="indeterminate")

        self._build_menu()
        self._setup_drag_and_drop()

    def _add_labeled_entry(self, parent, label, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        entry = ttk.Entry(parent, width=50)
        entry.grid(row=row, column=1, sticky="ew", pady=5)
        if "Title" in label:
            self.title_entry = entry
        elif "Album" in label:
            self.album_entry = entry
        elif "Artist" in label:
            self.artist_entry = entry

    # --- 進捗バー ---

    def _start_progress(self):
        self.progress.grid(row=2, column=0, sticky="ew")
        self.progress.start(10)

    def _stop_progress(self):
        self.progress.stop()
        self.progress.grid_remove()

    # --- メニュー / 最近使ったファイル ---

    def _build_menu(self):
        self.menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open Recent", menu=self.recent_menu)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=self.menu_bar)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        self.recent_menu.delete(0, tk.END)
        if not self.recent_files:
            self.recent_menu.add_command(label="(履歴なし)", state="disabled")
            return
        for path_str in self.recent_files:
            self.recent_menu.add_command(label=path_str, command=lambda p=path_str: self._open_recent(p))

    def _open_recent(self, path_str: str):
        path = Path(path_str)
        if not path.exists():
            messagebox.showwarning("File Not Found", f"ファイルが見つかりません:\n{path_str}")
            self.recent_files = [p for p in self.recent_files if p != path_str]
            self._refresh_recent_menu()
            return
        self._load_mp3(path)

    def _add_to_history(self, path: Path):
        self.recent_files = add_to_history(path, self.recent_files)
        self._refresh_recent_menu()

    # --- ドラッグ&ドロップ ---

    def _setup_drag_and_drop(self):
        if not hasattr(self.root, "drop_target_register"):
            return
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self.on_drop_file)
        self.cover_label.drop_target_register(DND_FILES)
        self.cover_label.dnd_bind("<<Drop>>", self.on_drop_cover)

    def on_drop_file(self, event):
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return
        path = Path(paths[0])
        if path.suffix.lower() != ".mp3":
            messagebox.showwarning("Invalid File", "MP3ファイルをドロップしてください。")
            return
        self._load_mp3(path)

    def on_drop_cover(self, event):
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return
        path = Path(paths[0])
        if path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            messagebox.showwarning("Invalid Image", "画像ファイル(.jpg/.jpeg/.png)をドロップしてください。")
            return
        self.update_cover(str(path))

    # --- ファイル読み込み ---

    def select_file(self):
        file_str = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
        if file_str:  # ファイルが選ばれた場合
            self._load_mp3(Path(file_str))

    def _load_mp3(self, path: Path):
        self.file_path = path
        self.mp3_editor = MP3Editor(self.file_path)
        self.select_button.config(state="disabled")
        self.status_var.set("Loading metadata...")
        self._start_progress()

        thread = threading.Thread(target=self.load_metadata_in_background, daemon=True)
        thread.start()

    def load_metadata_in_background(self):
        try:
            self.mp3_editor.load_metadata()
            self.root.after(0, self.on_load_complete)
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.on_load_fail(error_msg))

    def on_load_complete(self):
        self.update_metadata_display()
        self.status_var.set(f"Loaded - {self.file_path}")
        self.select_button.config(state="normal")
        self._stop_progress()
        self._add_to_history(self.file_path)

    def on_load_fail(self, error_msg):
        self.status_var.set("Error")
        self.select_button.config(state="normal")
        self._stop_progress()
        messagebox.showerror("Failed to load", f"メタデータの読み込みに失敗しました。\n{error_msg}")

    def update_metadata_display(self):
        title = self.mp3_editor.metadata["title"]
        album = self.mp3_editor.metadata["album"]
        artist = self.mp3_editor.metadata["artist"]
        cover_data = self.mp3_editor.cover_data

        # テキストボックスに情報を表示
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, title)
        self.album_entry.delete(0, tk.END)
        self.album_entry.insert(0, album)
        self.artist_entry.delete(0, tk.END)
        self.artist_entry.insert(0, artist)

        # カバー画像を表示
        if cover_data:
            original_image = Image.open(BytesIO(cover_data))
            self.resize_display_cover(original_image)
            self.cover_data = cover_data
        else:
            self.cover_image = None
            self.cover_data = None
            self.cover_label.config(image="", text="No Cover Image")
        messagebox.showinfo("File Selected", f"Selected: {self.file_path}")

    def resize_display_cover(self, original_image):
        # 表示画像の最大サイズを512pxに設定
        max_size = 512
        if max(original_image.size) > max_size:
            # リサイズ
            display_image = original_image.copy()  # オリジナルを保持
            display_image.thumbnail((max_size, max_size), Image.LANCZOS)
        else:
            display_image = original_image
        # 表示画像設定
        self.cover_image = ImageTk.PhotoImage(display_image)
        self.cover_label.config(image=self.cover_image, text="")

    def select_cover_local(self):
        image_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if image_path:
            self.update_cover(image_path)

    def download_cover_from_url(self):
        url = self.cover_url_entry.get()
        try:
            response = requests.get(url)
            response.raise_for_status()
            self.update_cover(BytesIO(response.content))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download image: {e}")

    def update_cover(self, image_source):
        original_image = Image.open(image_source)
        self.resize_display_cover(original_image)
        if isinstance(image_source, BytesIO):
            self.cover_data = image_source.getvalue()  # 元の画像データをバイト形式で保持
        else:
            with open(image_source, "rb") as img_file:
                self.cover_data = img_file.read()

    # --- 保存 ---

    def save_metadata(self):
        if not self.file_path:
            messagebox.showwarning("No file selected", "Please select an MP3 file first.")
            return

        title = self.title_entry.get()
        album = self.album_entry.get()
        artist = self.artist_entry.get()

        delete_original = False
        sanitized_new_title = sanitize_filename(title)
        if sanitized_new_title != self.file_path.stem:
            delete_original = messagebox.askyesno(
                "Confirm Rename",
                f"タイトルが変更されています。\n元のファイル「{self.file_path.name}」を削除しますか？",
            )

        self.mp3_editor.set_metadata(title, album, artist, self.cover_data)
        self.status_var.set("Saving metadata...")
        self.save_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self._start_progress()

        original_path = self.file_path
        thread = threading.Thread(
            target=self._save_metadata_thread, args=(original_path, delete_original), daemon=True
        )
        thread.start()

    def _save_metadata_thread(self, original_path, delete_original):
        try:
            self.mp3_editor.save()
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.on_save_fail(error_msg))
            return

        delete_warning = None
        if delete_original and self.mp3_editor.file_path != original_path:
            try:
                original_path.unlink()
            except OSError as e:
                delete_warning = str(e)

        self.root.after(0, lambda: self.on_save_complete(delete_warning))

    def on_save_complete(self, delete_warning=None):
        self.file_path = self.mp3_editor.file_path
        self.status_var.set("Success")
        self.save_button.config(state="normal")
        self.export_button.config(state="normal")
        self._stop_progress()
        if delete_warning:
            messagebox.showwarning(
                "Partial Success",
                f"メタデータは保存されましたが、元ファイルの削除に失敗しました。\n{delete_warning}",
            )
        else:
            messagebox.showinfo("Success", "Metadata saved successfully.")
        self._add_to_history(self.file_path)

    def on_save_fail(self, error_msg):
        self.status_var.set("Error")
        self.save_button.config(state="normal")
        self.export_button.config(state="normal")
        self._stop_progress()
        messagebox.showerror("Failed", "Failed to save metadata .\n" f"{error_msg}")

    def save_cover_image(self):
        if not self.cover_data:
            messagebox.showwarning("No Cover", "No cover image to save.")
            return

        # 優先順位：album → title → "cover"
        base_name = self.mp3_editor.metadata.get("album") or self.mp3_editor.metadata.get("title") or "cover"
        base_name = sanitize_filename(base_name)

        # 保存先ディレクトリ（MP3ファイルと同じ場所）
        save_dir = os.path.dirname(self.file_path) if self.file_path else "."
        save_path = os.path.join(save_dir, f"{base_name}.png")

        try:
            image = Image.open(BytesIO(self.cover_data))
            image.save(save_path, format="PNG")
            messagebox.showinfo("Success", f"Cover image saved as:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save image: {e}")


if __name__ == "__main__":
    missing = check_dependencies()
    if missing:
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror(
            "Missing Dependency",
            f"次のツールが見つかりません: {', '.join(missing)}\n"
            "ffmpeg / ffprobe をインストールし、PATHに追加してから再起動してください。",
        )
        temp_root.destroy()
        sys.exit(1)

    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    app = MP3EditorApp(root)
    root.mainloop()
