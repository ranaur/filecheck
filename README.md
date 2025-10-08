# filecheck
MD5 file checker to verify backup copies

# Summary
[c:\Trove\my-git\filecheck\filecheck.py](cci:7://file:///c:/Trove/my-git/filecheck/filecheck.py:0:0-0:0) is a Python 2 CLI tool to track and verify file integrity for a directory. It creates and maintains a `.filecheck` manifest recording each file’s MD5 hash, size, and timestamps, and can later compare current files against that manifest to report changes.

# How it works
- **Manifest file**: Stored at `DIR/.filecheck` with a header and one line per entry.
- **Recorded fields**: `hash`, `size`, `ctime`, `mtime`, `atime`, and `fileName` (see [makeInfo()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:216:0-230:15)).
- **Directory walk**: [walkTree()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:39:0-67:33) scans a directory (optionally recursively), skipping symlinks and ignoring certain names via [shouldIgnore()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:32:0-37:16).
- **Ignore patterns**: `ignoreFiles` includes `.filecheck`, `.filecheck.tmp`, `.git`, `Icon*`, `.DS_Store`, etc.

# Commands
- **generate DIR**  
  Builds a new manifest with MD5 for files and `<DIR>` for directories.  
  Functions: [generate()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:273:0-275:116), [generateBegin()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:192:0-196:32), [generateFile()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:206:0-207:38), [generateEnd()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:199:0-201:32), [filecheckSave()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:79:0-93:77).

- **update DIR**  
  Loads existing `.filecheck`, rescans metadata, and only recomputes MD5 for files that appear changed (size/mtime/ctime/atime according to flags).  
  Functions: [update()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:277:0-279:110), [updateBegin()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:232:0-238:21), [updateFile()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:240:0-268:57), [updateEnd()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:270:0-271:39).

- **check DIR**  
  Compares current directory state to the saved manifest and reports:
  - new item, deleted file
  - size/mtime/ctime/atime mismatch
  - MD5 mismatch
  - directory mismatch
  - same file (optional display)  
  Functions: [check()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:281:0-283:107), [checkBegin()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:128:0-131:33), [checkFile()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:133:0-134:43), [checkEnd()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:182:0-190:41), [compareData()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:136:0-180:73).

Note: During check, hashes are computed lazily only when metadata matches but a hash is needed ([compareData()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:136:0-180:73)).

# File format
Written by [filecheckSave()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:79:0-93:77):
- Header line (with BOM): `\xef\xbb\xbfFILECHECK:<version>:<signature>\r\n`
- One line per file/dir: `<hash>:<size>:<ctime>:<mtime>:<atime>:<fileName>\r\n`
- Parsed by [filecheckLoad()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:95:0-126:14).

# CLI options (per subcommand)
- **Common**: `-r/--recursive`, `-l/--follow-links` (note: symlinks are actually skipped), `-v/--verbose`
- **update/check**:
  - `-a/--check-atime`, `-c/--check-ctime`
  - `-M/--ignore-mtime`, `-S/--ignore-size`
- **check only**: `-s/--show-same-files`, `-H/--ignore-hash`

# Notable details and limitations
- **Python 2 only**: Shebang `#!/usr/bin/env python2` and Python 2 `print` statements.
- **Symlinks ignored**: [walkTree()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:39:0-67:33) explicitly skips symlinks, so `--follow-links` has no effect.
- **Minor bug**: In [filecheckSave()](cci:1://file:///c:/Trove/my-git/filecheck/filecheck.py:79:0-93:77), the exception handler references `filecheckDirName` which is undefined; should be `dirName` or `data["dirName"]`.
- **Platform note**: `ctime` means creation time on Windows, change time on Unix.

# Example usage
- Generate manifest for current dir:
  ```
  python filecheck.py generate .
  ```
- Update manifest (recompute hashes only for changed files):
  ```
  python filecheck.py update . -r
  ```
- Check current files against saved manifest:
  ```
  python filecheck.py check . -r -s
  ```
- Check ignoring mtime differences:
  ```
  python filecheck.py check . -r -M
  ```

