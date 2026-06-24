import pytest
import filecheck
import sys
import os
import io


class TestCLI:
    def run_main(self, args, tmp_path=None):
        """Run filecheck.main with given args, capturing output."""
        if tmp_path is not None:
            orig_dir = os.getcwd()
            os.chdir(str(tmp_path))
        out = io.StringIO()
        err = io.StringIO()
        old_out = sys.stdout
        old_err = sys.stderr
        sys.stdout = out
        sys.stderr = err
        try:
            try:
                filecheck.main(args)
            except SystemExit as e:
                return e.code, out.getvalue() + err.getvalue()
            return 0, out.getvalue() + err.getvalue()
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
            if tmp_path is not None:
                os.chdir(orig_dir)

    def test_no_command_shows_help(self):
        ret, out = self.run_main([])
        assert "usage:" in out.lower()

    def test_generate(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("data")
        ret, out = self.run_main(["generate", "."], tmp_path)
        assert ret == 0
        assert "GENERATE:" in out
        assert (tmp_path / ".filecheck").is_file()

    def test_update(self, tmp_path):
        (tmp_path / "f.txt").write_text("data")
        self.run_main(["generate", "."], tmp_path)
        (tmp_path / "f.txt").write_text("modified")
        ret, out = self.run_main(["update", "."], tmp_path)
        assert ret == 0
        assert "UPDATE:" in out

    def test_check(self, tmp_path):
        (tmp_path / "f.txt").write_text("data")
        self.run_main(["generate", "."], tmp_path)
        ret, out = self.run_main(["check", "."], tmp_path)
        assert ret == 0
        assert "CHECK:" in out

    def test_generate_recursive_flag(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested")
        (tmp_path / "f.txt").write_text("data")
        ret, out = self.run_main(["generate", "-r", "."], tmp_path)
        assert ret == 0
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "sub" in loaded["files"]
        sub_loaded = filecheck.filecheckLoad(str(tmp_path / "sub"))
        assert "nested.txt" in sub_loaded["files"]

    def test_generate_verbose_flag(self, tmp_path):
        (tmp_path / "f.txt").write_text("data")
        ret, out = self.run_main(["-v", "generate", "."], tmp_path)
        assert ret == 0
        # With verbose, the directory name is printed during walk
        assert "GENERATE:" in out

    def test_check_all_flags(self, tmp_path):
        (tmp_path / "f.txt").write_text("data")
        self.run_main(["generate", "."], tmp_path)
        ret, out = self.run_main(
            ["check", "-r", "-s", "-a", "-c", "-M", "-S", "-H", "."],
            tmp_path
        )
        assert ret == 0

    def test_keyboard_interrupt(self, tmp_path, monkeypatch):
        def mock_generate(*_):
            raise KeyboardInterrupt()
        monkeypatch.setattr(filecheck, 'generate', mock_generate)
        ret, out = self.run_main(["generate", "."], tmp_path)
        assert ret == 1
        assert "cancelled" in out

    def test_general_exception(self, tmp_path, monkeypatch):
        def mock_generate(*_):
            raise RuntimeError("unexpected error")
        monkeypatch.setattr(filecheck, 'generate', mock_generate)
        ret, out = self.run_main(["generate", "."], tmp_path)
        assert ret == 1
        assert "ERROR: Error: unexpected error" in out

    def test_general_exception_verbose(self, tmp_path, monkeypatch):
        def mock_generate(*_):
            raise RuntimeError("unexpected error")
        monkeypatch.setattr(filecheck, 'generate', mock_generate)
        ret, out = self.run_main(["-v", "generate", "."], tmp_path)
        assert ret == 1
        assert "Traceback" in out

    def test_update_with_all_flags(self, tmp_path):
        (tmp_path / "f.txt").write_text("data")
        self.run_main(["generate", "."], tmp_path)
        ret, out = self.run_main(
            ["update", "-a", "-c", "-M", "-S", "."],
            tmp_path
        )
        assert ret == 0
        assert "UPDATE:" in out

    def test_check_exit_code_nonzero_on_mismatch(self, tmp_path):
        (tmp_path / "f.txt").write_text("data")
        self.run_main(["generate", "."], tmp_path)
        (tmp_path / "f.txt").write_text("modified")
        ret, out = self.run_main(["check", "."], tmp_path)
        assert ret != 0

    def test_exclude_flag_via_cli(self, tmp_path):
        (tmp_path / "keep.txt").write_text("keep")
        (tmp_path / "ignore.log").write_text("ignore")
        ret, out = self.run_main(["generate", "--exclude", "*.log", "."], tmp_path)
        assert ret == 0
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "keep.txt" in loaded["files"]
        assert "ignore.log" not in loaded["files"]

    def test_include_flag_via_cli(self, tmp_path):
        """--include pattern overrides ignore list so normally-ignored files are tracked."""
        (tmp_path / "_IconShouldBeIgnored").write_text("normally ignored")
        (tmp_path / "regular.txt").write_text("normal")
        ret, out = self.run_main(["generate", "--include", "Icon*", "."], tmp_path)
        assert ret == 0
        loaded = filecheck.filecheckLoad(str(tmp_path))
        assert "regular.txt" in loaded["files"]
        assert "_IconShouldBeIgnored" in loaded["files"]
