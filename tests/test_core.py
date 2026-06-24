import pytest
import filecheck
import os
import hashlib


# ── error() ──────────────────────────────────────────────────────────

class TestError:
    def test_prints_message(self, capsys):
        filecheck.error("test message")
        captured = capsys.readouterr()
        assert captured.out == "ERROR: test message\n"


# ── _compute_hash() ──────────────────────────────────────────────────

class TestComputeHash:
    def test_normal_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        expected = hashlib.md5(b"hello world").hexdigest()
        assert filecheck._compute_hash(str(f)) == expected

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert filecheck._compute_hash(str(f)) == "d41d8cd98f00b204e9800998ecf8427e"

    def test_binary_file(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(bytes(range(256)))
        result = filecheck._compute_hash(str(f))
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_large_file(self, tmp_path):
        f = tmp_path / "large.bin"
        data = b"ABCDEFGH" * 100000
        f.write_bytes(data)
        expected = hashlib.md5(data).hexdigest()
        assert filecheck._compute_hash(str(f)) == expected

    def test_nonexistent_file(self, capsys):
        assert filecheck._compute_hash(r"C:\nonexistent_file_xyz\foo.txt") == "error"
        captured = capsys.readouterr()
        assert "Error calculating" in captured.out

    def test_permission_denied(self, tmp_path, capsys, monkeypatch):
        f = tmp_path / "noperm.txt"
        f.write_text("secret")
        import builtins
        original_open = builtins.open
        def mock_open(*args, **kwargs):
            if args[0] == str(f):
                raise PermissionError(f"Permission denied: {args[0]}")
            return original_open(*args, **kwargs)
        monkeypatch.setattr(builtins, 'open', mock_open)
        assert filecheck._compute_hash(str(f)) == "error"
        captured = capsys.readouterr()
        assert "Error calculating" in captured.out

    def test_sha256(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert filecheck._compute_hash(str(f), "sha256") == expected

    def test_unknown_algorithm_falls_back_to_md5(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        expected = hashlib.md5(b"hello").hexdigest()
        assert filecheck._compute_hash(str(f), "unknown_algo") == expected

    def test_algorithm_from_options(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        filecheck.options.algorithm = "sha256"
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert filecheck._compute_hash(str(f)) == expected


# ── shouldIgnore() ────────────────────────────────────────────────────

class TestShouldIgnore:
    @pytest.mark.parametrize("path", [
        "/some/dir/.filecheck",
        "/some/dir/.filecheck.tmp",
        "/some/dir/.git",
        "/some/dir/.DS_Store",
        "/some/dir/Icon\r",
        "/some/dir/IconABC",
        "/some/dir/._IconXYZ",
    ])
    def test_should_ignore_true(self, path):
        assert filecheck.shouldIgnore(path) is True

    @pytest.mark.parametrize("path", [
        "/some/dir/normal.txt",
        "/some/dir/filecheck",
        "/some/dir/.gitignore",
        "/some/dir/D.S_Store",
        "/some/dir/myicon",
        "/some/dir/_.Icon",
    ])
    def test_should_ignore_false(self, path):
        assert filecheck.shouldIgnore(path) is False

    def test_exclude_pattern_matches(self):
        filecheck.options.exclude = ["*.log"]
        assert filecheck.shouldIgnore("test.log")

    def test_exclude_pattern_no_match(self):
        filecheck.options.exclude = ["*.log"]
        assert not filecheck.shouldIgnore("test.txt")

    def test_include_overrides_default_ignore(self):
        filecheck.options.include = ["*"]
        assert not filecheck.shouldIgnore(".filecheck")

    def test_include_does_not_override_without_match(self):
        filecheck.options.include = ["*.py"]
        assert filecheck.shouldIgnore(".filecheck")


# ── filecheckNew() ────────────────────────────────────────────────────

class TestFilecheckNew:
    def test_creates_empty_manifest(self):
        result = filecheck.filecheckNew("/my/dir")
        assert result == {"dirName": "/my/dir", "files": {}}


# ── filecheckSet() ────────────────────────────────────────────────────

class TestFilecheckSet:
    def test_adds_file_info(self):
        data = {"files": {}}
        info = {"fileName": "foo.txt", "hash": "abc"}
        filecheck.filecheckSet(data, info)
        assert data["files"]["foo.txt"] == info

    def test_overwrites_existing(self):
        data = {"files": {}}
        info1 = {"fileName": "foo.txt", "hash": "abc"}
        info2 = {"fileName": "foo.txt", "hash": "xyz"}
        filecheck.filecheckSet(data, info1)
        filecheck.filecheckSet(data, info2)
        assert data["files"]["foo.txt"]["hash"] == "xyz"


# ── filecheckSave() ───────────────────────────────────────────────────

class TestFilecheckSave:
    def _read_lines(self, tmp_path):
        raw = (tmp_path / ".filecheck").read_bytes()
        text = raw.decode("utf-8")
        lines = [l.strip(" \r") for l in text.split("\n") if l.strip(" \r")]
        return lines, text

    def test_saves_empty_manifest(self, tmp_path):
        data = filecheck.filecheckNew(str(tmp_path))
        filecheck.filecheckSave(data, str(tmp_path))
        mf = tmp_path / ".filecheck"
        assert mf.is_file()
        lines, text = self._read_lines(tmp_path)
        assert "FILECHECK:" in text
        assert any(filecheck.version in l for l in lines)

    def test_saves_files(self, tmp_path):
        data = filecheck.filecheckNew(str(tmp_path))
        data["files"]["a.txt"] = {
            "fileName": "a.txt", "hash": "aaa",
            "size": 10, "ctime": 1.0, "mtime": 2.0, "atime": 3.0,
        }
        filecheck.filecheckSave(data, str(tmp_path))
        lines, text = self._read_lines(tmp_path)
        assert len(lines) == 2
        assert "aaa:10:" in lines[1]

    def test_overwrites_existing(self, tmp_path):
        data = filecheck.filecheckNew(str(tmp_path))
        data["files"]["v1.txt"] = {"fileName": "v1.txt", "hash": "old",
                                   "size": 1, "ctime": 1.0, "mtime": 1.0, "atime": 1.0}
        filecheck.filecheckSave(data, str(tmp_path))
        data["files"] = {}
        data["files"]["v2.txt"] = {"fileName": "v2.txt", "hash": "new",
                                   "size": 2, "ctime": 2.0, "mtime": 2.0, "atime": 2.0}
        filecheck.filecheckSave(data, str(tmp_path))
        lines, text = self._read_lines(tmp_path)
        assert len(lines) == 2
        assert "v2.txt" in lines[1]

    def test_save_exception(self, tmp_path, capsys, monkeypatch):
        """When os.replace raises, the save is aborted and error is printed."""
        data = filecheck.filecheckNew(str(tmp_path))
        (tmp_path / ".filecheck").write_text("dummy", encoding="utf-8")
        def mock_replace(*_):
            raise OSError("mock replace error")
        monkeypatch.setattr(os, 'replace', mock_replace)
        filecheck.filecheckSave(data, str(tmp_path))
        captured = capsys.readouterr()
        assert "cannot save info" in captured.out
        # File content unchanged because replace failed
        assert (tmp_path / ".filecheck").read_text(encoding="utf-8") == "dummy"

    def test_uses_unix_line_endings(self, tmp_path):
        """New manifests use \\n line endings (not \\r\\r\\n)."""
        data = filecheck.filecheckNew(str(tmp_path))
        data["files"]["f.txt"] = {
            "fileName": "f.txt", "hash": "abc",
            "size": 10, "ctime": 1.0, "mtime": 2.0, "atime": 3.0,
        }
        filecheck.filecheckSave(data, str(tmp_path))
        raw = (tmp_path / ".filecheck").read_bytes()
        assert raw.endswith(b"\n"), "must end with \\n"
        assert not raw.endswith(b"\r\r\n"), "must NOT end with old \\r\\r\\n"

    def test_no_temp_file_left_after_save(self, tmp_path):
        """Temp file is cleaned up after successful save."""
        data = filecheck.filecheckNew(str(tmp_path))
        data["files"]["f.txt"] = {
            "fileName": "f.txt", "hash": "abc",
            "size": 10, "ctime": 1.0, "mtime": 2.0, "atime": 3.0,
        }
        filecheck.filecheckSave(data, str(tmp_path))
        assert not (tmp_path / ".filecheck.tmp").exists()
        assert (tmp_path / ".filecheck").exists()


# ── filecheckLoad() ───────────────────────────────────────────────────

class TestFilecheckLoad:
    def test_no_manifest_returns_empty(self, tmp_path):
        result = filecheck.filecheckLoad(str(tmp_path))
        assert result["files"] == {}
        assert result["dirName"] == str(tmp_path)

    def test_loads_valid_manifest(self, tmp_path):
        data = filecheck.filecheckNew(str(tmp_path))
        data["files"]["a.txt"] = {
            "fileName": "a.txt", "hash": "aaa",
            "size": 10, "ctime": 1.0, "mtime": 2.0, "atime": 3.0,
        }
        filecheck.filecheckSave(data, str(tmp_path))
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "a.txt" in loaded["files"]
        assert loaded["files"]["a.txt"]["hash"] == "aaa"
        assert loaded["files"]["a.txt"]["size"] == 10

    def test_loads_multiple_files(self, tmp_path):
        data = filecheck.filecheckNew(str(tmp_path))
        for name, hsh in [("a.txt", "aaa"), ("b.txt", "bbb"), ("c.txt", "ccc")]:
            data["files"][name] = {
                "fileName": name, "hash": hsh,
                "size": 10, "ctime": 1.0, "mtime": 2.0, "atime": 3.0,
            }
        filecheck.filecheckSave(data, str(tmp_path))
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert sorted(loaded["files"].keys()) == ["a.txt", "b.txt", "c.txt"]

    def test_invalid_header_wrong_prefix(self, tmp_path):
        mf = tmp_path / ".filecheck"
        mf.write_text(f"INVALID:{filecheck.version}:{filecheck.signature}\r\r\n", encoding="utf-8")
        result = filecheck.filecheckLoad(str(tmp_path))
        assert result is False

    def test_invalid_header_wrong_version(self, tmp_path):
        mf = tmp_path / ".filecheck"
        mf.write_text(f"\ufeffFILECHECK:99.9:{filecheck.signature}\r\r\n", encoding="utf-8")
        result = filecheck.filecheckLoad(str(tmp_path))
        assert result is False

    def test_invalid_header_wrong_signature(self, tmp_path):
        mf = tmp_path / ".filecheck"
        mf.write_text("\ufeffFILECHECK:0.1:WRONG_SIG\r\r\n", encoding="utf-8")
        result = filecheck.filecheckLoad(str(tmp_path))
        assert result is False

    def test_invalid_header_too_few_fields(self, tmp_path):
        mf = tmp_path / ".filecheck"
        mf.write_text("\ufeffFILECHECK:0.1\r\r\n", encoding="utf-8")
        result = filecheck.filecheckLoad(str(tmp_path))
        assert result is False

    def test_data_line_with_less_than_6_fields(self, tmp_path):
        data = filecheck.filecheckNew(str(tmp_path))
        data["files"]["good.txt"] = {
            "fileName": "good.txt", "hash": "aaa",
            "size": 10, "ctime": 1.0, "mtime": 2.0, "atime": 3.0,
        }
        filecheck.filecheckSave(data, str(tmp_path))
        mf = tmp_path / ".filecheck"
        content = mf.read_text(encoding="utf-8")
        content += "bad_line_with_2:fields\n"
        mf.write_text(content, encoding="utf-8")
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "good.txt" in loaded["files"]
        assert loaded["files"]["good.txt"]["hash"] == "aaa"

    def test_empty_file_returns_empty_manifest(self, tmp_path):
        mf = tmp_path / ".filecheck"
        mf.write_text("", encoding="utf-8")
        result = filecheck.filecheckLoad(str(tmp_path))
        assert result["files"] == {}

    def test_loads_old_cr_cr_lf_manifest(self, tmp_path):
        """Backward compat: manifest with \\r\\r\\n endlines is loadable."""
        mf = tmp_path / ".filecheck"
        raw = (
            f"\ufeffFILECHECK:{filecheck.version}:{filecheck.signature}\r\r\n"
            f"abc:10:1.0:2.0:3.0:f.txt\r\r\n"
        ).encode("utf-8")
        mf.write_bytes(raw)
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "f.txt" in loaded["files"]
        assert loaded["files"]["f.txt"]["hash"] == "abc"

    def test_loads_cr_lf_manifest(self, tmp_path):
        """Backward compat: manifest with \\r\\n endlines is loadable."""
        mf = tmp_path / ".filecheck"
        raw = (
            f"\ufeffFILECHECK:{filecheck.version}:{filecheck.signature}\r\n"
            f"abc:10:1.0:2.0:3.0:f.txt\r\n"
        ).encode("utf-8")
        mf.write_bytes(raw)
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "f.txt" in loaded["files"]
        assert loaded["files"]["f.txt"]["hash"] == "abc"


# ── generateBegin() / generateEnd() ───────────────────────────────────

class TestGenerateBeginEnd:
    def test_generate_begin_default(self):
        filecheck.options.verbose = False
        data = filecheck.generateBegin("/my/dir")
        assert data["dirName"] == "/my/dir"

    def test_generate_begin_verbose(self, capsys):
        filecheck.options.verbose = True
        data = filecheck.generateBegin("/my/dir")
        assert data["dirName"] == "/my/dir"
        captured = capsys.readouterr()
        assert "/my/dir" in captured.out

    def test_generate_end(self, tmp_path, monkeypatch):
        saved = []
        monkeypatch.setattr(filecheck, 'filecheckSave', lambda d, dn: saved.append((d, dn)))
        data = filecheck.filecheckNew(str(tmp_path))
        filecheck.generateEnd(str(tmp_path), data)
        assert saved[0][1] == str(tmp_path)


# ── generateFile() / generateFileWithoutHash() / _generateFile() ──────

class TestGenerateFile:
    def test_generate_file_with_hash(self, tmp_path):
        f = create_file(tmp_path / "test.txt", b"content")
        data = filecheck.filecheckNew(str(tmp_path))
        filecheck.generateFile(str(f), data)
        assert "test.txt" in data["files"]
        assert len(data["files"]["test.txt"]["hash"]) == 32

    def test_generate_file_without_hash(self, tmp_path):
        f = create_file(tmp_path / "test.txt", b"content")
        data = filecheck.filecheckNew(str(tmp_path))
        filecheck.generateFileWithoutHash(str(f), data)
        assert "test.txt" in data["files"]
        assert data["files"]["test.txt"]["hash"] == ""

    def test_generate_file_ignored(self, tmp_path):
        data = filecheck.filecheckNew(str(tmp_path))
        filecheck.generateFile(str(tmp_path / ".filecheck"), data)
        assert ".filecheck" not in data["files"]

    def test_generate_file_exception(self, tmp_path, capsys, monkeypatch):
        data = filecheck.filecheckNew(str(tmp_path))
        def mock_make_info(*_):
            raise PermissionError("mocked fail")
        monkeypatch.setattr(filecheck, 'makeInfo', mock_make_info)
        f = create_file(tmp_path / "test.txt", b"x")
        filecheck._generateFile(str(f), data, False)
        captured = capsys.readouterr()
        assert "ERROR: cannot generate info" in captured.out


# ── makeInfo() ────────────────────────────────────────────────────────

class TestMakeInfo:
    def test_directory_returns_dir_hash(self, tmp_path):
        d = tmp_path / "subdir"
        d.mkdir()
        info = filecheck.makeInfo(str(d))
        assert info["hash"] == "<DIR>"

    def test_file_with_callable_hash(self, tmp_path):
        f = create_file(tmp_path / "f.txt", b"data")
        info = filecheck.makeInfo(str(f), filecheck._compute_hash)
        assert len(info["hash"]) == 32

    def test_file_with_non_callable_hash(self, tmp_path):
        f = create_file(tmp_path / "f.txt", b"data")
        info = filecheck.makeInfo(str(f), False)
        assert info["hash"] == ""

    def test_stat_failure_returns_none(self, tmp_path, capsys, monkeypatch):
        f = create_file(tmp_path / "f.txt", b"x")
        from pathlib import Path
        monkeypatch.setattr(Path, 'is_dir', lambda self: False)
        def mock_stat(*_, **__):
            raise OSError("stat failed")
        monkeypatch.setattr(os, 'stat', mock_stat)
        result = filecheck.makeInfo(str(f))
        assert result is None
        captured = capsys.readouterr()
        assert "ERROR: Error getting file info" in captured.out

    def test_st_birthtime_missing(self, tmp_path, monkeypatch):
        """st_birthtime doesn't exist (Linux) — falls back to st_ctime."""
        f = create_file(tmp_path / "f.txt", b"data")
        import collections
        NoBirthStat = collections.namedtuple(
            'NoBirthStat',
            'st_mode st_ino st_dev st_nlink st_uid st_gid '
            'st_size st_atime st_mtime st_ctime'
        )
        nb = NoBirthStat(
            st_mode=0o100644, st_ino=0, st_dev=0, st_nlink=1,
            st_uid=0, st_gid=0, st_size=4,
            st_atime=3000.0, st_mtime=2000.0, st_ctime=1234.0,
        )
        monkeypatch.setattr(os, 'stat', lambda _, **__: nb)
        info = filecheck.makeInfo(str(f), False)
        assert info["ctime"] == 1234.0

    def test_file_metadata(self, tmp_path):
        f = create_file(tmp_path / "f.txt", b"hello world")
        info = filecheck.makeInfo(str(f), False)
        assert info["fileName"] == "f.txt"
        assert info["size"] == 11
        assert isinstance(info["mtime"], float)
        assert isinstance(info["atime"], float)
        assert isinstance(info["ctime"], float)


# ── helpers ───────────────────────────────────────────────────────────

def create_file(path, content=b"hello"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
