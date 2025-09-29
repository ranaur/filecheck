#!/usr/bin/env python3
import traceback
import sys
import argparse
import os
import stat
import hashlib
from fnmatch import fnmatch

version="0.1"
# LONG RIGHTWARDS DOUBLE ARROW (U+27F9)   e29fb9
signature = b"\xe2\x9f\xb9".decode('utf-8')

options = {}
filecheckName = ".filecheck"
filecheckTempName = ".filecheck.tmp"
ignoreFiles = [filecheckName, filecheckTempName, ".git", "._Icon*", "Icon*", ".DS_Store"]

def error(message):
    print(f"ERROR: {message}")

def md5(fileName):
    #print(f"executing md5 {fileName}")
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
    fileName = os.path.basename(filename)
    for pattern in ignoreFiles:
        if fnmatch(fileName, pattern):
            return True
    return False

def walkTree(top, callback, recursive, followLink, data, beginDirCallback=False, endDirCallback=False):
    if callable(beginDirCallback):
        data = beginDirCallback(top)
    for f in os.listdir(top):
        if not shouldIgnore(f):
            pathname = os.path.join(top, f)

            try:
                mode = os.lstat(pathname).st_mode
            except Exception as e:
                print(f"cannot stat {pathname}: {e}")
                continue
                
            if stat.S_ISLNK(mode) and not followLink:
                continue
            
            if stat.S_ISDIR(mode):
                # also save DIRs
                callback(pathname, data)
                if recursive:
                    # It's a directory, recurse into it
                    walkTree(pathname, callback, recursive, followLink, data, beginDirCallback, endDirCallback)
            elif stat.S_ISREG(mode):
                # It's a file, call the callback function
                callback(pathname, data)
            else:
                # Unknown file type, print a message
                print(f'Skipping {pathname}')
    if callable(endDirCallback):
        endDirCallback(top, data)


def filecheckNew(dirName):
    data = {}
    data["dirName"] = dirName
    data["files"] = {}
    return data

def filecheckSet(data, info):
    data["files"][info["fileName"]] = info

def filecheckSave(data, dirName):
    dirName = data["dirName"]
    dbFile = os.path.join(dirName, filecheckName)

    try:
        if os.path.isfile(dbFile):
            os.unlink(dbFile)
        if len(data["files"]) > 0:
            with open(dbFile, "a+t", encoding='utf-8') as f:
                f.write(f"\ufeffFILECHECK:{version}:{signature}\r\r\n")
                for fn, info in data["files"].items():
                    line=f"{info['hash']}:{info['size']}:{info['ctime']:.10f}:{info['mtime']:.10f}:{info['atime']:.10f}:{info['fileName']}\r\r\n"
                    f.write(line)
    except Exception as e:
        error(f"cannot save info for dir {dirName}: {e}")
        traceback.print_exc() # Prints the full exception traceback

