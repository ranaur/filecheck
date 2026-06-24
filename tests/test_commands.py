import pytest
import filecheck
import os
from tests.conftest import create_file


class TestGenerateCommand:
    def test_generate_non_recursive(self, tmp_path, capsys):
        f = create_file(tmp_path / "f.txt", b"data")
        sub = tmp_path / "sub"
        sub.mkdir()
        create_file(sub / "nested.txt", b"nested")
        filecheck.options['recursive'] = False
        filecheck.generate(str(tmp_path))
        mf = tmp_path / ".filecheck"
        assert mf.is_file()
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "f.txt" in loaded["files"]
        assert "nested.txt" not in loaded["files"]
        captured = capsys.readouterr()
        assert "GENERATE:" in captured.out

    def test_generate_recursive(self, tmp_path):
        create_file(tmp_path / "f.txt", b"data")
        sub = tmp_path / "sub"
        sub.mkdir()
        create_file(sub / "nested.txt", b"nested")
        filecheck.options['recursive'] = True
        filecheck.generate(str(tmp_path))
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "f.txt" in loaded["files"]
        assert "sub" in loaded["files"]
        # Nested files get their own .filecheck in the subdirectory
        sub_loaded = filecheck.filecheckLoad(str(sub))
        assert "nested.txt" in sub_loaded["files"]

    def test_generate_verbose(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"data")
        filecheck.options['verbose'] = True
        filecheck.generate(str(tmp_path))
        captured = capsys.readouterr()
        assert str(tmp_path) in captured.out
        assert "GENERATE:" in captured.out


class TestUpdateCommand:
    def test_update_existing(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"original")
        filecheck.options['recursive'] = False
        filecheck.generate(str(tmp_path))
        old_hash = filecheck.filecheckLoad(str(tmp_path))["files"]["f.txt"]["hash"]
        create_file(tmp_path / "f.txt", b"modified content")
        filecheck.update(str(tmp_path))
        new_hash = filecheck.filecheckLoad(str(tmp_path))["files"]["f.txt"]["hash"]
        assert new_hash != old_hash
        captured = capsys.readouterr()
        assert "UPDATE:" in captured.out

    def test_update_no_changes(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"stable")
        filecheck.options['recursive'] = False
        filecheck.generate(str(tmp_path))
        original_hash = filecheck.filecheckLoad(str(tmp_path))["files"]["f.txt"]["hash"]
        filecheck.update(str(tmp_path))
        same_hash = filecheck.filecheckLoad(str(tmp_path))["files"]["f.txt"]["hash"]
        assert same_hash == original_hash


class TestCheckCommand:
    def test_check_no_changes(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"data")
        filecheck.options['recursive'] = False
        filecheck.generate(str(tmp_path))
        filecheck.options['show_same_files'] = True
        filecheck.check(str(tmp_path))
        captured = capsys.readouterr()
        assert "CHECK:" in captured.out
        assert "same file" in captured.out

    def test_check_detects_new_file(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"data")
        filecheck.options['recursive'] = False
        filecheck.generate(str(tmp_path))
        create_file(tmp_path / "g.txt", b"new")
        filecheck.check(str(tmp_path))
        captured = capsys.readouterr()
        assert "new item" in captured.out

    def test_check_detects_deleted_file(self, tmp_path, capsys):
        create_file(tmp_path / "f.txt", b"data")
        filecheck.options['recursive'] = False
        filecheck.generate(str(tmp_path))
        (tmp_path / "f.txt").unlink()
        filecheck.check(str(tmp_path))
        captured = capsys.readouterr()
        assert "deleted file" in captured.out
