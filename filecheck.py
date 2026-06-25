#!/usr/bin/env python3
from __future__ import annotations
import traceback
import sys
import argparse
import os
import stat
import hashlib
from fnmatch import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
import itertools
import shutil
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any

version: str = "0.2"
signature: str = "FLCK"
endline: str = "\n"

filecheckName: str = ".filecheck"
filecheckTempName: str = ".filecheck.tmp"
_IGNORE_EXACT: list[str] = [filecheckName, filecheckTempName, ".git", ".DS_Store"]
_IGNORE_GLOB: list[str] = ["._Icon*", "Icon*"]

check_exit_code: int = 0
check_added: int = 0
check_deleted: int = 0
check_modified: int = 0
check_same: int = 0

_SUPPORTED_VERSIONS: tuple[str, ...] = ("0.1", "0.2")
_SUPPORTED_SIGS: tuple[str, ...] = ("\u27f9", "FLCK")
_SPINNER_FRAMES: tuple[str, ...] = ("⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷")
_spinner_cycle = itertools.cycle(_SPINNER_FRAMES)
_terminal_width: int = 0


def _get_width() -> int:
    global _terminal_width
    if _terminal_width == 0:
        try:
            _terminal_width = shutil.get_terminal_size().columns
        except (AttributeError, OSError, ValueError):
            _terminal_width = 80
    return _terminal_width


def _progress(path: str) -> None:
    avail: int = _get_width() - 2
    if avail < 1:
        avail = 1
    if len(path) > avail:
        display: str = path[-(avail - 1):]
    else:
        display = path
    try:
        print(f"\r\033[K{next(_spinner_cycle)} {display}", end="", file=sys.stderr)
    except (OSError, UnicodeEncodeError):
        pass


def _clear_progress() -> None:
    width: int = _get_width()
    try:
        print("\r" + " " * width + "\r", end="", file=sys.stderr)
    except (OSError, UnicodeEncodeError):
        pass
_ALGORITHMS: dict[str, Callable[[], Any]] = {
    "md5": hashlib.md5,
    "sha256": hashlib.sha256,
}


@dataclass
class Options:
    recursive: bool = False
    follow_links: bool = False
    verbose: bool = False
    check_atime: bool = False
    check_ctime: bool = False
    ignore_mtime: bool = False
    ignore_size: bool = False
    show_same_files: bool = False
    ignore_hash: bool = False
    quiet: bool = False
    algorithm: str = "md5"
    exclude: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)


options: Options = Options()


def error(message: str) -> None:
    print(f"ERROR: {message}")