def filecheckLoad(dirName):
    fileName = os.path.join(dirName, filecheckName)
    res = filecheckNew(dirName)
    header = False
    if not os.path.isfile(fileName):
        return res

    with open(fileName, "rt", encoding="utf-8") as f:
        for line in f:
            if not header:
                headerFields = line.strip().split(":")
                if len(headerFields) < 3 or \
                   headerFields[0] != "\ufeffFILECHECK" or \
                   headerFields[1] != version or \
                   headerFields[2] != signature:
                    error("Invalid header")
                    return False
                header = True
            else:
                lineFields = line.strip().split(":", 5)
                if len(lineFields) >= 6:
                    data = {
                        'dirName': os.path.dirname(fileName),
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
    if options['verbose']:
        print(dirName)
    return generateBegin(dirName)

def checkFile(fileName, data):
    generateFileWithoutHash(fileName, data)

def compareData(current, saved, dirName):
    showSameFile = options["show_same_files"]
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
            elif not options["ignore_size"] and savedValue["size"] != currentValue["size"]:
                status = "size mismatch"
            elif not options["ignore_mtime"] and int(savedValue["mtime"]) != int(currentValue["mtime"]):
                status = "mtime mismatch"
            elif options["check_atime"] and int(savedValue["atime"]) != int(currentValue["atime"]):
                status = "atime mismatch"
            elif options["check_ctime"] and int(savedValue["ctime"]) != int(currentValue["ctime"]):
                status = "ctime mismatch"
            else:
                if not options["ignore_hash"] and currentValue["hash"] == "" and savedValue["hash"] != "":
                    currentValue["hash"] = md5(os.path.join(currentValue["dirName"], currentValue["fileName"]))

                if not options["ignore_hash"] and savedValue["hash"] != currentValue["hash"]:
                    status = "MD5 mismatch"
                else:
                    status = "same file"
            del saved["files"][key]
        if showSameFile or status != "same file":
            print(f"{status}: {os.path.join(dirName, key)}")
    for key, savedValue in saved["files"].items():
        if not shouldIgnore(key):
            print(f"deleted file: {os.path.join(dirName, key)}")

def checkEnd(dirName, data):
    savedData = filecheckLoad(dirName)
    compareData(data, savedData, dirName)

def generateBegin(dirName):
    if options['verbose']:
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
    if os.path.isdir(fileName):
        hash_val = "<DIR>"
    else:
        hash_val = hashFunc(fileName) if callable(hashFunc) else ""
    
    try:
        stat_info = os.stat(fileName)
        info = {
            'dirName': os.path.dirname(fileName),
            'fileName': os.path.basename(fileName),
            'hash': hash_val,
            'size': stat_info.st_size,
            'ctime': stat_info.st_birthtime or stat_info.st_ctime,
            'mtime': stat_info.st_mtime,
            'atime': stat_info.st_atime
        }
        return info
    except Exception as e:
        error(f"Error getting file info for {fileName}: {e}")
        return None

def updateBegin(dirName):
    if options['verbose']:
        print(dirName)
    updateData = {}
    updateData["old"] = filecheckLoad(dirName)
    updateData["new"] = filecheckNew(dirName)
    return updateData

def updateFile(fileName, data):
    generateFileWithoutHash(fileName, data["new"])
    baseName = os.path.basename(fileName)
    newInfo = data["new"]["files"][baseName]
    
    if baseName in data["old"]["files"]:
        oldInfo = data["old"]["files"][baseName]
        changed = False
        if not options["ignore_size"] and newInfo["size"] != oldInfo["size"]:
            print("reason: size")
            changed = True
        elif options["check_ctime"] and int(newInfo["ctime"]) != int(oldInfo["ctime"]):
            print("reason: ctime")
            changed = True
        elif options["check_atime"] and int(newInfo["atime"]) != int(oldInfo["atime"]):
            changed = True
        elif not options["ignore_mtime"] and int(newInfo["mtime"]) != int(oldInfo["mtime"]):
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
    walkTree(directory, generateFile, options["recursive"], options["follow_links"], {}, generateBegin, generateEnd)

def update(directory):
    print(f"UPDATE: {directory}")
    walkTree(directory, updateFile, options["recursive"], options["follow_links"], {}, updateBegin, updateEnd)

def check(directory):
    print(f"CHECK: {directory}")
    walkTree(directory, checkFile, options["recursive"], options["follow_links"], {}, checkBegin, checkEnd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check file integrity')
    parser.add_argument('-v', '--verbose', action='store_true', help='display more info')
    subparsers = parser.add_subparsers(dest="command", help='command to execute')

    # Generate subcommand
    parser_generate = subparsers.add_parser('generate', help='generate integrity files')
    parser_generate.add_argument('directory', nargs='?', default=".", help='directory to generate (defaults to current dir)')
    parser_generate.add_argument('-r', '--recursive', action='store_true', help='recurse into subdirectories')
    parser_generate.add_argument('-l', '--follow-links', action='store_true', dest='follow_links', help='follow symbolic links')

    # Update subcommand
    parser_update = subparsers.add_parser('update', help='update integrity files')
    parser_update.add_argument('directory', nargs='?', default=".", help='directory to update (defaults to current dir)')
    parser_update.add_argument('-r', '--recursive', action='store_true', help='recurse into subdirectories')
    parser_update.add_argument('-l', '--follow-links', action='store_true', dest='follow_links', help='follow symbolic links')
    parser_update.add_argument('-a', '--check-atime', action='store_true', help='check access time')
    parser_update.add_argument('-c', '--check-ctime', action='store_true', help='check creation time')
    parser_update.add_argument('-M', '--ignore-mtime', action='store_true', help='ignore modification time')
    parser_update.add_argument('-S', '--ignore-size', action='store_true', help='ignore size')

    # Check subcommand
    parser_check = subparsers.add_parser('check', help='check integrity of files')
    parser_check.add_argument('directory', nargs='?', default=".", help='directory to check (defaults to current dir)')
    parser_check.add_argument('-r', '--recursive', action='store_true', help='recurse into subdirectories')
    parser_check.add_argument('-l', '--follow-links', action='store_true', dest='follow_links', help='follow symbolic links')
    parser_check.add_argument('-s', '--show-same-files', action='store_true', help='show files that are the same')
    parser_check.add_argument('-a', '--check-atime', action='store_true', help='check access time')
    #parser_check.add_argument('-A', '--ignore-atime', action='store_true', help='ignore access time')
    parser_check.add_argument('-c', '--check-ctime', action='store_true', help='check creation time')
    #parser_check.add_argument('-C', '--ignore-ctime', action='store_true', help='ignore creation time')
    parser_check.add_argument('-M', '--ignore-mtime', action='store_true', help='ignore modification time')
    parser_check.add_argument('-S', '--ignore-size', action='store_true', help='ignore size')
    parser_check.add_argument('-H', '--ignore-hash', action='store_true', help='ignore hash (contents)')

    args = parser.parse_args()
    options = vars(args)
    
    # Set default values for options that might not be present in all subcommands
    for opt in ['recursive', 'follow_links', 'check_atime', 'check_ctime', 
                'ignore_mtime', 'ignore_size', 'show_same_files', 'ignore_hash']:
        options.setdefault(opt, False)
    
    if args.command is None:
        parser.print_help()
    else:
        try:
            globals()[args.command](options["directory"])
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            sys.exit(1)
        except Exception as e:
            error(f"Error: {e}")
            if options.get('verbose'):
                import traceback
                traceback.print_exc()
            sys.exit(1)
