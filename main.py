import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from io import BytesIO
import requests
import threading
import os
from pathlib import Path
from mp3_editor import MP3Editor


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
        ttk.Button(main_frame, text="Select MP3 File", command=self.select_file).grid(row=0, column=1, pady=5)

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
        ttk.Button(main_frame, text="Save Metadata", command=self.save_metadata).grid(row=8, column=1, pady=10)
        ttk.Button(main_frame, text="Export Cover", command=self.save_cover_image).grid(row=8, column=2, pady=10)

        # ステータスバー
        status_bar = ttk.Label(root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.grid(row=1, column=0, sticky="ew")

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

    def select_file(self):
        file_str = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
        if file_str:  # ファイルが選ばれた場合
            self.file_path = Path(file_str)  # ← str → Path に変換
            self.mp3_editor = MP3Editor(self.file_path)

            # 別スレッドでメタデータを読み込む
            thread = threading.Thread(target=self.load_metadata_in_background)
            thread.start()

    def load_metadata_in_background(self):
        self.mp3_editor.load_metadata()
        self.update_metadata_display()
        self.status_var.set(f"Loaded - {self.file_path}")

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

    def save_metadata(self):
        if not self.file_path:
            messagebox.showwarning("No file selected", "Please select an MP3 file first.")
            return

        self.status_var.set("Saving metadata...")
        title = self.title_entry.get()
        album = self.album_entry.get()
        artist = self.artist_entry.get()
        self.mp3_editor.set_metadata(title, album, artist, self.cover_data)

        # 別スレッドで保存処理
        thread = threading.Thread(target=self._save_metadata_thread)
        thread.start()

    def _save_metadata_thread(self):
        print("DEBUG: save thread started")
        try:
            self.mp3_editor.save()
            print("DEBUG: save finished")
            self.root.after(0, self.on_save_complete)
        except Exception as e:
            print("DEBUG: save failed", e)
            error_msg = str(e)
            self.root.after(0, lambda: self.on_save_fail(error_msg))

    def on_save_complete(self):
        self.status_var.set("Success")
        messagebox.showinfo("Success", "Metadata saved successfully.")

    def on_save_fail(self, error_msg):
        self.status_var.set("Error")
        messagebox.showerror("Failed", "Failed to save metadata .\n" f"{error_msg}")

    def save_cover_image(self):
        if not self.cover_data:
            messagebox.showwarning("No Cover", "No cover image to save.")
            return

        # 優先順位：album → title → "cover"
        base_name = self.mp3_editor.metadata.get("album") or self.mp3_editor.metadata.get("title") or "cover"
        # ファイル名に使用できない文字を削除または置換
        base_name = re.sub(r'[<>:"/\\|?*]', "_", base_name)

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
    root = tk.Tk()
    app = MP3EditorApp(root)
    root.mainloop()
