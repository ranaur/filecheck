import pytest
import filecheck
import os
from tests.conftest import make_info, make_manifest, create_file
from pathlib import Path as Path


# ── checkBegin() ──────────────────────────────────────────────────────

class TestCheckBegin:
    def test_default(self):
        filecheck.options.verbose = False
        data = filecheck.checkBegin("/my/dir")
        assert data["dirName"] == "/my/dir"

    def test_verbose(self, capsys):
        filecheck.options.verbose = True
        data = filecheck.checkBegin("/my/dir")
        assert data["dirName"] == "/my/dir"
        captured = capsys.readouterr()
        assert "/my/dir" in captured.out


# ── checkFile() ───────────────────────────────────────────────────────

class TestCheckFile:
    def test_delegates_to_generate_without_hash(self, tmp_path, monkeypatch):
        f = create_file(tmp_path / "f.txt", b"data")
        data = filecheck.filecheckNew(str(tmp_path))
        filecheck.checkFile(str(f), data)
        assert "f.txt" in data["files"]
        assert data["files"]["f.txt"]["hash"] == ""

    def test_skip_new_dir(self, tmp_path):
        sub = tmp_path / "newsub"
        sub.mkdir()
        data = filecheck.checkBegin(str(tmp_path))
        filecheck.options._skip_new_dirs = True
        result = filecheck.checkFile(str(sub), data)
        assert result is False

    def test_skip_existing_dir(self, tmp_path):
        sub = tmp_path / "existingsub"
        sub.mkdir()
        data = filecheck.checkBegin(str(tmp_path))
        data["_saved_keys"].add("existingsub")
        filecheck.options._skip_new_dirs = True
        result = filecheck.checkFile(str(sub), data)
        assert result is None

    def test_skip_new_dir_disabled(self, tmp_path):
        sub = tmp_path / "newsub"
        sub.mkdir()
        data = filecheck.checkBegin(str(tmp_path))
        filecheck.options._skip_new_dirs = False
        result = filecheck.checkFile(str(sub), data)
        assert result is None

    def test_skip_new_dir_oserror(self, tmp_path, monkeypatch):
        sub = tmp_path / "somepath"
        sub.mkdir()
        def mock_is_dir(*_):
            raise OSError("mock stat error")
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        data = filecheck.checkBegin(str(tmp_path))
        filecheck.options._skip_new_dirs = True
        result = filecheck.checkFile(str(sub), data)
        assert result is None


# ── compareData() ─────────────────────────────────────────────────────


