import pytest
import filecheck
import os
from tests.conftest import create_file


class TestAnalyzeCommand:
    def test_analyze_non_recursive(self, tmp_path, capsys):
        f = create_file(tmp_path / "f.txt", b"data")
        sub = tmp_path / "sub"
        sub.mkdir()
        create_file(sub / "nested.txt", b"nested")
        filecheck.options.recursive = False
        filecheck.analyze(str(tmp_path))
        mf = tmp_path / ".filecheck"
        assert mf.is_file()
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "f.txt" in loaded["files"]
        assert "nested.txt" not in loaded["files"]
        captured = capsys.readouterr()
        assert "ANALYZE:" in captured.out

    def test_analyze_recursive(self, tmp_path):
        create_file(tmp_path / "f.txt", b"data")
        sub = tmp_path / "sub"
        sub.mkdir()
        create_file(sub / "nested.txt", b"nested")
        filecheck.options.recursive = True
        filecheck.analyze(str(tmp_path))
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "f.txt" in loaded["files"]
        assert "sub" in loaded["files"]
        # Nested files get their own .filecheck in the subdirectory
        sub_loaded = filecheck.filecheckLoad(str(sub))
        assert "nested.txt" in sub_loaded["files"]

    def test_analyze_verbose(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"data")
        filecheck.options.verbose = True
        filecheck.analyze(str(tmp_path))
        captured = capsys.readouterr()
        assert str(tmp_path) in captured.out
        assert "ANALYZE:" in captured.out

    def test_analyze_existing(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"original")
        filecheck.options.recursive = False
        filecheck.analyze(str(tmp_path))
        old_hash = filecheck.filecheckLoad(str(tmp_path))["files"]["f.txt"]["hash"]
        create_file(tmp_path / "f.txt", b"modified content")
        filecheck.analyze(str(tmp_path))
        new_hash = filecheck.filecheckLoad(str(tmp_path))["files"]["f.txt"]["hash"]
        assert new_hash != old_hash
        captured = capsys.readouterr()
        assert "ANALYZE:" in captured.out

    def test_analyze_no_changes(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"stable")
        filecheck.options.recursive = False
        filecheck.analyze(str(tmp_path))
        original_hash = filecheck.filecheckLoad(str(tmp_path))["files"]["f.txt"]["hash"]
        filecheck.analyze(str(tmp_path))
        same_hash = filecheck.filecheckLoad(str(tmp_path))["files"]["f.txt"]["hash"]
        assert same_hash == original_hash

    def test_analyze_corrupt_manifest(self, tmp_path):
        create_file(tmp_path / "f.txt", b"data")
        mf = tmp_path / ".filecheck"
        mf.write_text("INVALID_HEADER\n", encoding="utf-8")
        filecheck.options.recursive = False
        filecheck.analyze(str(tmp_path))
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "f.txt" in loaded["files"]


class TestCheckCommand:
    def test_check_no_changes(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"data")
        filecheck.options.recursive = False
        filecheck.analyze(str(tmp_path))
        filecheck.options.show_same_files = True
        filecheck.check(str(tmp_path))
        captured = capsys.readouterr()
        assert "CHECK:" in captured.out
        assert "same file" in captured.out

    def test_check_detects_new_file(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"data")
        filecheck.options.recursive = False
        filecheck.analyze(str(tmp_path))
        create_file(tmp_path / "g.txt", b"new")
        filecheck.check(str(tmp_path))
        captured = capsys.readouterr()
        assert "new item" in captured.out

    def test_check_detects_deleted_file(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"data")
        filecheck.options.recursive = False
        filecheck.analyze(str(tmp_path))
        (tmp_path / "f.txt").unlink()
        filecheck.check(str(tmp_path))
        captured = capsys.readouterr()
        assert "deleted file" in captured.out
