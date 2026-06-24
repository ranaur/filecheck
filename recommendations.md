# Code Audit & Architectural Recommendations

Marks:
 . => doing
 * => done
 x => won't do/not necessary anymore

## Security

| # | Issue | Severity | Recommendation |
|---|-------|----------|----------------|
|*1 | **MD5 is cryptographically broken** — `hashlib.md5()` in `md5()` at `filecheck.py:25` uses a hash known to be vulnerable to collision attacks. For file integrity verification this may be acceptable, but it is not future-proof. | Medium | Replace with SHA-256 or SHA-512 by default; support a `--hash` flag to select algorithm. SHA-256 is available in the standard library via `hashlib.sha256()`. |
|x2 | **No path traversal validation** — `filecheckLoad()` (`filecheck.py:101`) trusts filenames from the manifest verbatim when building file paths via `os.path.join()`. A tampered manifest could reference files outside the intended directory. | Low | Validate that resolved paths are within the target directory using `os.path.realpath()` and `Path.resolve()`. |
|x3 | **Dynamic dispatch via `globals()[args.command]()`** (`filecheck.py:323`) — Maps user input directly to a global function call. While constrained to `generate`/`update`/`check` by argparse, this pattern is fragile and complicates static analysis. | Low | Use a dispatch dict or `if/elif` chain. |
|x4 | **`subprocess.Popen(..., shell=True)`** in `test_filecheck.py:14` — Shell injection risk if `args` came from untrusted input. | Low | Use `shlex.split()` or pass a list directly. |
|*5 | **BOM in manifest header** (`\ufeff`) — Useless byte-order mark that can confuse cross-platform diff/merge tools. | Low | Drop the BOM or offer a flag to omit it. |

## Performance

| # | Issue | Severity | Recommendation |
|---|-------|----------|----------------|
|*6 | **`os.listdir()` + `os.lstat()` per entry** (`walkTree()`, line 45-50) — Two syscalls per entry. `os.scandir()` returns both names and stat info in one call. | Medium | Replace with `os.scandir()` which yields `DirEntry` objects with cached `stat()` results. |
|x7 | **Manifest fully loaded into memory** (`filecheckLoad()`, line 108) — All entries stored in a dict. For millions of files this becomes expensive. | Medium | Consider streaming checks, or storing in a simpler indexed format (e.g., SQLite). |
|*8 | **No parallel hashing** — Large directories with many files hash sequentially on a single thread. | Low | Use `concurrent.futures.ThreadPoolExecutor` for I/O-bound file reads. |
|*9 | **`a+t` open mode** (`filecheckSave()`, line 92) — Unnecessary; a fresh write (`wt`) is clearer and avoids any append overhead on some platforms. | Low | Replace with `open(dbFile, "w", ...)`. |
|x10 | **`int()` truncation of timestamps** (`compareData()`, lines 157-162) — Truncates to whole seconds, forcing a rehash on every check even if the sub-second portion is the only difference. | Low | Compare with a tolerance (e.g., `abs(a - b) < 0.01`) or use `float` comparison directly. |

## Robustness

| # | Issue | Severity | Recommendation |
|---|-------|----------|----------------|
|*11 | **Non-standard line ending `\r\r\n`** — Defined at `filecheck.py:13` as the manifest line terminator. This will cause interoperability problems on all platforms, especially Unix. | High | Replace with `\n` (or at worst `\r\n`). Backward compatibility can be handled by detecting the existing line ending on load. |
|*12 | **No atomic manifest write** — `filecheckSave()` writes directly to `.filecheck`. A crash mid-write corrupts the manifest. | High | Write to `.filecheck.tmp` then `os.rename()` (atomic on most file systems). |
|*13 | **Undefined variable in exception handler** — `filecheckSave()` line 98 references `filecheckDirName` which is never defined; should be `dirName` or `data["dirName"]`. | High | Fix the variable name. |
|x14 | **`st_birthtime` may not exist** — `makeInfo()` line 216 uses `stat_info.st_birthtime or stat_info.st_ctime`. On Linux, `st_birthtime` doesn't exist, raising `AttributeError`. `st_ctime` on Linux is *change time*, not *creation time*. | High | Use `getattr(stat_info, 'st_birthtime', stat_info.st_ctime)`. |
|*15 | **No recursion depth guard** — `walkTree()` is recursive. Deeply nested directory structures (thousands of levels) will cause `RecursionError`. | Medium | Convert to iterative stack or use `os.walk()` (which is iterative internally). |
|*16 | **TOCTOU race in manifest overwrite** — Lines 89-92: `isfile()`, `unlink()`, then `open()`. The file could be re-created between unlink and open. | Medium | Open with `"wt"` directly (truncates), or write to a temp file and rename. |
|*17 | **`ignoreFiles` mixes exact strings and globs** — `".git"` is exact, `"Icon*"` is a glob. `fnmatch` treats `".git"` as a pattern too, which happens to match exactly. This works but is unclear. | Low | Separate literal names from patterns, or make all entries explicit globs. |
|*18 | **No `--exclude`/`--include` CLI flags** — Users must edit source code to add patterns. | Low | Accept `--exclude` and `--include` patterns on the command line. |
|*19 | **Signature string is fragile** — A Unicode arrow character (`U+27F9`) is used as a version delimiter. Encoding mismatches could cause false "invalid header" errors on load. | Low | Use a simple ASCII version string. |

