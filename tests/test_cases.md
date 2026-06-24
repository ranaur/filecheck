# Test Plan for 100% Line Coverage of `filecheck.py`

## Structure

Each test group below covers a function (or related set of functions). For each, I enumerate every **branch path**, **exception path**, and **edge case** that must be exercised.

---

## 1. Module-Level Constants — Lines 10–18

| Test | What It Exercises | Lines |
|------|-------------------|-------|
| 1.1 | Verify `version == "0.1"` | 10 |
| 1.2 | Verify `signature` is a string (decoded from bytes) | 12 |
| 1.3 | Verify `endline == "\r\r\n"` | 13 |
| 1.4 | Verify `options` is an empty dict | 15 |
| 1.5 | Verify `filecheckName`, `filecheckTempName`, `ignoreFiles` are correct | 16–18 |

---

## 2. `error(message)` — Lines 20–21

| Test | Input | Expected | Lines |
|------|-------|----------|-------|
| 2.1 | `error("test")` | Prints `ERROR: test` | 20–21 |

---

## 3. `md5(fileName)` — Lines 23–33

| Test | Condition | Expected | Lines |
|------|-----------|----------|-------|
| 3.1 | Normal file with content | Returns correct 32-char hex MD5 | 25, 27–30 |
| 3.2 | Empty file | Returns `d41d8cd98f00b204e9800998ecf8427e` | 25, 27–30 |
| 3.3 | Binary file (e.g., PNG header bytes) | Returns correct hash | 25, 27–30 |
| 3.4 | **Exception**: non-existent file | Prints error, returns `"error"` | 31–33 |
| 3.5 | **Exception**: permission-denied file | Prints error, returns `"error"` | 31–33 |

---

## 4. `shouldIgnore(filename)` — Lines 35–40

| Test | Input | Expected | Lines |
|------|-------|----------|-------|
| 4.1 | `"/path/.filecheck"` | `True` (exact match) | 37–38 |
| 4.2 | `"/path/.filecheck.tmp"` | `True` (exact match) | 37–38 |
| 4.3 | `"/path/.git"` | `True` (exact match) | 37–38 |
| 4.4 | `"/path/.DS_Store"` | `True` (glob match) | 37–38 |
| 4.5 | `"/path/Icon\r"` (with CR) | `True` (glob match `Icon*`) | 37–38 |
| 4.6 | `"/path/._IconSomething"` | `True` (glob match `._Icon*`) | 37–38 |
| 4.7 | `"/path/normal.txt"` | `False` | 37–38, 40 |
| 4.8 | Partial match: `"my.filecheck"` | `False` (no pattern matches) | 37–38, 40 |

---

## 5. `walkTree(top, callback, recursive, followLink, data, beginDirCallback, endDirCallback)` — Lines 42–71

### Branch matrix

| # | Scenario | `beginDirCallback` | `endDirCallback` | `recursive` | `followLink` | Entries | Lines Covered |
|---|----------|-------------------|------------------|-------------|--------------|---------|---------------|
| 5.1 | beginDirCb is callable → called | lambda | False | - | - | empty dir | 43–44 |
| 5.2 | beginDirCb is not callable → skipped | `False` | - | - | - | empty dir | 43 (skips 44) |
| 5.3 | Ignores matching file | - | - | - | - | `.filecheck` only | 45–46 (skip) |
| 5.4 | **Exception**: `os.lstat()` fails | - | - | - | - | unreadable entry | 49–53 |
| 5.5 | Symlink, `followLink=False` → skip | - | - | - | `False` | symlink entry | 55–56 |
| 5.6 | Symlink, `followLink=True` → falls through to `else` ("Skipping") | - | - | - | `True` | symlink entry | 55 (skip), 58–69 (else) |
| 5.7 | Directory, `recursive=False` | - | - | `False` | - | one subdir | 58–63 (callback, skip recurse) |
| 5.8 | Directory, `recursive=True` | - | - | `True` | - | one subdir | 58–63 (callback + recurse) |
| 5.9 | Regular file | - | - | - | - | one file | 64–66 |
| 5.10 | **Unknown type** (FIFO, socket, device) | - | - | - | - | FIFO entry | 67–69 |
| 5.11 | endDirCb is callable → called | - | lambda | - | - | empty dir | 70–71 |
| 5.12 | endDirCb not callable → skipped | - | `False` | - | - | empty dir | 70 (skips 71) |
| 5.13 | Multiple entries (file + dir + ignored) all in one pass | - | - | - | - | mix | 45–71 |

