import pytest
import filecheck
import os
import stat
from pathlib import Path


class TestWalkTree:
    def collect(self, tmp_path, **kwargs):
        """Walk a tree and collect all callback paths."""
        results = []
        def cb(path, data):
            results.append(os.path.relpath(path, tmp_path).replace("\\", "/"))
        filecheck.walkTree(str(tmp_path), cb, kwargs.get("recursive", False),
                           kwargs.get("follow_links", False), {},
                           kwargs.get("begin"), kwargs.get("end"))
        return results

    # ── Callbacks ────────────────────────────────────────────────────

    def test_begin_callback_callable(self, tmp_path):
        """beginDirCallback is called and its return becomes data."""
        begin_called = []
        def begin(dn):
            begin_called.append(dn)
            return {"custom": True}
        data = {}
        def cb(_, d):
            pass
        filecheck.walkTree(str(tmp_path), cb, False, False, data, begin)
        assert len(begin_called) == 1

    def test_begin_callback_not_callable(self, tmp_path):
        """beginDirCallback=False is skipped."""
        data = {"initial": True}
        def cb(_, d):
            pass
        filecheck.walkTree(str(tmp_path), cb, False, False, data, False)
        # data should still be {"initial": True}
        assert data == {"initial": True}

    def test_end_callback_callable(self, tmp_path):
        """endDirCallback is called."""
        end_called = []
        def end(dn, data):
            end_called.append(dn)
        filecheck.walkTree(str(tmp_path), lambda p, d: None, False, False, {}, False, end)
        assert len(end_called) == 1

    def test_end_callback_not_callable(self, tmp_path):
        """endDirCallback=False is skipped."""
        filecheck.walkTree(str(tmp_path), lambda p, d: None, False, False, {}, False, False)

    def test_begin_return_becomes_data(self, tmp_path):
        """Return value of beginDirCallback replaces data."""
        (tmp_path / "f.txt").write_text("x")
        data = ["old"]
        def begin(dn):
            return ["new"]
        results_data = []
        def cb(path, d):
            results_data.append(d)
        filecheck.walkTree(str(tmp_path), cb, False, False, data, begin)
        assert results_data[0] == ["new"]

    # ── Ignored entries ──────────────────────────────────────────────

    def test_ignored_file_skipped(self, tmp_path):
        (tmp_path / ".filecheck").write_text("x")
        (tmp_path / "real.txt").write_text("y")
        results = self.collect(tmp_path)
        assert ".filecheck" not in results
        assert "real.txt" in results

    def test_all_ignored(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".DS_Store").write_text("x")
        results = self.collect(tmp_path)
        assert results == []

    # ── lstat failure ────────────────────────────────────────────────

    def test_lstat_failure(self, tmp_path, capsys, monkeypatch):
        (tmp_path / "good.txt").write_text("ok")
        (tmp_path / "bad.txt").write_text("secret")
        bad_path = str(tmp_path / "bad.txt")
        original_lstat = Path.lstat
        def mock_lstat(self):
            if str(self) == bad_path:
                raise PermissionError(f"cannot stat {self}")
            return original_lstat(self)
        monkeypatch.setattr(Path, 'lstat', mock_lstat)
        results = self.collect(tmp_path)
        assert "good.txt" in results
        captured = capsys.readouterr()
        assert "cannot stat" in captured.out

    # ── Symlinks (mocked — avoids platform dependency) ──────────────

    def test_symlink_skipped_when_follow_false(self, tmp_path, monkeypatch):
        """Symlink is skipped when followLink=False (mock Path.lstat)."""
        (tmp_path / "target.txt").write_text("real")
        link_path = str(tmp_path / "link.txt")
        (tmp_path / "link.txt").write_text("dummy")
        original_lstat = Path.lstat
        def mock_lstat(self):
            if str(self) == link_path:
                class MockStat:
                    st_mode = stat.S_IFLNK | 0o777
                return MockStat()
            return original_lstat(self)
        monkeypatch.setattr(Path, 'lstat', mock_lstat)
        results = self.collect(tmp_path, follow_links=False)
        assert "target.txt" in results
        assert "link.txt" not in results

    def test_symlink_with_follow_true_falls_to_unknown(self, tmp_path, monkeypatch, capsys):
        """--follow-links has no effect: lstat still shows symlink, ends as 'Skipping'."""
        (tmp_path / "target.txt").write_text("real")
        link_path = str(tmp_path / "link.txt")
        (tmp_path / "link.txt").write_text("dummy")
        original_lstat = Path.lstat
        def mock_lstat(self):
            if str(self) == link_path:
                class MockStat:
                    st_mode = stat.S_IFLNK | 0o777
                return MockStat()
            return original_lstat(self)
        monkeypatch.setattr(Path, 'lstat', mock_lstat)
        results = self.collect(tmp_path, follow_links=True)
        assert "target.txt" in results
        captured = capsys.readouterr()
        assert "Skipping" in captured.out

    # ── Directory handling ───────────────────────────────────────────

    def test_directory_non_recursive(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "nested.txt").write_text("x")
        results = self.collect(tmp_path, recursive=False)
        assert "sub" in results
        assert "sub/nested.txt" not in results

    def test_directory_recursive(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "nested.txt").write_text("x")
        results = self.collect(tmp_path, recursive=True)
        assert "sub" in results
        assert "sub/nested.txt" in results

    def test_deep_nested_recursive(self, tmp_path):
        path = tmp_path
        for i in range(5):
            path = path / f"lvl{i}"
            path.mkdir()
        (path / f"leaf.txt").write_text("deep")
        results = self.collect(tmp_path, recursive=True)
        assert "lvl0" in results
        assert "lvl0/lvl1/lvl2/lvl3/lvl4/leaf.txt" in results

    def test_directory_callback_called(self, tmp_path):
        """Directories get passed to the file callback too."""
        (tmp_path / "sub").mkdir()
        results = self.collect(tmp_path)
        assert "sub" in results

    # ── Regular files ────────────────────────────────────────────────

    def test_regular_file(self, tmp_path):
        (tmp_path / "file.txt").write_text("content")
        results = self.collect(tmp_path)
        assert "file.txt" in results

    def test_multiple_files(self, tmp_path):
        for name in ["a.txt", "b.txt", "c.txt"]:
            (tmp_path / name).write_text(name)
        results = self.collect(tmp_path)
        assert sorted(results) == ["a.txt", "b.txt", "c.txt"]

    # ── Unknown type ─────────────────────────────────────────────────

    def test_unknown_file_type(self, tmp_path, capsys, monkeypatch):
        """Non-dir, non-reg, non-symlink entries are printed as Skipping."""
        (tmp_path / "regular.txt").write_text("hello")
        special_path = tmp_path / "special_device"
        special_path.write_text("")  # create it so listdir finds it
        special = str(special_path)
        original_lstat = Path.lstat
        def mock_lstat(self):
            if str(self) == special:
                class MockStat:
                    st_mode = stat.S_IFIFO | 0o644
                return MockStat()
            return original_lstat(self)
        monkeypatch.setattr(Path, 'lstat', mock_lstat)
        results = self.collect(tmp_path)
        assert "regular.txt" in results
        captured = capsys.readouterr()
        assert "Skipping" in captured.out
        assert "special_device" in captured.out

    # ── Deep nesting (iterative walk guard) ─────────────────────────

    def test_deep_nested_recursive_iterative(self, tmp_path):
        """The iterative walk visits deeply nested dirs the same as recursive."""
        base = str(tmp_path)
        leaf = os.path.join(base, "a", "b", "c", "d", "e", "f", "g", "leaf.txt")
        os.makedirs(os.path.dirname(leaf), exist_ok=True)
        with open(leaf, "w") as f:
            f.write("deep")
        expected = [
            os.path.join(base, "a"),
            os.path.join(base, "a", "b"),
            os.path.join(base, "a", "b", "c"),
            os.path.join(base, "a", "b", "c", "d"),
            os.path.join(base, "a", "b", "c", "d", "e"),
            os.path.join(base, "a", "b", "c", "d", "e", "f"),
            os.path.join(base, "a", "b", "c", "d", "e", "f", "g"),
            os.path.join(base, "a", "b", "c", "d", "e", "f", "g", "leaf.txt"),
        ]

        results = []
        def cb(p, _):
            results.append(p)

        filecheck.walkTree(base, cb, True, False, {})
        assert results == expected

    # ── iterdir failure ──────────────────────────────────────────────

    def test_iterdir_failure_skips_directory(self, tmp_path, monkeypatch):
        (tmp_path / "f.txt").write_text("x")
        from pathlib import Path
        original_iterdir = Path.iterdir
        def mock_iterdir(self):
            if str(self) == str(tmp_path):
                raise PermissionError("cannot read")
            return original_iterdir(self)
        monkeypatch.setattr(Path, 'iterdir', mock_iterdir)
        results = self.collect(tmp_path)
        assert results == []

    # ── Empty directory ──────────────────────────────────────────────

    def test_empty_directory(self, tmp_path):
        results = self.collect(tmp_path)
        assert results == []