## Modern Practices / Code Quality

| # | Issue | Severity | Recommendation |
|---|-------|----------|----------------|
|*20 | **Global mutable `options` dict** — Defined at module level at `filecheck.py:15`, mutated by CLI parsing, accessed throughout. This prevents reentrancy and complicates testing. | Medium | Pass options as a parameter or use a dataclass/namespace. |
|*21 | **No type hints** — The codebase has zero annotations despite targeting Python 3. | Medium | Add type hints for all function signatures. |
|*22 | **`os.path` instead of `pathlib`** — Throughout the codebase. `pathlib.Path` provides a cleaner, object-oriented API. | Low | Migrate to `pathlib.Path`. |
|*23 | **Broad except clauses** — Several functions catch `Exception` generically (lines 31, 51, 97, 200, 221, 328). This can hide actual bugs. | Medium | Catch specific exceptions (e.g., `PermissionError`, `FileNotFoundError`). |
|*24 | **Hardcoded `python3` in test** — `test_filecheck.py:24` runs `python3 filecheck.py ...`. Fails if Python 3 is not on PATH as `python3`. | Low | Use `sys.executable` or `venv` shebang. |
| 25 | **No CI configuration** — No `.github/workflows/`, `.gitlab-ci.yml`, or similar. | Low | Add CI to run tests on push. |
|x26 | **No `__init__.py`** — Can't be imported as a package. | Low | Restructure as a package with `__init__.py` and `__main__.py`. |
|*27 | **Duplicate CLI argument definitions** — `--check-atime`, `--check-ctime`, etc. are defined separately for `update` and `check` subparsers. | Low | Use a shared parent parser with `add_parser(..., parents=[...])`. |

## Missing Features

| # | Feature | Rationale |
|---|---------|-----------|
|*28 | **Non-zero exit code on mismatch** — `check` always exits 0. Should exit with a code indicating how many files differ (or at least 1 if any difference found). |
|*29 | **Check summary** — Print "X files matched, Y modified, Z new, W deleted" at end. |
|x30 | **`--dry-run`** — Show what would change without writing the manifest. |
|x31 | **`--format json`** — Machine-readable output for scripting. |
|*32 | **Configurable hash algorithm** — `--hash sha256`, `--hash blake2b`. |
|x33 | **Custom manifest path** — `--manifest my-manifest.txt`. |
|*34 | **Exclude patterns from CLI** — `--exclude "*.log" --exclude "tmp/"`. |
|x35 | **Progress bar** — `tqdm` or spinner for large trees. |
|x36 | **Ignore list from file** — `--ignore-file .filecheckignore`. |
|x37 | **Check subdirectories independently** — Each subdirectory gets its own `.filecheck` (already done in recursive mode), but there's no way to verify only a subset. |
|x38 | **Whitespace/encoding-safe filenames** — Filenames with colons (`:`) would break the manifest's colon-delimited format. Need an escaping mechanism or a more robust format (e.g., JSON Lines, MessagePack). |

## Architecture Recommendations

The following structural changes would address most of the issues above:

### 1. Restructure as a Python Package

```
filecheck/
  __init__.py       # version, public API
  __main__.py       # `python -m filecheck` entry
  cli.py            # argparse, option handling
  core.py           # walk, hash, compare logic
  manifest.py       # read/write/format abstraction
  types.py          # dataclasses (FileInfo, Options, etc.)
  _compat.py        # platform-specific helpers (st_birthtime, etc.)
```

### 2. Use Dataclasses for Data

```python
@dataclass
class FileInfo:
    path: Path
    hash: str = ""
    size: int = 0
    ctime: float = 0.0
    mtime: float = 0.0
    atime: float = 0.0

@dataclass
class Manifest:
    version: str
    signature: str
    files: dict[str, FileInfo]
    dirname: Path
```

### 3. Support Algorithm Agility

```python
HASH_ALGOS = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
    "blake2b": hashlib.blake2b,
}
```

### 4. Atomic Manifest Writes

Always write to `.filecheck.tmp`, then `os.replace(src, dst)` for atomic swap.

### 5. Streaming / Lazy Check Mode

For very large directories, allow checking file-by-file without loading the entire manifest into memory (e.g., via an index-backed store).

### 6. Iterative Walk

Replace recursive `walkTree()` with a stack-based loop to avoid stack overflow on deep trees.

### 7. Better Serialization Format

Current colon-delimited format breaks on filenames with colons. Options:
- **JSON Lines** (`.jsonl`) — one JSON object per line, human-readable.
- **MessagePack** — compact binary, fast.
- **CSV with quoting** — standard and parseable by other tools.

### 8. Add CI/CD

A minimal GitHub Actions workflow:

```yaml
# .github/workflows/test.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python test_filecheck.py
```

---

## Migration Path

1. **Immediate fixes** (low effort, high impact): #11 (line endings), #13 (undefined variable), #14 (st_birthtime), #7 (os.scandir), #12 (atomic write).
2. **Short-term** (medium effort): #1 (SHA-256 default), #21 (type hints), #20 (eliminate global options), #15 (iterative walk), #28 (exit codes), #29 (summary).
3. **Medium-term**: Package restructuring, pathlib migration, format improvements.
4. **Long-term**: Parallel hashing, plugin system, SQLite-backed manifests.
