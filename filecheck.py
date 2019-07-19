#/usr/bin/env python2
version="0.1"
# LONG RIGHTWARDS DOUBLE ARROW (U+27F9)   e29fb9
signature = "\xe2\x9f\xb9";

import argparse
import os
import stat
import hashlib
from fnmatch import fnmatch

options = {}
filecheckName = ".filecheck"
filecheckTempName = ".filecheck.tmp"
ignoreFiles = [filecheckName, filecheckTempName, ".git"]

def error(message):
    print "ERROR: %s" % message

def md5(fileName):
    #print "executing md5 %s" % fileName
    hash_md5 = hashlib.md5()
    try:
        with open(fileName, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
    
        return hash_md5.hexdigest()
    except:
    	return "error"

def shouldIgnore(filename):
    fileName = os.path.basename(filename)
    for pattern in ignoreFiles:
        if fnmatch(fileName, pattern):
            return True
    return False

def walkTree(top, callback, recursive, followLink, data, beginDirCallback = False, endDirCallback = False):
    if callable(beginDirCallback):
        data = beginDirCallback(top)
    for f in os.listdir(top):
        if not shouldIgnore(f):
            pathname = os.path.join(top, f)

            try:
                mode = os.lstat(pathname).st_mode
            except:
                print "cannot stat %s" % pathname
                continue
            if stat.S_ISLNK(mode):
                continue
            
            if stat.S_ISDIR(mode):
                if recursive:
                    # It's a directory, recurse into it
                    walkTree(pathname, callback, recursive, followLink, data, beginDirCallback, endDirCallback)
            elif stat.S_ISREG(mode):
                # It's a file, call the callback function
                    callback(pathname, data)
            else:
                # Unknown file type, print a message
                print 'Skipping %s' % pathname
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

        with open(dbFile, "a+t") as f:
            f.write("%s%s:%s:%s\r\n" % ("\xef\xbb\xbf", "FILECHECK", version, signature ))
        
            for fn, info in data["files"].items():
                f.write("%s:%ld:%.10f:%.10f:%.10f:%s\r\n" % (info["hash"], info["size"], info["ctime"], info["mtime"], info["atime"], info["fileName"] ))
    except Exception as e:
        error("cannot save info for dir %s: %s" % (filecheckDirName, str(e)))

def filecheckLoad(dirName):
    #print "loadFilecheck(%s)" % dirName
    fileName = os.path.join(dirName, filecheckName)
    res = filecheckNew(dirName)
    header = False
    if not os.path.isfile(fileName):
        return res

    with open(fileName, "rt") as f:
        for line in f:
            if not header:
                headerFields = line.split(":")
                if headerFields[0] != "\xef\xbb\xbfFILECHECK" or \
                    headerFields[1] != version or \
                    headerFields[2] != signature + '\r\n':
                    error("Invalid header")
                    return False
                header = True
            else:
                lineFields = line.split(":")
                data = {
                    'dirName': os.path.dirname(fileName),
                    'fileName': lineFields[5].rstrip("\n\r"),
                    'hash': lineFields[0],
                    'size': int(lineFields[1]),
                    'ctime': float(lineFields[2]),
                    'mtime': float(lineFields[3]),
                    'atime': float(lineFields[4])
                }
                res["files"][data["fileName"]] = data
    # print res
    return res

def checkBegin(dirName):
    return generateBegin(dirName)

def checkFile(fileName, data):
    generateFileWithoutHash(fileName, data)

def compareData(current, saved, dirName):
    #print "CURRENT"
    #print current
    #print "SAVED"
    #print saved
    showSameFile = options["show_same_files"]
    for key, currentValue in current["files"].iteritems():
        status = "pending"
        if not saved["files"].has_key(key):
            status = "new item"
        else:
            savedValue = saved["files"][key]
            if not options["ignore_size"] and savedValue["size"] != currentValue["size"]:

                status = "size mismatch"
            elif not options["ignore_mtime"] and savedValue["mtime"] != currentValue["mtime"]:
                #print "saved %s / current %s" % (type(savedValue["mtime"]), type(currentValue["mtime"]))
                #print "saved %s / current %s" % (savedValue["mtime"], currentValue["mtime"])
                status = "mtime mismatch"
            elif not options["ignore_atime"] and savedValue["atime"] != currentValue["atime"]:
                status = "atime mismatch"
            elif not options["ignore_ctime"] and savedValue["ctime"] != currentValue["ctime"]:
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
            print "%s: %s" % (status, os.path.join(dirName, key))
    for key, savedValue in saved["files"].iteritems():
        print "%s: %s" % ("deleted file", os.path.join(dirName, key))
 
def checkEnd(dirName, data):
    #print "checkEnd(%s)" % dirName
    savedData = filecheckLoad(dirName)

    #print "SAVED DATA"
    #print savedData
    #print "FILECHECK DATA"
    #print filecheckData
    compareData(data, savedData, dirName)

def generateBegin(dirName):
    #print "generateBegin %s" % dirName
    return filecheckNew(dirName)


def generateEnd(dirName, data):
    #print "generateEnd %s" % dirName
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
        error("cannot generate info for file %s: %s" % (fileName, str(e)))

def makeInfo(fileName, hashFunc = False):
    info = {
        'dirName': os.path.dirname(fileName),
        'fileName': os.path.basename(fileName),
        'hash': hashFunc(fileName) if callable(hashFunc) else "",
        'size': os.path.getsize(fileName),
        'ctime': os.path.getctime(fileName),
        'mtime': os.path.getmtime(fileName),
        'atime': os.path.getatime(fileName)
    }
    return info

def updateBegin(dirName):
    updateData = {}
    updateData["old"] = filecheckLoad(dirName)
    updateData["new"] = filecheckNew(dirName)
    return updateData 

def updateFile(fileName, data):
    #print data
    generateFileWithoutHash(fileName, data["new"])
    baseName = os.path.basename(fileName)
    newInfo = data["new"]["files"][baseName]
    if data["old"]["files"].has_key(baseName):
        oldInfo = data["old"]["files"][baseName]

        changed = False
        if newInfo["size"] != oldInfo["size"]:
            changed = True
        elif newInfo["ctime"] != oldInfo["ctime"]:
            changed = True
        elif newInfo["atime"] != oldInfo["atime"]:
            changed = True
        elif newInfo["mtime"] != oldInfo["mtime"]:
            changed = True
    else:
        changed = True
    if changed:
        print "Regenerating %s." % fileName
        generateFile(fileName, data["new"])
    else:
        print "File %s not changed. Skipped." % fileName

def updateEnd(dirName, data):
    filecheckSave(data["new"], dirName)

def generate(directory):
    print "GENERATE: " + directory
    walkTree(directory, generateFile, options["recursive"], options["follow_links"], {}, generateBegin, generateEnd)

def update(directory):
    print "UPDATE: " + directory
    walkTree(directory, updateFile, options["recursive"], options["follow_links"], {}, updateBegin, updateEnd)

def check(directory):
    print "CHECK: " + directory
    walkTree(directory, checkFile, options["recursive"], options["follow_links"], {}, checkBegin, checkEnd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check file integrity')
    subparsers = parser.add_subparsers(dest="command", help='command to execute')

    parser_generate = subparsers.add_parser('generate',  help='generate integrity files')
    parser_generate.add_argument('directory', nargs='?', default=".", help='directory to generate (defaults to current dir)')
    parser_generate.add_argument('-r', '--recursive', action='store_true', help='recurse into subdirectories')
    parser_generate.add_argument('-l', '--follow-links', action='store_true', help='follow symboly links')

    parser_generate = subparsers.add_parser('update',  help='update integrity files')
    parser_generate.add_argument('directory', nargs='?', default=".", help='directory to generate (defaults to current dir)')
    parser_generate.add_argument('-r', '--recursive', action='store_true', help='recurse into subdirectories')
    parser_generate.add_argument('-l', '--follow-links', action='store_true', help='follow symboly links')

    parser_check = subparsers.add_parser('check', help='check integrity of files')
    parser_check.add_argument('directory', nargs='?', default=".", help='directory to check (defaults to current dir)')
    parser_check.add_argument('-r', '--recursive', action='store_true', help='recurse into subdirectories')
    parser_check.add_argument('-l', '--follow-links', action='store_true', help='follow symboly links')
    parser_check.add_argument('-s', '--show-same-files', action='store_true', help='show files that are the same')
    parser_check.add_argument('-A', '--ignore-atime', action='store_true', help='ignore access time')
    parser_check.add_argument('-C', '--ignore-ctime', action='store_true', help='ignore creation time')
    parser_check.add_argument('-M', '--ignore-mtime', action='store_true', help='ignore modification time')
    parser_check.add_argument('-S', '--ignore-size', action='store_true', help='ignore size')
    parser_check.add_argument('-H', '--ignore-hash', action='store_true', help='ignore hash (contents)')

    options = vars(parser.parse_args())
    globals()[options.pop('command')](options["directory"])