**Edge cases:**
| 5.14 | Directory is empty | - | - | - | - | none | 45 (no loop iterations) |
| 5.15 | `os.listdir()` raises `PermissionError` | - | - | - | - | N/A | program crashes (handled at caller) |

---

## 6. `filecheckNew(dirName)` — Lines 74–78

| Test | Input | Expected | Lines |
|------|-------|----------|-------|
| 6.1 | `filecheckNew("/tmp")` | `{'dirName': '/tmp', 'files': {}}` | 75–78 |
| 6.2 | `filecheckNew(".")` | Correct relative path | 75–78 |

---

## 7. `filecheckSet(data, info)` — Lines 80–81

| Test | Input | Expected | Lines |
|------|-------|----------|-------|
| 7.1 | Add one file | `data["files"]["a.txt"] == info` | 81 |
| 7.2 | Add two files (overwrite same key) | Last write wins | 81 |

---

## 8. `filecheckSave(data, dirName)` — Lines 83–99

| Test | Condition | Expected | Lines |
|------|-----------|----------|-------|
| 8.1 | No existing `.filecheck`, empty files dict | Creates file with header only | 85–96 (skip 89–90) |
| 8.2 | Existing `.filecheck`, non-empty files | Overwrites, writes header + entries | 89–96 |
| 8.3 | **Exception**: permission denied on dir | Calls `error()` + `traceback.print_exc()` | 97–99 |
| 8.4 | **Edge**: `len(data["files"]) == 0` (≥ 0 is always true, so always writes) | Header written | 91–96 |

---

## 9. `filecheckLoad(dirName)` — Lines 101–132

| Test | Condition | Expected | Lines |
|------|-----------|----------|-------|
| 9.1 | No `.filecheck` exists | Returns empty manifest | 103–106 |
| 9.2 | Valid `.filecheck`, one data line | Parses header + 1 entry correctly | 108–132 |
| 9.3 | Valid `.filecheck`, multiple data lines | Parses all entries | 108–132 (loop iterations) |
| 9.4 | **Invalid header** (wrong version) | Prints error, returns `False` | 111–117 |
| 9.5 | **Invalid header** (wrong `\ufeffFILECHECK` prefix) | Prints error, returns `False` | 111–117 |
| 9.6 | **Invalid header** (wrong signature) | Prints error, returns `False` | 111–117 |
| 9.7 | **Invalid header** (< 3 fields) | Prints error, returns `False` | 112–117 |
| 9.8 | Valid header but data line has < 6 fields | Line is silently skipped | 120–121 (skip 122–131) |
| 9.9 | **Edge**: Empty file (no lines) | Returns empty manifest (header never parsed) | 108 (no iterations) |

---

## 10. `checkBegin(dirName)` — Lines 134–137

| Test | `options['verbose']` | Expected | Lines |
|------|----------------------|----------|-------|
| 10.1 | `True` | Prints `dirName`, returns new manifest | 135–137 |
| 10.2 | `False` | Returns new manifest (no print) | 137 (skip 135–136) |

---

## 11. `checkFile(fileName, data)` — Lines 139–140

| Test | Expected | Lines |
|------|----------|-------|
| 11.1 | Calls `generateFileWithoutHash(fileName, data)` | 140 |

---

## 12. `compareData(current, saved, dirName)` — Lines 142–176

### Main loop (lines 144–173) — status outcomes:

