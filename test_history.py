import unittest
import tempfile
from pathlib import Path

from history import load_history, add_to_history, MAX_HISTORY_ITEMS


class TestLoadHistory(unittest.TestCase):
    def test_load_history_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            self.assertEqual(load_history(path), [])

    def test_load_history_reads_existing_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            path.write_text('["a.mp3", "b.mp3"]', encoding="utf-8")
            self.assertEqual(load_history(path), ["a.mp3", "b.mp3"])

    def test_load_history_corrupted_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            path.write_text("not valid json", encoding="utf-8")
            self.assertEqual(load_history(path), [])


class TestAddToHistory(unittest.TestCase):
    def test_add_to_history_inserts_new_entry_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            result = add_to_history(Path("a.mp3"), [], path=path)
            self.assertEqual(result, ["a.mp3"])
            self.assertEqual(load_history(path), ["a.mp3"])

    def test_add_to_history_moves_duplicate_to_front(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            history = ["a.mp3", "b.mp3"]
            result = add_to_history(Path("b.mp3"), history, path=path)
            self.assertEqual(result, ["b.mp3", "a.mp3"])

    def test_add_to_history_trims_to_max_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            history = [f"{i}.mp3" for i in range(MAX_HISTORY_ITEMS)]
            result = add_to_history(Path("new.mp3"), history, path=path)
            self.assertEqual(len(result), MAX_HISTORY_ITEMS)
            self.assertEqual(result[0], "new.mp3")

    def test_add_to_history_write_failure_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 親ディレクトリとして使えないパスを渡し、書き込み失敗を誘発する
            path = Path(tmp) / "history.json" / "nested.json"
            try:
                result = add_to_history(Path("a.mp3"), [], path=path)
            except Exception:
                self.fail("add_to_history() raised Exception unexpectedly!")
            self.assertEqual(result, ["a.mp3"])


if __name__ == "__main__":
    unittest.main()