def _compute_hash(fileName: str, algorithm: str | None = None) -> str:
    algo = algorithm or options.algorithm
    if algo not in _ALGORITHMS:
        algo = "md5"
    try:
        h = _ALGORITHMS[algo]()
        try:
            file_size: int = os.path.getsize(fileName)
        except OSError:
            file_size = 0
        show_progress: bool = not options.quiet and not options.verbose and file_size > 1048576
        bytes_read: int = 0
        next_pct: int = 5
        with open(fileName, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
                if show_progress:
                    bytes_read += len(chunk)
                    new_pct: int = bytes_read * 100 // file_size
                    if new_pct >= next_pct:
                        _progress(f"{fileName} ({new_pct}%)")
                        next_pct = ((new_pct // 5) + 1) * 5
        return h.hexdigest()
    except (OSError, PermissionError, FileNotFoundError) as e:
        print(f"Error calculating {algo} for {fileName}: {e}")
        return "error"


def _compute_hash_batch(files_dict: dict[str, dict[str, Any]]) -> None:
    paths: list[str] = []
    keys: list[str] = []
    for key, info in files_dict.items():
        if info["hash"] == "" and info["hash"] != "<DIR>":
            paths.append(os.path.join(info["dirName"], info["fileName"]))
            keys.append(key)
    if not paths:
        return
    key_to_path: dict[str, str] = dict(zip(keys, paths))
    with ThreadPoolExecutor(max_workers=4) as executor:
        fut_to_key = {executor.submit(_compute_hash, p): k for p, k in zip(paths, keys)}
        for fut in as_completed(fut_to_key):
            key = fut_to_key[fut]
            try:
                files_dict[key]["hash"] = fut.result()
            except Exception:
                files_dict[key]["hash"] = "error"
            if not options.quiet and not options.verbose:
                _progress(key_to_path[key])


def shouldIgnore(filename: str) -> bool:
    name: str = Path(filename).name

    include_patterns: list[str] = options.include
    if include_patterns:
        for pattern in include_patterns:
            if fnmatch(name, pattern) or fnmatch(filename, pattern):
                return False

    if name in _IGNORE_EXACT:
        return True

    for pattern in _IGNORE_GLOB:
        if fnmatch(name, pattern):
            return True

    exclude_patterns: list[str] = options.exclude
    for pattern in exclude_patterns:
        if fnmatch(name, pattern) or fnmatch(filename, pattern):
            return True

    return False


def walkTree(
    top: str,
    callback: Callable[[str, Any], None],
    recursive: bool,
    followLink: bool,
    data: Any,
    beginDirCallback: Callable[[str], Any] | bool = False,
    endDirCallback: Callable[[str, Any], None] | bool = False,
    bfs: bool = False,
) -> None:
    top_path: Path = Path(top)
    if bfs:
        container: deque = deque([(top_path, data)])
        pop = container.popleft
    else:
        container = [(top_path, data)]
        pop = container.pop
    while container:
        dirPath: Path
        inheritedData: Any
        dirPath, inheritedData = pop()
        if callable(beginDirCallback):
            dirData: Any = beginDirCallback(str(dirPath))
        else:
            dirData = inheritedData
        try:
            entries: list[Path] = list(dirPath.iterdir())
        except (OSError, PermissionError):
            entries = []
        for entry in entries:
            if not shouldIgnore(entry.name):
                try:
                    st: os.stat_result = entry.lstat()
                    mode: int = st.st_mode
                except (OSError, PermissionError) as e:
                    _clear_progress()
                    print(f"cannot stat {entry}: {e}")
                    continue

                if stat.S_ISLNK(mode) and not followLink:
                    continue

                if stat.S_ISDIR(mode):
                    callback(str(entry), dirData)
                    if recursive:
                        container.append((entry, dirData))
                elif stat.S_ISREG(mode):
                    callback(str(entry), dirData)
                else:
                    _clear_progress()
                    print(f'Skipping {entry}')
        if callable(endDirCallback):
            endDirCallback(str(dirPath), dirData)


def filecheckNew(dirName: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    data["dirName"] = dirName
    data["files"] = {}
    return data


def filecheckSet(data: dict[str, Any], info: dict[str, Any]) -> None:
    data["files"][info["fileName"]] = info


def filecheckSave(data: dict[str, Any], dirName: str) -> None:
    dirName = data["dirName"]
    dbFile: Path = Path(dirName) / filecheckName
    tmpFile: Path = Path(dirName) / filecheckTempName
    try:
        with open(tmpFile, "w", encoding='utf-8') as f:
            f.write(f"FILECHECK:{version}:{signature}:{options.algorithm}{endline}")
            for fn, info in data["files"].items():
                line: str = f"{info['hash']}:{info['size']}:{info['ctime']:.10f}:{info['mtime']:.10f}:{info['atime']:.10f}:{info['fileName']}{endline}"
                f.write(line)
        os.replace(str(tmpFile), str(dbFile))
    except (OSError, PermissionError) as e:
        error(f"cannot save info for dir {dirName}: {e}")
        traceback.print_exc()


def filecheckLoad(dirName: str) -> dict[str, Any] | bool:
    fileName: Path = Path(dirName) / filecheckName
    res: dict[str, Any] = filecheckNew(dirName)
    res["algorithm"] = options.algorithm
    header: bool = False
    if not fileName.is_file():
        return res

    with open(fileName, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not header:
                headerFields: list[str] = line.split(":")
                if len(headerFields) < 3:
                    error("Invalid header")
                    return False
                h0: str = headerFields[0].lstrip("\ufeff")
                h1: str = headerFields[1]
                h2: str = headerFields[2]
                if h0 != "FILECHECK" or h1 not in _SUPPORTED_VERSIONS or h2 not in _SUPPORTED_SIGS:
                    error("Invalid header")
                    return False
                res["algorithm"] = headerFields[3].strip() if len(headerFields) > 3 else "md5"
                header = True
            else:
                lineFields: list[str] = line.split(":", 5)
                if len(lineFields) >= 6:
                    data: dict[str, Any] = {
                        'dirName': str(fileName.parent),
                        'fileName': lineFields[5],
                        'hash': lineFields[0],
                        'size': int(lineFields[1]),
                        'ctime': float(lineFields[2]),
                        'mtime': float(lineFields[3]),
                        'atime': float(lineFields[4])
                    }
                    res["files"][data["fileName"]] = data
    return res


def checkBegin(dirName: str) -> dict[str, Any]:
    if options.verbose:
        print(dirName)
    elif not options.quiet:
        _progress(dirName)
    return generateBegin(dirName)


def checkFile(fileName: str, data: dict[str, Any]) -> None:
    generateFileWithoutHash(fileName, data)


def compareData(current: dict[str, Any], saved: dict[str, Any], dirName: str) -> None:
    global check_exit_code, check_added, check_deleted, check_modified, check_same
    showSameFile: bool = options.show_same_files
    total: int = len(current["files"])
    for idx, (key, currentValue) in enumerate(current["files"].items()):
        if not options.quiet and not options.verbose:
            _progress(f"{dirName} [{idx+1}/{total}] {key}")
        status: str = "pending"
        if key not in saved["files"]:
            status = "new item"
        else:
            savedValue: dict[str, Any] = saved["files"][key]
            if currentValue["hash"] == "<DIR>" or savedValue["hash"] == "<DIR>":
                if currentValue["hash"] != savedValue["hash"]:
                    status = "directory mismatch"
                else:
                    status = "same file"
            elif not options.ignore_size and savedValue["size"] != currentValue["size"]:
                status = "size mismatch"
            elif not options.ignore_mtime and int(savedValue["mtime"]) != int(currentValue["mtime"]):
                status = "mtime mismatch"
            elif options.check_atime and int(savedValue["atime"]) != int(currentValue["atime"]):
                status = "atime mismatch"
            elif options.check_ctime and int(savedValue["ctime"]) != int(currentValue["ctime"]):
                status = "ctime mismatch"
            else:
                if not options.ignore_hash and currentValue["hash"] == "" and savedValue["hash"] != "":
                    saved_algo: str = saved.get("algorithm", "md5")
                    currentValue["hash"] = _compute_hash(
                        os.path.join(currentValue["dirName"], currentValue["fileName"]),
                        saved_algo
                    )

                if not options.ignore_hash and savedValue["hash"] != currentValue["hash"]:
                    status = "MD5 mismatch"
                else:
                    status = "same file"
            del saved["files"][key]
        if showSameFile or status != "same file":
            if not options.quiet and not options.verbose:
                _clear_progress()
            print(f"{status}: {os.path.join(dirName, key)}")
            if not options.quiet and not options.verbose:
                _progress(f"{dirName} [{idx+1}/{total}] {key}")
        if status in ("same file", "pending"):
            check_same += 1
        elif status in ("new item"):
            check_added += 1
        else:
            check_modified += 1
            check_exit_code += 1
    for key, savedValue in saved["files"].items():
        if not shouldIgnore(key):
            if not options.quiet and not options.verbose:
                _clear_progress()
            print(f"deleted file: {os.path.join(dirName, key)}")
            if not options.quiet and not options.verbose:
                _progress(f"{dirName} [deleted] {key}")
            check_exit_code += 1
            check_deleted += 1


def checkEnd(dirName: str, data: dict[str, Any]) -> None:
    if not options.quiet and not options.verbose:
        _clear_progress()
    savedData: dict[str, Any] | bool = filecheckLoad(dirName)
    compareData(data, savedData, dirName)


def generateBegin(dirName: str) -> dict[str, Any]:
    if options.verbose:
        print(dirName)
    elif not options.quiet:
        _progress(dirName)
    return filecheckNew(dirName)


def generateEnd(dirName: str, data: dict[str, Any]) -> None:
    _compute_hash_batch(data["files"])
    filecheckSave(data, dirName)


def generateFileWithoutHash(fileName: str, data: dict[str, Any]) -> None:
    _generateFile(fileName, data, False)


def generateFile(fileName: str, data: dict[str, Any]) -> None:
    _generateFile(fileName, data, _compute_hash)


def _generateFile(fileName: str, data: dict[str, Any], hashFunc: Callable[[str], str] | bool) -> None:
    if not options.quiet and not options.verbose:
        _progress(fileName)
    try:
        if not shouldIgnore(fileName):
            filecheckSet(data, makeInfo(fileName, hashFunc))
    except (OSError, PermissionError, FileNotFoundError) as e:
        error(f"cannot generate info for file {fileName}: {e}")


def makeInfo(fileName: str, hashFunc: Callable[[str], str] | bool = False) -> dict[str, Any] | None:
    path: Path = Path(fileName)
    if path.is_dir():
        hash_val: str = "<DIR>"
    else:
        hash_val = hashFunc(fileName) if callable(hashFunc) else ""

    try:
        stat_info: os.stat_result = path.stat()
        info: dict[str, Any] = {
            'dirName': str(path.parent),
            'fileName': path.name,
            'hash': hash_val,
            'size': stat_info.st_size,
            'ctime': getattr(stat_info, 'st_birthtime', 0) or stat_info.st_ctime,
            'mtime': stat_info.st_mtime,
            'atime': stat_info.st_atime
        }
        return info
    except (OSError, PermissionError, FileNotFoundError) as e:
        error(f"Error getting file info for {fileName}: {e}")
        return None


def updateBegin(dirName: str) -> dict[str, Any]:
    if options.verbose:
        print(dirName)
    elif not options.quiet:
        _progress(dirName)
    updateData: dict[str, Any] = {}
    updateData["old"] = filecheckLoad(dirName)
    updateData["new"] = filecheckNew(dirName)
    return updateData


def updateFile(fileName: str, data: dict[str, Any]) -> None:
    if not options.quiet and not options.verbose:
        _progress(fileName)
    generateFileWithoutHash(fileName, data["new"])
    baseName: str = Path(fileName).name
    newInfo: dict[str, Any] = data["new"]["files"][baseName]

    if baseName in data["old"]["files"]:
        oldInfo: dict[str, Any] = data["old"]["files"][baseName]
        changed: bool = False
        if not options.ignore_size and newInfo["size"] != oldInfo["size"]:
            _clear_progress()
            print("reason: size")
            changed = True
        elif options.check_ctime and int(newInfo["ctime"]) != int(oldInfo["ctime"]):
            _clear_progress()
            print("reason: ctime")
            changed = True
        elif options.check_atime and int(newInfo["atime"]) != int(oldInfo["atime"]):
            changed = True
        elif not options.ignore_mtime and int(newInfo["mtime"]) != int(oldInfo["mtime"]):
            _clear_progress()
            print("reason: mtime")
            changed = True
    else:
        changed = True

    if changed:
        _clear_progress()
        print(f"Regenerating {fileName}.")
        generateFile(fileName, data["new"])
    else:
        data["new"]["files"][baseName]["hash"] = oldInfo["hash"]


def updateEnd(dirName: str, data: dict[str, Any]) -> None:
    _compute_hash_batch(data["new"]["files"])
    filecheckSave(data["new"], dirName)


def generate(directory: str) -> None:
    print(f"GENERATE: {directory}")
    walkTree(directory, generateFileWithoutHash, options.recursive, options.follow_links, {}, generateBegin, generateEnd)
    if not options.quiet and not options.verbose:
        _clear_progress()


def update(directory: str) -> None:
    print(f"UPDATE: {directory}")
    walkTree(directory, updateFile, options.recursive, options.follow_links, {}, updateBegin, updateEnd)
    if not options.quiet and not options.verbose:
        _clear_progress()


def check(directory: str) -> int:
    global check_exit_code, check_added, check_deleted, check_modified, check_same
    check_exit_code = 0
    check_added = 0
    check_deleted = 0
    check_modified = 0
    check_same = 0
    print(f"CHECK: {directory}")
    walkTree(directory, checkFile, options.recursive, options.follow_links, {}, checkBegin, checkEnd, bfs=True)
    if not options.quiet:
        _clear_progress()
        total: int = check_added + check_deleted + check_modified + check_same
        print(f"Total: {total}  Added: {check_added}  Deleted: {check_deleted}  Modified: {check_modified}  Same: {check_same}")
    return check_exit_code


def _build_shared_parent() -> argparse.ArgumentParser:
    parent: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    parent.add_argument('-r', '--recursive', action='store_true', help='recurse into subdirectories')
    parent.add_argument('-l', '--follow-links', action='store_true', dest='follow_links', help='follow symbolic links')
    parent.add_argument('-A', '--algorithm', choices=list(_ALGORITHMS.keys()), default="md5",
                        help='hash algorithm (default: md5)')
    parent.add_argument('-a', '--check-atime', action='store_true', help='check access time')
    parent.add_argument('-c', '--check-ctime', action='store_true', help='check creation time')
    parent.add_argument('-M', '--ignore-mtime', action='store_true', help='ignore modification time')
    parent.add_argument('-S', '--ignore-size', action='store_true', help='ignore size')
    parent.add_argument('--exclude', action='append', default=[], dest='exclude',
                        help='exclude files matching pattern (can specify multiple)')
    parent.add_argument('--include', action='append', default=[], dest='include',
                        help='include files matching pattern (overrides exclude, can specify multiple)')
    return parent


def main(argv: list[str] | None = None) -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='Check file integrity')
    parser.add_argument('-v', '--verbose', action='store_true', help='display more info')
    subparsers = parser.add_subparsers(dest="command", help='command to execute')

    shared: argparse.ArgumentParser = _build_shared_parent()

    parser_generate = subparsers.add_parser('generate', parents=[shared], help='generate integrity files',
                                            conflict_handler='resolve')
    parser_generate.add_argument('directory', nargs='?', default=".", help='directory to generate (defaults to current dir)')

    parser_update = subparsers.add_parser('update', parents=[shared], help='update integrity files',
                                          conflict_handler='resolve')
    parser_update.add_argument('directory', nargs='?', default=".", help='directory to update (defaults to current dir)')

    parser_check = subparsers.add_parser('check', parents=[shared], help='check integrity of files',
                                         conflict_handler='resolve')
    parser_check.add_argument('directory', nargs='?', default=".", help='directory to check (defaults to current dir)')
    parser_check.add_argument('-s', '--show-same-files', action='store_true', help='show files that are the same')
    parser_check.add_argument('-H', '--ignore-hash', action='store_true', help='ignore hash (contents)')
    parser_check.add_argument('-q', '--quiet', action='store_true', help='suppress summary output')

    args = parser.parse_args(argv)
    global options
    for fld in options.__dataclass_fields__:
        if hasattr(args, fld):
            setattr(options, fld, getattr(args, fld))

    if args.command is None:
        parser.print_help()
    else:
        try:
            directory: str = args.directory if hasattr(args, 'directory') else "."
            ret: Any = globals()[args.command](directory)
            if isinstance(ret, int):
                sys.exit(ret)
        except KeyboardInterrupt:
            _clear_progress()
            print("\nOperation cancelled by user")
            sys.exit(1)
        except Exception as e:
            error(f"Error: {e}")
            if options.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv[1:])