| # | Status | Conditions | Lines |
|---|--------|------------|-------|
| 12.1 | `"new item"` | `key not in saved["files"]` | 146–147, 172–173 |
| 12.2 | `"directory mismatch"` | Both entries exist, one is `"<DIR>"`, hashes differ | 150–152, 172–173 |
| 12.3 | `"same file"` (DIR variant) | Both entries exist, both `"<DIR>"`, hashes match | 150–151, 153–154, 172–173 |
| 12.4 | `"size mismatch"` | `ignore_size=False`, sizes differ | 155, 172–173 |
| 12.5 | `"mtime mismatch"` | `ignore_mtime=False`, int(mtime) differs | 157, 172–173 |
| 12.6 | `"atime mismatch"` | `check_atime=True`, int(atime) differs | 159, 172–173 |
| 12.7 | `"ctime mismatch"` | `check_ctime=True`, int(ctime) differs | 161, 172–173 |
| 12.8 | **Lazy hash compute** | `ignore_hash=False`, `current hash == ""`, `saved hash != ""` | 164–165 |
| 12.9 | `"MD5 mismatch"` | `ignore_hash=False`, hashes differ | 167–168, 172–173 |
| 12.10 | `"same file"` (hash match) | `ignore_hash=False`, hashes match | 167, 169–170, 172–173 |
| 12.11 | `"same file"` (ignore_hash) | `ignore_hash=True` | 163 (skip 164–170), 169–170, 172–173 |

### Display logic (lines 172–173):
| 12.12 | `show_same_file=True`, status=`"same file"` | Prints `"same file: ..."` | 172–173 |
| 12.13 | `show_same_file=False`, status=`"same file"` | Does not print | 172 (skips 173) |
| 12.14 | Any non-`"same file"` status | Always prints | 172–173 |

### Deleted file loop (lines 174–176):
| 12.15 | Saved has remaining entries not ignored | Prints `"deleted file: ..."` | 175–176 |
| 12.16 | Saved has remaining entries that ARE ignored | Does not print | 175 (skips 176) |
| 12.17 | No remaining entries | Loop body never runs | 174 (skip) |

---

## 13. `checkEnd(dirName, data)` — Lines 178–180

| Test | Condition | Expected | Lines |
|------|-----------|----------|-------|
| 13.1 | Valid saved manifest exists | Loads manifest, calls `compareData()` | 179–180 |
| 13.2 | **Edge**: saved manifest has invalid header (`filecheckLoad` returns `False`) | `compareData` receives `False` as `saved` → will fail when iterating `saved["files"]` → exception at line 144 (`for key, currentValue in current["files"]`) → actually `current` is fine, it's `saved` that's False. Then line 146 `key not in saved["files"]` → TypeError. Caught by? Wait, `checkEnd` is called from `walkTree`'s endDirCallback, which is called at line 71. No try/except there. But `check()` at line 274 calls `walkTree` inside `__main__`'s try block (322–332). So exception caught at line 327. | 179–180 then exception |

Actually, this is an important edge case. When `filecheckLoad` returns `False` (invalid header), `checkEnd` passes that `False` to `compareData` as `saved`. Then at line 146, `key not in saved["files"]` will throw `TypeError: 'bool' object is not subscriptable`. The test should verify this happens.

---

## 14. `generateBegin(dirName)` — Lines 182–185

| Test | `options['verbose']` | Expected | Lines |
|------|----------------------|----------|-------|
| 14.1 | `True` | Prints `dirName`, returns new manifest | 183–185 |
| 14.2 | `False` | Returns new manifest silently | 185 (skip 183–184) |

---

## 15. `generateEnd(dirName, data)` — Lines 187–188

| Test | Expected | Lines |
|------|----------|-------|
| 15.1 | Calls `filecheckSave(data, dirName)` | 188 |

---

## 16. `generateFileWithoutHash(fileName, data)` — Lines 190–191

| Test | Expected | Lines |
|------|----------|-------|
| 16.1 | Calls `_generateFile(fileName, data, False)` | 191 |

---

## 17. `generateFile(fileName, data)` — Lines 193–194

| Test | Expected | Lines |
|------|----------|-------|
| 17.1 | Calls `_generateFile(fileName, data, md5)` | 194 |

---

## 18. `_generateFile(fileName, data, hashFunc)` — Lines 196–201

