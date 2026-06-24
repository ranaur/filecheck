import pytest
import filecheck
import os
import stat
from filecheck import Options


@pytest.fixture(autouse=True)
def reset_globals():
    filecheck.options = Options()
    filecheck.check_exit_code = 0


def make_info(file_name, hash_val="abc123", size=100,
              ctime=1000.0, mtime=2000.0, atime=3000.0, dir_name=None):
    return {
        "fileName": file_name,
        "dirName": dir_name or os.path.normpath("/test"),
        "hash": hash_val,
        "size": size,
        "ctime": ctime,
        "mtime": mtime,
        "atime": atime,
    }


def make_manifest(files, dir_name=None):
    d = dir_name or os.path.normpath("/test")
    return {
        "dirName": d,
        "files": {f["fileName"]: f for f in files},
    }


def create_file(path, content=b"hello"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.fixture
def manifest_file(tmp_path):
    """Create a valid .filecheck manifest in tmp_path."""
    data = filecheck.filecheckNew(str(tmp_path))
    data["files"]["a.txt"] = make_info("a.txt", hash_val="aaa", size=10,
                                       dir_name=str(tmp_path))
    filecheck.filecheckSave(data, str(tmp_path))
    return tmp_path


@pytest.fixture
def stat_result():
    """Build an os.stat_result-like object with controllable attributes."""
    values = [0o100644, 0, 0, 0, 0, 0, 100, 1000.0, 2000.0, 3000.0]
    return os.stat_result(values)


@pytest.fixture
def mock_stat_no_birthtime(monkeypatch, stat_result):
    """Mock os.stat to return a result that lacks st_birthtime."""
    import collections
    NoBirthStat = collections.namedtuple(
        'NoBirthStat',
        'st_mode st_ino st_dev st_nlink st_uid st_gid '
        'st_size st_atime st_mtime st_ctime'
    )
    nb = NoBirthStat(
        st_mode=stat_result.st_mode,
        st_ino=0, st_dev=0, st_nlink=0, st_uid=0, st_gid=0,
        st_size=100,
        st_atime=3000.0, st_mtime=2000.0, st_ctime=1234.0,
    )
    monkeypatch.setattr(os, 'stat', lambda _: nb)
    return nb
