import re
import tkinter as tk
from tkinter import filedialog, messagebox
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
        icon_path = os.path.join(script_dir, 'music.ico')
        self.root.iconbitmap(icon_path)
        self.file_path: Path | None = None
        self.mp3_editor = MP3Editor()
        self.cover_data = None

        input_field_width = 70
        tk.Button(root, text="Select MP3 File", command=self.select_file).pack()
        tk.Label(root, text="Title:").pack()
        self.title_entry = tk.Entry(root, width=input_field_width)
        self.title_entry.pack()
        tk.Label(root, text="Album:").pack()
        self.album_entry = tk.Entry(root, width=input_field_width)
        self.album_entry.pack()
        tk.Label(root, text="Artist:").pack()
        self.artist_entry = tk.Entry(root, width=input_field_width)
        self.artist_entry.pack()
        self.cover_label = tk.Label(root, text="No Cover Image")
        self.cover_label.pack()
        tk.Button(root, text="Select Cover Image (Local)", command=self.select_cover_local).pack()
        tk.Label(root, text="or enter a URL below:").pack()
        self.cover_url_entry = tk.Entry(root, width=input_field_width)
        self.cover_url_entry.pack()
        tk.Button(root, text="Download Cover Image from URL", command=self.download_cover_from_url).pack()
        tk.Button(root, text="Save Metadata", command=self.save_metadata).pack()
        tk.Button(root, text="Save Cover Image as PNG/JPG", command=self.save_cover_image).pack()

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
        self.root.after(0, self.update_app_title)

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
            self.cover_label.config(image='', text="No Cover Image")
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

    def update_app_title(self):
        self.root.title(f"MP3 Metadata Editor - {self.mp3_editor.metadata['title']}")

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
            with open(image_source, 'rb') as img_file:
                self.cover_data = img_file.read()

    def save_metadata(self):
        if not self.file_path:
            messagebox.showwarning("No file selected", "Please select an MP3 file first.")
            return

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
        messagebox.showinfo("Success", "Metadata saved successfully.")

    def on_save_fail(self, error_msg):
        messagebox.showerror(
            "Failed", "Failed to save metadata .\n" \
            f"{error_msg}")
    
    def save_cover_image(self):
        if not self.cover_data:
            messagebox.showwarning("No Cover", "No cover image to save.")
            return

        # 優先順位：album → title → "cover"
        base_name = (
            self.mp3_editor.metadata.get("album")
            or self.mp3_editor.metadata.get("title")
            or "cover"
        )
        # ファイル名に使用できない文字を削除または置換
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)

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