| Test | Condition | Expected | Lines |
|------|-----------|----------|-------|
| 18.1 | File is NOT ignored, `makeInfo` succeeds | Calls `filecheckSet` | 198–199 |
| 18.2 | File IS ignored | Does nothing | 198 (skip 199) |
| 18.3 | **Exception**: `makeInfo` raises (e.g., permission denied) | Calls `error()`, caught by except | 200–201 |
| 18.4 | `makeInfo` returns `None` (stat failed) → `filecheckSet(data, None)` → `info["fileName"]` raises `TypeError` | Caught by except at line 200 | 200–201 |

---

## 19. `makeInfo(fileName, hashFunc=False)` — Lines 203–223

| Test | Conditions | Expected | Lines |
|------|------------|----------|-------|
| 19.1 | `fileName` is a directory | hash = `"<DIR>"` | 204–205, 209–220 |
| 19.2 | Not a dir, `hashFunc` is callable | hash is computed via `hashFunc` | 204, 207, 209–220 |
| 19.3 | Not a dir, `hashFunc` is not callable (e.g., `False`) | hash = `""` | 204, 207, 209–220 |
| 19.4 | **Exception**: `os.stat()` fails | Returns `None`, prints error | 221–223 |
| 19.5 | **Edge**: `st_birthtime` exists (macOS/Windows) → uses `st_birthtime` | ctime = `st_birthtime` | 216 |
| 19.6 | **Edge**: `st_birthtime` does not exist (Linux) → falls back to `st_ctime` | ctime = `st_ctime` | 216 |
| 19.7 | **Edge**: `st_birthtime` is 0 (falsy) → falls back to `st_ctime` | ctime = `st_ctime` | 216 |

---

## 20. `updateBegin(dirName)` — Lines 225–231

| Test | `verbose` | `.filecheck` exists | Expected | Lines |
|------|-----------|---------------------|----------|-------|
| 20.1 | `False` | Yes | Loads old, creates new, returns both | 228–231 |
| 20.2 | `True` | No | Prints dirName, returns empty old + new | 226–231 |
| 20.3 | `False` | No (corner: first update) | Old manifest is empty | 228–231 |

---

## 21. `updateFile(fileName, data)` — Lines 233–259

### Branch matrix for `changed` detection (lines 238–253):

| # | Condition path | `changed` | Lines |
|---|----------------|-----------|-------|
| 21.1 | `baseName` NOT in `data["old"]["files"]` | `True` | 252–253 |
| 21.2 | `baseName` in old, size differs, `ignore_size=False` | `True` | 240–243 |
| 21.3 | `baseName` in old, size same, `check_ctime=True`, ctime differs | `True` | 240–246 |
| 21.4 | `baseName` in old, size same, `check_ctime=False`, `check_atime=True`, atime differs | `True` | 240, 247–248 |
| 21.5 | `baseName` in old, size same, `check_ctime=False`, `check_atime=False`, mtime differs, `ignore_mtime=False` | `True` | 240, 249–251 |
| 21.6 | `baseName` in old, all checks pass (no differences or all checks disabled) | `False` | 240 (changed stays False) |

### Post-change logic (lines 255–259):
| 21.7 | `changed=True` | Prints "Regenerating", calls `generateFile` (with hash) | 256–257 |
| 21.8 | `changed=False` | Copies old hash to new entry | 259 |

### Edge:
| 21.9 | `updateFile` called for a directory entry → `generateFileWithoutHash` adds dir to `data["new"]["files"]` with hash `<DIR>`, `baseName` won't have a matching entry in `old` with `<DIR>` hash (it might be `<DIR>` too) → `changed=True` → regenerates (computes MD5 on dir), which adds `<DIR>` again via `makeInfo` because dir detection runs first in `makeInfo` | Correct behavior | 233–259 |

---

## 22. `updateEnd(dirName, data)` — Lines 261–262

| Test | Expected | Lines |
|------|----------|-------|
| 22.1 | Calls `filecheckSave(data["new"], dirName)` | 262 |

---

## 23. `generate(directory)` — Lines 264–266

| Test | Condition | Expected | Lines |
|------|-----------|----------|-------|
| 23.1 | Basic call | Prints `"GENERATE: {dir}"`, walks tree with generateFile/generateBegin/generateEnd | 265–266 |

---

## 24. `update(directory)` — Lines 268–270

