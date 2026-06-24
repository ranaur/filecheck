#!/usr/bin/env python3
import traceback
import sys
import argparse
import os
import stat
import hashlib
from fnmatch import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

version = "0.1"
signature = "\xe2\x9f\xb9"
endline = "\n"

filecheckName = ".filecheck"
filecheckTempName = ".filecheck.tmp"
ignoreFiles = [filecheckName, filecheckTempName, ".git", "._Icon*", "Icon*", ".DS_Store"]

check_exit_code = 0


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
    exclude: list = field(default_factory=list)
    include: list = field(default_factory=list)


options = Options()


def error(message):
    print(f"ERROR: {message}")


def md5(fileName):
    hash_md5 = hashlib.md5()
    try:
        with open(fileName, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Error calculating MD5 for {fileName}: {e}")
        return "error"


def shouldIgnore(filename):
    name = Path(filename).name

    include_patterns = options.include
    if include_patterns:
        for pattern in include_patterns:
            if fnmatch(name, pattern) or fnmatch(filename, pattern):
                return False

    for pattern in ignoreFiles:
        if fnmatch(name, pattern):
            return True

    exclude_patterns = options.exclude
    for pattern in exclude_patterns:
        if fnmatch(name, pattern) or fnmatch(filename, pattern):
            return True

    return False


def walkTree(top, callback, recursive, followLink, data, beginDirCallback=False, endDirCallback=False):
    top_path = Path(top)
    stack = [(top_path, data)]
    while stack:
        dirPath, inheritedData = stack.pop()
        if callable(beginDirCallback):
            dirData = beginDirCallback(str(dirPath))
        else:
            dirData = inheritedData
        try:
            entries = list(dirPath.iterdir())
        except Exception:
            entries = []
        for entry in entries:
            if not shouldIgnore(entry.name):
                try:
                    st = entry.lstat()
                    mode = st.st_mode
                except Exception as e:
                    print(f"cannot stat {entry}: {e}")
                    continue

                if stat.S_ISLNK(mode) and not followLink:
                    continue

                if stat.S_ISDIR(mode):
                    callback(str(entry), dirData)
                    if recursive:
                        stack.append((entry, dirData))
                elif stat.S_ISREG(mode):
                    callback(str(entry), dirData)
                else:
                    print(f'Skipping {entry}')
        if callable(endDirCallback):
            endDirCallback(str(dirPath), dirData)


def filecheckNew(dirName):
    data = {}
    data["dirName"] = dirName
    data["files"] = {}
    return data


def filecheckSet(data, info):
    data["files"][info["fileName"]] = info


def filecheckSave(data, dirName):
    dirName = data["dirName"]
    dbFile = Path(dirName) / filecheckName
    tmpFile = Path(dirName) / filecheckTempName
    try:
        with open(tmpFile, "w", encoding='utf-8') as f:
            f.write(f"\ufeffFILECHECK:{version}:{signature}{endline}")
            for fn, info in data["files"].items():
                line = f"{info['hash']}:{info['size']}:{info['ctime']:.10f}:{info['mtime']:.10f}:{info['atime']:.10f}:{info['fileName']}{endline}"
                f.write(line)
        os.replace(str(tmpFile), str(dbFile))
    except Exception as e:
        error(f"cannot save info for dir {dirName}: {e}")
        traceback.print_exc()


def filecheckLoad(dirName):
    fileName = Path(dirName) / filecheckName
    res = filecheckNew(dirName)
    header = False
    if not fileName.is_file():
        return res

    with open(fileName, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not header:
                headerFields = line.split(":")
                if len(headerFields) < 3 or \
                   headerFields[0] != "\ufeffFILECHECK" or \
                   headerFields[1] != version or \
                   headerFields[2] != signature:
                    error("Invalid header")
                    return False
                header = True
            else:
                lineFields = line.split(":", 5)
                if len(lineFields) >= 6:
                    data = {
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


def checkBegin(dirName):
    if options.verbose:
        print(dirName)
    return generateBegin(dirName)


def checkFile(fileName, data):
    generateFileWithoutHash(fileName, data)


def compareData(current, saved, dirName):
    global check_exit_code
    showSameFile = options.show_same_files
    for key, currentValue in current["files"].items():
        status = "pending"
        if key not in saved["files"]:
            status = "new item"
        else:
            savedValue = saved["files"][key]
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
                    currentValue["hash"] = md5(os.path.join(currentValue["dirName"], currentValue["fileName"]))

                if not options.ignore_hash and savedValue["hash"] != currentValue["hash"]:
                    status = "MD5 mismatch"
                else:
                    status = "same file"
            del saved["files"][key]
        if showSameFile or status != "same file":
            print(f"{status}: {os.path.join(dirName, key)}")
        if status not in ("same file", "pending"):
            check_exit_code += 1
    for key, savedValue in saved["files"].items():
        if not shouldIgnore(key):
            print(f"deleted file: {os.path.join(dirName, key)}")
            check_exit_code += 1


def checkEnd(dirName, data):
    savedData = filecheckLoad(dirName)
    compareData(data, savedData, dirName)


def generateBegin(dirName):
    if options.verbose:
        print(dirName)
    return filecheckNew(dirName)


def generateEnd(dirName, data):
    filecheckSave(data, dirName)


def generateFileWithoutHash(fileName, data):
    _generateFile(fileName, data, False)


def generateFile(fileName, data):
    _generateFile(fileName, data, md5)


def _generateFile(fileName, data, hashFunc):
    try:
        if not shouldIgnore(fileName):
            filecheckSet(data, makeInfo(fileName, hashFunc))
    except Exception as e:
        error(f"cannot generate info for file {fileName}: {e}")


def makeInfo(fileName, hashFunc=False):
    path = Path(fileName)
    if path.is_dir():
        hash_val = "<DIR>"
    else:
        hash_val = hashFunc(fileName) if callable(hashFunc) else ""

    try:
        stat_info = path.stat()
        info = {
            'dirName': str(path.parent),
            'fileName': path.name,
            'hash': hash_val,
            'size': stat_info.st_size,
            'ctime': getattr(stat_info, 'st_birthtime', 0) or stat_info.st_ctime,
            'mtime': stat_info.st_mtime,
            'atime': stat_info.st_atime
        }
        return info
    except Exception as e:
        error(f"Error getting file info for {fileName}: {e}")
        return None


def updateBegin(dirName):
    if options.verbose:
        print(dirName)
    updateData = {}
    updateData["old"] = filecheckLoad(dirName)
    updateData["new"] = filecheckNew(dirName)
    return updateData


def updateFile(fileName, data):
    generateFileWithoutHash(fileName, data["new"])
    baseName = Path(fileName).name
    newInfo = data["new"]["files"][baseName]

    if baseName in data["old"]["files"]:
        oldInfo = data["old"]["files"][baseName]
        changed = False
        if not options.ignore_size and newInfo["size"] != oldInfo["size"]:
            print("reason: size")
            changed = True
        elif options.check_ctime and int(newInfo["ctime"]) != int(oldInfo["ctime"]):
            print("reason: ctime")
            changed = True
        elif options.check_atime and int(newInfo["atime"]) != int(oldInfo["atime"]):
            changed = True
        elif not options.ignore_mtime and int(newInfo["mtime"]) != int(oldInfo["mtime"]):
            print("reason: mtime")
            changed = True
    else:
        changed = True

    if changed:
        print(f"Regenerating {fileName}.")
        generateFile(fileName, data["new"])
    else:
        data["new"]["files"][baseName]["hash"] = oldInfo["hash"]


def updateEnd(dirName, data):
    filecheckSave(data["new"], dirName)


def generate(directory):
    print(f"GENERATE: {directory}")
    walkTree(directory, generateFile, options.recursive, options.follow_links, {}, generateBegin, generateEnd)


def update(directory):
    print(f"UPDATE: {directory}")
    walkTree(directory, updateFile, options.recursive, options.follow_links, {}, updateBegin, updateEnd)


def check(directory):
    global check_exit_code
    check_exit_code = 0
    print(f"CHECK: {directory}")
    walkTree(directory, checkFile, options.recursive, options.follow_links, {}, checkBegin, checkEnd)
    return check_exit_code


def _build_shared_parent():
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument('-r', '--recursive', action='store_true', help='recurse into subdirectories')
    parent.add_argument('-l', '--follow-links', action='store_true', dest='follow_links', help='follow symbolic links')
    parent.add_argument('-a', '--check-atime', action='store_true', help='check access time')
    parent.add_argument('-c', '--check-ctime', action='store_true', help='check creation time')
    parent.add_argument('-M', '--ignore-mtime', action='store_true', help='ignore modification time')
    parent.add_argument('-S', '--ignore-size', action='store_true', help='ignore size')
    parent.add_argument('--exclude', action='append', default=[], dest='exclude',
                        help='exclude files matching pattern (can specify multiple)')
    parent.add_argument('--include', action='append', default=[], dest='include',
                        help='include files matching pattern (overrides exclude, can specify multiple)')
    return parent


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check file integrity')
    parser.add_argument('-v', '--verbose', action='store_true', help='display more info')
    subparsers = parser.add_subparsers(dest="command", help='command to execute')

    shared = _build_shared_parent()

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

    args = parser.parse_args(argv)
    global options
    for fld in options.__dataclass_fields__:
        if hasattr(args, fld):
            setattr(options, fld, getattr(args, fld))

    if args.command is None:
        parser.print_help()
    else:
        try:
            directory = args.directory if hasattr(args, 'directory') else "."
            ret = globals()[args.command](directory)
            if isinstance(ret, int):
                sys.exit(ret)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            sys.exit(1)
        except Exception as e:
            error(f"Error: {e}")
            if options.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
