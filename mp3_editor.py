from pathlib import Path
from typing import Optional
import subprocess
import re
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent
TEMP_DIR = SCRIPT_DIR / ".temp"


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)


class MP3Editor:
    def __init__(self, file_path: Optional[Path] = None):
        self.file_path: Optional[Path] = file_path
        self.cover_data: Optional[bytes] = None
        self.metadata = {"title": "", "album": "", "artist": ""}

    def load_metadata(self):
        if not self.file_path:
            return
        # タイトル取得
        title_result = (
            subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format_tags=title",
                    "-of",
                    "default=nw=1:nk=1",
                    str(self.file_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            .stdout.decode()
            .splitlines()
        )
        self.metadata["title"] = title_result[0] if title_result else self.file_path.stem

        # アルバム取得
        album_result = (
            subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format_tags=album",
                    "-of",
                    "default=nw=1:nk=1",
                    str(self.file_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            .stdout.decode()
            .splitlines()
        )
        self.metadata["album"] = album_result[0] if album_result else ""

        # アーティスト取得
        artist_result = (
            subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format_tags=artist",
                    "-of",
                    "default=nw=1:nk=1",
                    str(self.file_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            .stdout.decode()
            .splitlines()
        )
        self.metadata["artist"] = artist_result[0] if artist_result else ""

        # カバー抽出
        temp_dir = TEMP_DIR
        temp_dir.mkdir(exist_ok=True)
        cover_path = temp_dir / "temp_cover.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(self.file_path),
                "-an",
                "-vcodec",
                "copy",
                str(cover_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if cover_path.exists():
            self.cover_data = cover_path.read_bytes()
            cover_path.unlink()

    def set_metadata(self, title: str, album: str, artist: str, cover_data: Optional[bytes]):
        self.metadata["title"] = title
        self.metadata["album"] = album
        self.metadata["artist"] = artist
        self.cover_data = cover_data

    def save(self):
        if not self.file_path:
            raise ValueError("No MP3 file selected.")

        sanitized_title = sanitize_filename(self.metadata["title"])
        output_path = self.file_path.parent / f"{sanitized_title}.mp3"

        temp_dir = TEMP_DIR
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / "temp_output.mp3"
        cover_path = temp_dir / "temp_cover.jpg"

        command = ["ffmpeg", "-y", "-i", str(self.file_path)]  # -y: 上書き許可

        if self.cover_data:
            cover_path.write_bytes(self.cover_data)
            command += [
                "-i",
                str(cover_path),
                "-map",
                "0:a",
                "-map",
                "1:v",
                "-c",
                "copy",
                "-id3v2_version",
                "3",
                "-metadata",
                f"title={self.metadata['title']}",
                "-metadata",
                f"album={self.metadata['album']}",
                "-metadata",
                f"artist={self.metadata['artist']}",
                "-disposition:1",
                "attached_pic",
                str(temp_path),
            ]
        else:
            command += [
                "-c",
                "copy",
                "-id3v2_version",
                "3",
                "-metadata",
                f"title={self.metadata['title']}",
                "-metadata",
                f"album={self.metadata['album']}",
                "-metadata",
                f"artist={self.metadata['artist']}",
                str(temp_path),
            ]

        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
        print("DEBUG: ffmpeg cmd:", " ".join(command))
        print("DEBUG: ffmpeg stderr:", result.stderr)

        if result.returncode != 0:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        # 出力ファイルを安全に移動
        if output_path.exists():
            output_path.unlink()
        shutil.move(str(temp_path), str(output_path))
        self.file_path = output_path

        if cover_path.exists():
            cover_path.unlink()