class TestCompareData:
    def _run_compare(self, current, saved, dir_name):
        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            filecheck.compareData(current, saved, dir_name)
        finally:
            sys.stdout = old
        return buf.getvalue()

    def _setup_outcome(self, curr_overrides, saved_overrides, dir_name=os.path.normpath("/test")):
        base = make_info("f.txt")
        cur = dict(base)
        cur.update(curr_overrides or {})
        sav = dict(base)
        sav.update(saved_overrides or {})
        current = make_manifest([cur], dir_name=dir_name)
        saved = make_manifest([sav], dir_name=dir_name)
        return current, saved

    @pytest.mark.parametrize(
        ("name", "opts", "curr_overrides", "saved_overrides", "expected"),
        [
            ("dir_match",    {}, {"hash": "<DIR>"}, {"hash": "<DIR>"}, "same file"),
            ("dir_mismatch", {}, {"hash": "<DIR>"}, {"hash": "abc123"}, "directory mismatch"),
            ("size_mismatch", {}, {"size": 200}, {"size": 100}, "size mismatch"),
            ("mtime_mismatch", {}, {"mtime": 3000.5}, {"mtime": 2000.5}, "mtime mismatch"),
            ("atime_mismatch", {"check_atime": True}, {"atime": 9999.0}, {"atime": 3000.0}, "atime mismatch"),
            ("ctime_mismatch", {"check_ctime": True}, {"ctime": 8888.0}, {"ctime": 1000.0}, "ctime mismatch"),
            ("hash_mismatch",  {}, {"hash": "xxxx"}, {"hash": "yyyy"}, "MD5 mismatch"),
            ("same_file",      {}, {"hash": "abc123"}, {"hash": "abc123"}, "same file"),
            ("ignore_hash",    {"ignore_hash": True}, {"hash": "xxxx"}, {"hash": "yyyy"}, "same file"),
            ("ignore_size",    {"ignore_size": True}, {"size": 999}, {"size": 100}, "same file"),
            ("ignore_mtime",   {"ignore_mtime": True}, {"mtime": 9999.0}, {"mtime": 1000.0}, "same file"),
        ],
        ids=lambda p: p[0] if isinstance(p, tuple) else str(p)
    )
    def test_outcomes(self, name, opts, curr_overrides, saved_overrides, expected):
        for k, v in opts.items():
            setattr(filecheck.options, k, v)
        filecheck.options.show_same_files = True
        current, saved = self._setup_outcome(curr_overrides, saved_overrides)
        output = self._run_compare(current, saved, os.path.normpath("/test"))
        if expected == "same file":
            assert f"same file: {os.path.normpath('/test')}{os.sep}f.txt" in output
        else:
            assert f"{expected}: {os.path.normpath('/test')}{os.sep}f.txt" in output

    def test_new_item(self):
        """File in current but not in saved -> new item."""
        filecheck.options.show_same_files = False
        cur = make_info("f.txt")
        current = make_manifest([cur])
        saved = make_manifest([])

        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            filecheck.compareData(current, saved, os.path.normpath("/test"))
        finally:
            sys.stdout = old
        output = buf.getvalue()
        assert "new item" in output

    def test_lazy_hash_computation(self, tmp_path):
        """When current hash is empty and saved hash is not, compute MD5."""
        f = create_file(tmp_path / "f.txt", b"actual content")
        cur = make_info("f.txt", hash_val="", dir_name=str(tmp_path))
        sav = make_info("f.txt", hash_val="abc123", dir_name=str(tmp_path))
        current = make_manifest([cur], dir_name=str(tmp_path))
        saved = make_manifest([sav], dir_name=str(tmp_path))
        filecheck.options.show_same_files = True
        filecheck.options.ignore_hash = False

        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            filecheck.compareData(current, saved, str(tmp_path))
        finally:
            sys.stdout = old
        output = buf.getvalue()

        assert "MD5 mismatch" in output or "same file" in output
        new_hash = current["files"]["f.txt"]["hash"]
        assert len(new_hash) == 32
        assert new_hash != ""

    def test_lazy_hash_no_recompute_when_ignore_hash(self, tmp_path):
        """With ignore_hash=True, lazy computation is skipped."""
        f = create_file(tmp_path / "f.txt", b"content")
        cur = make_info("f.txt", hash_val="", dir_name=str(tmp_path))
        sav = make_info("f.txt", hash_val="abc123", dir_name=str(tmp_path))
        current = make_manifest([cur], dir_name=str(tmp_path))
        saved = make_manifest([sav], dir_name=str(tmp_path))
        filecheck.options.show_same_files = True
        filecheck.options.ignore_hash = True

        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            filecheck.compareData(current, saved, str(tmp_path))
        finally:
            sys.stdout = old
        output = buf.getvalue()
        assert "same file" in output
        assert current["files"]["f.txt"]["hash"] == ""

    @pytest.mark.parametrize(
        ("name", "show_same", "additional_current", "additional_saved", "expected_pattern"),
        [
            ("deleted_shown",             False, {},        {"del.txt": make_info("del.txt")}, "deleted file"),
            ("deleted_ignored_not_shown", False, {},        {".git": make_info(".git")},       None),
            ("deleted_empty_saved",       False, {},        {},                                None),
        ],
        ids=lambda p: p[0] if isinstance(p, tuple) else str(p)
    )
    def test_deleted_files(self, name, show_same, additional_current, additional_saved, expected_pattern):
        filecheck.options.show_same_files = show_same
        current = {"dirName": os.path.normpath("/test"), "files": dict(additional_current)}
        saved = {"files": dict(additional_saved)}

        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            filecheck.compareData(current, saved, os.path.normpath("/test"))
        finally:
            sys.stdout = old
        output = buf.getvalue()

        if expected_pattern is None:
            assert output == "" or "deleted file" not in output
        else:
            assert expected_pattern in output

    def test_multiple_statuses_in_one_run(self):
        """Mix of new, modified, same, and deleted in one compareData call."""
        filecheck.options.show_same_files = False
        base = make_info("same.txt")
        cur_new = make_info("new.txt")
        cur_mod = make_info("mod.txt", hash_val="newhash", size=200, mtime=9999.0)
        sav_mod = make_info("mod.txt", hash_val="oldhash", size=100, mtime=1000.0)
        sav_del = make_info("deleted.txt", hash_val="ghost")

        current = make_manifest([base, cur_new, cur_mod])
        saved = make_manifest([base, sav_mod, sav_del])

        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            filecheck.compareData(current, saved, os.path.normpath("/test"))
        finally:
            sys.stdout = old
        output = buf.getvalue()

        assert "new item" in output
        assert "size mismatch" in output or "mtime mismatch" in output or "MD5 mismatch" in output
        assert "deleted file" in output


