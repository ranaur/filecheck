import pytest
import filecheck
import os
from tests.conftest import make_info, create_file


# ── updateBegin() ─────────────────────────────────────────────────────

class TestUpdateBegin:
    def test_verbose(self, capsys, tmp_path):
        filecheck.options['verbose'] = True
        result = filecheck.updateBegin(str(tmp_path))
        assert "old" in result
        assert "new" in result
        captured = capsys.readouterr()
        assert str(tmp_path) in captured.out

    def test_non_verbose(self, tmp_path):
        filecheck.options['verbose'] = False
        result = filecheck.updateBegin(str(tmp_path))
        assert "old" in result
        assert "new" in result
        assert result["old"]["files"] == {}

    def test_with_existing_manifest(self, manifest_file):
        """When .filecheck exists, old is populated."""
        result = filecheck.updateBegin(str(manifest_file))
        assert "a.txt" in result["old"]["files"]
        assert result["old"]["files"]["a.txt"]["hash"] == "aaa"

    def test_without_manifest(self, tmp_path):
        """When no .filecheck, old is empty."""
        result = filecheck.updateBegin(str(tmp_path))
        assert result["old"]["files"] == {}


# ── updateFile() ──────────────────────────────────────────────────────

class TestUpdateFile:
    def make_update_data(self, tmp_path, old_files=None):
        old = filecheck.filecheckNew(str(tmp_path))
        if old_files:
            for f in old_files:
                old["files"][f["fileName"]] = f
        new = filecheck.filecheckNew(str(tmp_path))
        return {"old": old, "new": new}

    # --- changed=True paths ---

    def test_new_file_not_in_old(self, tmp_path, capsys):
        """baseName not in old files -> changed = True -> regenerate."""
        f = create_file(tmp_path / "new.txt", b"fresh")
        data = self.make_update_data(tmp_path)
        filecheck.updateFile(str(f), data)
        assert "new.txt" in data["new"]["files"]
        assert len(data["new"]["files"]["new.txt"]["hash"]) == 32
        captured = capsys.readouterr()
        assert "Regenerating" in captured.out

    def test_size_changed(self, tmp_path, capsys):
        f = create_file(tmp_path / "f.txt", b"new larger content")
        old_info = make_info("f.txt", hash_val="oldhash", size=5, dir_name=str(tmp_path))
        data = self.make_update_data(tmp_path, [old_info])
        filecheck.updateFile(str(f), data)
        captured = capsys.readouterr()
        assert "reason: size" in captured.out
        assert "Regenerating" in captured.out
        assert data["new"]["files"]["f.txt"]["hash"] != "oldhash"

    def test_ctime_changed(self, tmp_path, capsys):
        filecheck.options['check_ctime'] = True
        filecheck.options['ignore_size'] = True
        f = create_file(tmp_path / "f.txt", b"same content")
        old_info = make_info("f.txt", hash_val="oldhash", size=14, ctime=1000.0, dir_name=str(tmp_path))
        data = self.make_update_data(tmp_path, [old_info])
        filecheck.updateFile(str(f), data)
        captured = capsys.readouterr()
        assert "reason: ctime" in captured.out or "Regenerating" in captured.out

    def test_atime_changed(self, tmp_path, capsys):
        filecheck.options['check_atime'] = True
        filecheck.options['check_ctime'] = False
        filecheck.options['ignore_size'] = True
        f = create_file(tmp_path / "f.txt", b"same content")
        old_info = make_info("f.txt", hash_val="oldhash", size=14, ctime=1000.0, atime=1000.0, dir_name=str(tmp_path))
        data = self.make_update_data(tmp_path, [old_info])
        filecheck.updateFile(str(f), data)
        captured = capsys.readouterr()
        assert "Regenerating" in captured.out

    def test_mtime_changed(self, tmp_path, capsys):
        filecheck.options['ignore_size'] = True
        filecheck.options['ignore_mtime'] = False
        f = create_file(tmp_path / "f.txt", b"same content")
        old_info = make_info("f.txt", hash_val="oldhash", size=14, mtime=1000.0, dir_name=str(tmp_path))
        data = self.make_update_data(tmp_path, [old_info])
        filecheck.updateFile(str(f), data)
        captured = capsys.readouterr()
        assert "reason: mtime" in captured.out
        assert "Regenerating" in captured.out

    # --- changed=False path ---

    def test_no_change(self, tmp_path, capsys):
        filecheck.options['ignore_size'] = True
        filecheck.options['ignore_mtime'] = False
        filecheck.options['check_ctime'] = False
        filecheck.options['check_atime'] = False
        f = create_file(tmp_path / "f.txt", b"data")
        old_info = make_info("f.txt", hash_val="existing", size=4, mtime=2000.0, dir_name=str(tmp_path))
        data = self.make_update_data(tmp_path, [old_info])
        # Ensure mtime matches by stat'ing the file and using its real mtime
        st = os.stat(str(f))
        old_info["mtime"] = st.st_mtime
        data["old"]["files"]["f.txt"] = old_info
        filecheck.updateFile(str(f), data)
        assert data["new"]["files"]["f.txt"]["hash"] == "existing"
        captured = capsys.readouterr()
        assert "Regenerating" not in captured.out

    def test_no_change_all_checks_disabled(self, tmp_path):
        """If all checks are disabled/skipped and file exists in old, hash is copied."""
        filecheck.options['ignore_size'] = True
        filecheck.options['ignore_mtime'] = True
        filecheck.options['check_ctime'] = False
        filecheck.options['check_atime'] = False
        f = create_file(tmp_path / "f.txt", b"data")
        old_info = make_info("f.txt", hash_val="existing_hash", size=999, mtime=9999.0, ctime=9999.0, dir_name=str(tmp_path))
        data = self.make_update_data(tmp_path, [old_info])
        filecheck.updateFile(str(f), data)
        assert data["new"]["files"]["f.txt"]["hash"] == "existing_hash"


# ── updateEnd() ───────────────────────────────────────────────────────

class TestUpdateEnd:
    def test_saves_new_manifest(self, tmp_path, monkeypatch):
        saved_args = []
        monkeypatch.setattr(filecheck, 'filecheckSave', lambda d, dn: saved_args.append((d, dn)))
        new_data = filecheck.filecheckNew(str(tmp_path))
        data = {"new": new_data}
        filecheck.updateEnd(str(tmp_path), data)
        assert saved_args[0][0] is new_data
        assert saved_args[0][1] == str(tmp_path)
