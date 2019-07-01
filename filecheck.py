#/usr/bin/env python2
version="0.1"
# LONG RIGHTWARDS DOUBLE ARROW (U+27F9)   e29fb9
signature = "\xe2\x9f\xb9";

import argparse
import os
import stat
import hashlib
options = {}

def md5(fileName):
    #print "executing md5 %s" % fileName
    hash_md5 = hashlib.md5()
    with open(fileName, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def walkTree(top, callback, recursive, followLink, beginDirCallback = False, endDirCallback = False):
    if callable(beginDirCallback):
        beginDirCallback(top)
    for f in os.listdir(top):
        pathname = os.path.join(top, f)
        mode = os.stat(pathname).st_mode
        if stat.S_ISDIR(mode):
            if recursive:
                # It's a directory, recurse into it
                walkTree(pathname, callback, recursive, followLink, beginDirCallback, endDirCallback)
        elif stat.S_ISREG(mode):
            # It's a file, call the callback function
            callback(pathname)
        elif stat.S_ISLNK(mode):
            if followLink:
                callback(pathname)
        else:
            # Unknown file type, print a message
            print 'Skipping %s' % pathname
    if callable(endDirCallback):
        endDirCallback(top)

def save(info):
    dirName = info["dirName"]
    dbFile = os.path.join(dirName, ".filecheck.tmp")
    with open(dbFile, "a+t") as f:
        f.write("%s:%d:%d:%d:%d:%s\r\n" % (info["md5"], info["size"], info["ctime"], info["mtime"], info["atime"], info["fileName"] ))

def checkBegin(dirName):
    generateBegin(dirName)

def checkFile(fileName):
    generateFileWithoutHash(fileName)

def compareData(current, saved):
    showSameFile = options["show_same_files"]
    for key, currentValue in current.iteritems():
        status = "pending"
        if not saved.has_key(key):
            status = "new item"
        else:
            savedValue = saved[key]
            if not options["ignore_size"] and savedValue["size"] != currentValue["size"]:
                status = "size mismatch"
            elif not options["ignore_mtime"] and savedValue["mtime"] != currentValue["mtime"]:
                status = "mtime mismatch"
            elif not options["ignore_atime"] and savedValue["atime"] != currentValue["atime"]:
                status = "atime mismatch"
            elif not options["ignore_ctime"] and savedValue["ctime"] != currentValue["ctime"]:
                status = "ctime mismatch"
            else:
                if not options["ignore_hash"] and currentValue["md5"] == "" and savedValue["md5"] != "":
                    currentValue["md5"] = md5(os.path.join(currentValue["dirName"], currentValue["fileName"]))

                if not options["ignore_hash"] and savedValue["md5"] != currentValue["md5"]:
                    status = "MD5 mismatch"
                else:
                    status = "same file"
            del saved[key]
        if showSameFile or status != "same file":
            print "%s: %s" % (status, key)
    for key, savedValue in saved.iteritems():
        print "%s: %s" % ("deleted file", key)
 
def error(message):
    print "ERROR: %s" % message

def loadFilecheck(fileName):
    #print "loadFilecheck(%s)" % fileName
    res = {}
    header = False
    if not os.path.isfile(fileName):
        return {}

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
                    'md5': lineFields[0],
                    'size': lineFields[1],
                    'ctime': lineFields[2],
                    'mtime': lineFields[3],
                    'atime': lineFields[4]
                }
                res[data["fileName"]] = data
    return res

def checkEnd(dirName):
    currentFile = os.path.join(dirName, ".filecheck.tmp")
    currentData = loadFilecheck(currentFile)
    savedData = loadFilecheck(os.path.join(dirName, ".filecheck"))

    #print currentData
    #print savedData
    compareData(currentData, savedData)

    os.unlink(currentFile)

def generateBegin(dirName):
    #print "generateBegin %s" % dirName
    dbFile = os.path.join(dirName, ".filecheck.tmp")

    if os.path.isfile(dbFile):
        os.unlink(dbFile)

    with open(dbFile, "a+t") as f:
        f.write("%s%s:%s:%s\r\n" % ("\xef\xbb\xbf", "FILECHECK", version, signature ))

def generateEnd(dirName):
    #print "generateEnd %s" % dirName
    dbFile = os.path.join(dirName, ".filecheck.tmp")
    dbDefFile = os.path.join(dirName, ".filecheck")
    os.rename(dbFile, dbDefFile)

def generateFileWithoutHash(filename):
    fileName = os.path.basename(filename)
    #print "XXX %s" % fileName
    if fileName != ".filecheck" and fileName != ".filecheck.tmp":
        info = {
            'dirName': os.path.dirname(filename),
            'fileName': fileName,
            'md5': "",
            'size': os.path.getsize(filename),
            'ctime': os.path.getctime(filename),
            'mtime': os.path.getmtime(filename),
            'atime': os.path.getatime(filename)
        }
        save(info)

def generateFile(filename):
    fileName = os.path.basename(filename)
    #print "XXX %s" % fileName
    if fileName != ".filecheck" and fileName != ".filecheck.tmp":
        info = {
            'dirName': os.path.dirname(filename),
            'fileName': fileName,
            'md5': md5(filename),
            'size': os.path.getsize(filename),
            'ctime': os.path.getctime(filename),
            'mtime': os.path.getmtime(filename),
            'atime': os.path.getatime(filename)
        }
        save(info)

def generate(directory):
    print "GENERATE: " + directory
    walkTree(directory, generateFile, options["recursive"], options["follow_links"], generateBegin, generateEnd)

def check(directory):
    print "CHECK: " + directory
    walkTree(directory, checkFile, options["recursive"], options["follow_links"], checkBegin, checkEnd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check file integrity')
    subparsers = parser.add_subparsers(dest="command", help='command to execute')

    parser_generate = subparsers.add_parser('generate',  help='generate integrity files')
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