| Test | Condition | Expected | Lines |
|------|-----------|----------|-------|
| 24.1 | Basic call | Prints `"UPDATE: {dir}"`, walks tree with updateFile/updateBegin/updateEnd | 269–270 |

---

## 25. `check(directory)` — Lines 272–274

| Test | Condition | Expected | Lines |
|------|-----------|----------|-------|
| 25.1 | Basic call | Prints `"CHECK: {dir}"`, walks tree with checkFile/checkBegin/checkEnd | 273–274 |

---

## 26. CLI `__main__` — Lines 276–332

| Test | CLI Args | Expected | Lines |
|------|----------|----------|-------|
| 26.1 | No args | Prints help | 319–320 |
| 26.2 | `generate .` | Runs `generate(".")` | 323 |
| 26.3 | `update .` | Runs `update(".")` | 323 |
| 26.4 | `check .` | Runs `check(".")` | 323 |
| 26.5 | `generate -v -r .` | `options['verbose']=True`, `options['recursive']=True` | 322–323, 312–317 |
| 26.6 | `update -a -c -M -S .` | All update flags | 322–323, 312–317 |
| 26.7 | `check -a -c -M -S -H -s -r .` | All check flags | 322–323, 312–317 |
| 26.8 | **KeyboardInterrupt** during execution | Prints cancellation, exits 1 | 324–326 |
| 26.9 | **General exception** without `--verbose` | Prints `"ERROR: {e}"`, exits 1 | 328, 332 |
| 26.10 | **General exception** with `--verbose` | Also prints traceback | 329–332 |

---

## Summary: Line Coverage Map

| Line Range | Function | Tests Required (minimal) |
|------------|----------|--------------------------|
| 10–18 | Constants | 5 tests |
| 20–21 | `error` | 1 test |
| 23–33 | `md5` | 5 tests |
| 35–40 | `shouldIgnore` | 8 tests |
| 42–71 | `walkTree` | 15 tests |
| 74–78 | `filecheckNew` | 2 tests |
| 80–81 | `filecheckSet` | 2 tests |
| 83–99 | `filecheckSave` | 4 tests |
| 101–132 | `filecheckLoad` | 9 tests |
| 134–137 | `checkBegin` | 2 tests |
| 139–140 | `checkFile` | 1 test |
| 142–176 | `compareData` | 17 tests |
| 178–180 | `checkEnd` | 2 tests |
| 182–185 | `generateBegin` | 2 tests |
| 187–188 | `generateEnd` | 1 test |
| 190–191 | `generateFileWithoutHash` | 1 test |
| 193–194 | `generateFile` | 1 test |
| 196–201 | `_generateFile` | 4 tests |
| 203–223 | `makeInfo` | 7 tests |
| 225–231 | `updateBegin` | 3 tests |
| 233–259 | `updateFile` | 9 tests |
| 261–262 | `updateEnd` | 1 test |
| 264–266 | `generate` | 1 test |
| 268–270 | `update` | 1 test |
| 272–274 | `check` | 1 test |
| 276–332 | `__main__` | 10 tests |

**Total: ~116 tests** (many can be combined into single test functions with multiple assertions).

---

## Notes for Implementation

- Use `unittest.mock` for:
  - `os.lstat` failure (test 5.4)
  - `os.listdir` returning special files (FIFO, socket) for unknown type (test 5.10)
  - `os.stat` raising exception (test 19.4)
  - `st_birthtime` missing (test 19.6) or falsy (test 19.7)
  - File permission denied for `md5` (tests 3.5) and `makeInfo` (test 18.3)
  - `filecheckSave` I/O exception (test 8.3)

- Use `tempfile.mkdtemp()` + `shutil.rmtree()` for all filesystem-backed tests.

- `compareData` tests should be unit-tested directly (not via `check`/`checkEnd`) because setting up the right option flags and data dicts is easier.

- The `options` global dict must be reset between tests (set the relevant keys).

- For `__main__` tests, use `unittest.mock.patch('sys.argv', [...])` and capture stdout/stderr.

- For test 13.2 (invalid manifest passed to checkEnd), use `unittest.mock.patch` to make `filecheckLoad` return `False`.
