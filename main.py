import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from io import BytesIO
import requests
import threading
import os

class MP3Editor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.cover_data = None
        self.metadata = {
            "title": "",
            "album": "",
            "artist": ""
        }

    def load_metadata(self):
        # ffprobeを使ってメタデータを取得
        title_result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format_tags=title",
                "-of", "default=nw=1:nk=1", self.file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ).stdout.decode().splitlines()
        # タイトルが設定されていない場合はファイル名を初期設定
        if title_result:
            self.metadata["title"] = title_result[0]
        else:
            self.metadata["title"] = os.path.splitext(os.path.basename(self.file_path))[0]

        # アルバム情報の取得
        album_result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format_tags=album",
                "-of", "default=nw=1:nk=1", self.file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ).stdout.decode().splitlines()

        # アルバム名が設定されていない場合は空文字列に設定
        self.metadata["album"] = album_result[0] if album_result else ""

        # アーティスト情報の取得
        artist_result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format_tags=artist",
                "-of", "default=nw=1:nk=1", self.file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ).stdout.decode().splitlines()

        # アーティスト名が設定されていない場合は空文字列に設定
        self.metadata["artist"] = artist_result[0] if artist_result else ""

        # カバー画像の抽出
        cover_temp_path = "./.temp/temp_cover.jpg"
        # .tempフォルダが存在しない場合は作成
        os.makedirs(os.path.dirname(cover_temp_path), exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-i", self.file_path, "-an", "-vcodec", "copy", cover_temp_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if os.path.exists(cover_temp_path):
            with open(cover_temp_path, "rb") as f:
                self.cover_data = f.read()
            os.remove(cover_temp_path)

    def set_metadata(self, title, album, artist, cover_data):
        self.metadata["title"] = title
        self.metadata["album"] = album
        self.metadata["artist"] = artist
        self.cover_data = cover_data

    def save(self):
        # タイトルの存在チェック
        if not self.metadata['title']:
            messagebox.showwarning("No Title", "Please enter a title before saving.")
            return
        
        output_path = os.path.join(os.path.dirname(self.file_path), f"{self.metadata['title']}.mp3")
        # タイトルを変えない場合、出力ファイル名がすでに存在しffmpegの処理が解決しないため一度.temp.mp3で出力する
        output_path_temp = os.path.join(os.path.dirname(output_path), ".temp.mp3")
        print(f"output_path: {output_path}")
            
        # 一時的なカバー画像ファイルを作成
        cover_temp_path = "./.temp/temp_cover.jpg"
        if self.cover_data is not None and isinstance(self.cover_data, bytes):
            with open(cover_temp_path, 'wb') as cover_file:
                cover_file.write(self.cover_data)
            # ffmpegコマンドを実行してメタデータを設定
            command = [
                'ffmpeg', '-i', self.file_path,
                '-i', cover_temp_path,
                '-map', '0:a', '-map', '1:v',
                '-c', 'copy', '-id3v2_version', '3',
                '-metadata', f"title={self.metadata['title']}",
                '-metadata', f"album={self.metadata['album']}",
                '-metadata', f"artist={self.metadata['artist']}",
                '-disposition:1', 'attached_pic',
                output_path_temp
            ]

        else:
            # ffmpegコマンドを実行してメタデータを設定
            command = [
                'ffmpeg', '-i', self.file_path,
                '-c', 'copy', '-id3v2_version', '3',
                '-metadata', f"title={self.metadata['title']}",
                '-metadata', f"album={self.metadata['album']}",
                '-metadata', f"artist={self.metadata['artist']}",
                output_path_temp
            ]

        print(*command)
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.remove(self.file_path)
        os.rename(output_path_temp, output_path)
        if result.returncode == 0:
            print("Metadata and cover image set successfully.")
            if os.path.exists(cover_temp_path):
                os.remove(cover_temp_path)
        else:
            print("Failed to set metadata.")
            print(result.stderr.decode())

        self.file_path = output_path

class MP3EditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MP3 Metadata Editor")
        self.root.iconbitmap('music.ico')
        self.file_path = ""
        self.mp3_editor = None
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

    def select_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
        print(f"selected file path: {self.file_path}")
        if self.file_path:
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

        # 別スレッドで保存処理を実行
        thread = threading.Thread(target=self.save_in_background)
        thread.start()

    def save_in_background(self):
        self.mp3_editor.save()
        self.root.after(0, self.on_save_complete)

    def on_save_complete(self):
        messagebox.showinfo("Success", "Metadata saved successfully.")

root = tk.Tk()
app = MP3EditorApp(root)
root.mainloop()