# ── Progress during compareData() ─────────────────────────────────────

class TestCompareDataProgress:
    def test_progress_called_with_format(self, monkeypatch):
        """_progress is called with 'dir [count/total] filename' format."""
        calls = []
        monkeypatch.setattr(filecheck, '_progress', lambda msg: calls.append(msg))
        monkeypatch.setattr(filecheck, '_clear_progress', lambda: None)

        cur1 = make_info("f.txt")
        cur2 = make_info("g.txt")
        sav1 = make_info("f.txt", hash_val="old")
        sav2 = make_info("g.txt", hash_val="old")
        current = make_manifest([cur1, cur2])
        saved = make_manifest([sav1, sav2])
        filecheck.options.show_same_files = True

        filecheck.compareData(current, saved, os.path.normpath("/test"))

        progress_msgs = [c for c in calls if "[1/2]" in c or "[2/2]" in c]
        assert len(progress_msgs) >= 2
        assert any("[1/2] f.txt" in c for c in progress_msgs)
        assert any("[2/2] g.txt" in c for c in progress_msgs)

    def test_clear_progress_before_stdout(self, monkeypatch):
        """_clear_progress is called before each print."""
        clear_calls = []
        monkeypatch.setattr(filecheck, '_clear_progress', lambda: clear_calls.append(1))
        monkeypatch.setattr(filecheck, '_progress', lambda msg: None)

        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            current = make_manifest([make_info("f.txt", hash_val="x")])
            saved = make_manifest([make_info("f.txt", hash_val="y")])
            filecheck.options.show_same_files = True
            filecheck.compareData(current, saved, os.path.normpath("/test"))
        finally:
            sys.stdout = old

        output = buf.getvalue()
        status_lines = [l for l in output.splitlines() if ":" in l]
        assert len(status_lines) >= 1
        assert len(clear_calls) >= len(status_lines)

    def test_progress_restored_after_stdout(self, monkeypatch):
        """_progress is called again after each print."""
        progress_calls = []
        monkeypatch.setattr(filecheck, '_progress', lambda msg: progress_calls.append(msg))
        monkeypatch.setattr(filecheck, '_clear_progress', lambda: None)

        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            current = make_manifest([make_info("f.txt", hash_val="x")])
            saved = make_manifest([make_info("f.txt", hash_val="y")])
            filecheck.options.show_same_files = True
            filecheck.compareData(current, saved, os.path.normpath("/test"))
        finally:
            sys.stdout = old

        # 1 initial progress + 1 after-print restore
        assert len(progress_calls) >= 2
        assert "f.txt" in progress_calls[-1]

    def test_deleted_progress_format(self, monkeypatch):
        """Deleted files show [deleted] in progress."""
        calls = []
        monkeypatch.setattr(filecheck, '_progress', lambda msg: calls.append(msg))
        monkeypatch.setattr(filecheck, '_clear_progress', lambda: None)

        current = make_manifest([])
        saved = make_manifest([make_info("del.txt")])
        filecheck.compareData(current, saved, os.path.normpath("/test"))

        assert any("[deleted]" in c for c in calls)

    def test_deleted_clear_before_print(self, monkeypatch):
        """_clear_progress is called before printing deleted lines."""
        clear_calls = []
        monkeypatch.setattr(filecheck, '_clear_progress', lambda: clear_calls.append(1))
        monkeypatch.setattr(filecheck, '_progress', lambda msg: None)

        import io, sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            current = make_manifest([])
            saved = make_manifest([make_info("del.txt"), make_info("gone.txt")])
            filecheck.compareData(current, saved, os.path.normpath("/test"))
        finally:
            sys.stdout = old

        output = buf.getvalue()
        deleted_lines = [l for l in output.splitlines() if "deleted file" in l]
        assert len(deleted_lines) == 2
        assert len(clear_calls) >= 2

    def test_no_progress_in_quiet_mode(self, monkeypatch):
        """Quiet mode skips all _progress and _clear_progress calls."""
        calls = []
        monkeypatch.setattr(filecheck, '_progress', lambda msg: calls.append(msg))
        monkeypatch.setattr(filecheck, '_clear_progress', lambda: calls.append("clear"))

        filecheck.options.quiet = True
        current = make_manifest([make_info("f.txt", hash_val="x")])
        saved = make_manifest([make_info("f.txt", hash_val="y")])
        filecheck.compareData(current, saved, os.path.normpath("/test"))

        assert len(calls) == 0

    def test_no_progress_in_verbose_mode(self, monkeypatch):
        """Verbose mode skips all _progress and _clear_progress calls."""
        calls = []
        monkeypatch.setattr(filecheck, '_progress', lambda msg: calls.append(msg))
        monkeypatch.setattr(filecheck, '_clear_progress', lambda: calls.append("clear"))

        filecheck.options.verbose = True
        current = make_manifest([make_info("f.txt", hash_val="x")])
        saved = make_manifest([make_info("f.txt", hash_val="y")])
        filecheck.compareData(current, saved, os.path.normpath("/test"))

        assert len(calls) == 0


# ── checkEnd() ────────────────────────────────────────────────────────

class TestCheckEnd:
    def test_normal(self, tmp_path, capsys):
        data = filecheck.filecheckNew(str(tmp_path))
        data["files"]["f.txt"] = make_info("f.txt", dir_name=str(tmp_path))
        saved_data = filecheck.filecheckNew(str(tmp_path))
        saved_data["files"]["f.txt"] = make_info("f.txt", dir_name=str(tmp_path))
        filecheck.filecheckSave(saved_data, str(tmp_path))
        filecheck.options.show_same_files = True
        filecheck.checkEnd(str(tmp_path), data)
        captured = capsys.readouterr()
        assert "f.txt" in captured.out

    def test_invalid_manifest(self, tmp_path, monkeypatch, capsys):
        """When filecheckLoad returns False, checkEnd prints error and returns."""
        def mock_load(*_):
            return False
        monkeypatch.setattr(filecheck, 'filecheckLoad', mock_load)
        data = filecheck.filecheckNew(str(tmp_path))
        data["files"]["f.txt"] = make_info("f.txt", dir_name=str(tmp_path))
        filecheck.checkEnd(str(tmp_path), data)
        captured = capsys.readouterr()
        assert "invalid or corrupt manifest" in captured.out


class TestSummaryCounters:
    def test_new_item_increments_added(self):
        current = make_manifest([make_info("f.txt")])
        saved = make_manifest([])
        filecheck.compareData(current, saved, os.path.normpath("/test"))
        assert filecheck.check_added == 1
        assert filecheck.check_exit_code == 1

    def test_deleted_file_increments_deleted(self):
        current = make_manifest([])
        saved = make_manifest([make_info("del.txt")])
        filecheck.compareData(current, saved, os.path.normpath("/test"))
        assert filecheck.check_deleted == 1
        assert filecheck.check_exit_code == 1

    def test_modified_increments_modified(self):
        cur = make_info("f.txt", hash_val="newhash", size=999)
        sav = make_info("f.txt", hash_val="oldhash", size=100)
        current = make_manifest([cur])
        saved = make_manifest([sav])
        filecheck.compareData(current, saved, os.path.normpath("/test"))
        assert filecheck.check_modified == 1

    def test_same_file_increments_same(self):
        cur = make_info("f.txt", hash_val="abc")
        sav = make_info("f.txt", hash_val="abc")
        current = make_manifest([cur])
        saved = make_manifest([sav])
        filecheck.options.show_same_files = True
        filecheck.compareData(current, saved, os.path.normpath("/test"))
        assert filecheck.check_same == 1

    def test_counts_accumulate_across_calls(self):
        filecheck.compareData(
            make_manifest([make_info("a.txt")]),
            make_manifest([]),
            os.path.normpath("/test"),
        )
        filecheck.compareData(
            make_manifest([make_info("b.txt")]),
            make_manifest([]),
            os.path.normpath("/test"),
        )
        assert filecheck.check_added == 2

    def test_quiet_check_suppresses_summary(self, tmp_path, capsys):
        f = create_file(tmp_path / "f.txt", b"data")
        filecheck.options.recursive = False
        filecheck.options.show_same_files = True
        filecheck.options.quiet = True
        filecheck.analyze(str(tmp_path))
        filecheck.check(str(tmp_path))
        captured = capsys.readouterr()
        assert "Total:" not in captured.out
        assert "same file" in captured.out

    def test_check_outputs_summary(self, tmp_path, capsys):
        f = create_file(tmp_path / "f.txt", b"data")
        filecheck.options.recursive = False
        filecheck.options.show_same_files = True
        filecheck.options.quiet = False
        filecheck.analyze(str(tmp_path))
        filecheck.check(str(tmp_path))
        captured = capsys.readouterr()
        assert "Total:" in captured.out
        assert "Added:" in captured.out
        assert "Same:" in captured.out
