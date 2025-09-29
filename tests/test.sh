#!/bin/bash
function fc() {
	`dirname $0`/../filecheck.sh $*
}

function assertFileMD5() {
    if [ ! -f "$1" ] ; then
		>&2 echo "ERROR: file $1 does not exist"
        exit 1
    fi

	if [ `md5sum $1 | cut -b 1-32` != "$2" ] ; then
		>&2 echo "ERROR: file $1 has wrong MD5 (not $2)"
	fi
}

function assertFilecheckMD5() {
    if [ ! -f "$1" ] ; then
		>&2 echo "ERROR: file $1 does not exist"
        exit 1
    fi

	FILECHECK="$(dirname "$1")/.filecheck"
    if [ ! -f "$FILECHECK" ] ; then
		>&2 echo "ERROR: file $FILECHECK does not exist"
        exit 1
    fi

	FILECHECK_MD5=$(grep ":$(basename "$1")" "$FILECHECK" | cut -d : -f 1)
	FILE_MD5=$(md5sum "$1" | cut -b 1-32)

	if [ "$FILECHECK_MD5" != "$FILE_MD5" ] ; then
		>&2 echo "ERROR: file $1 has wrong MD5 ($FILE_MD5 and not $FILECHECK_MD5)"
	fi
}

rm -rf test
mkdir test

	# empty dir
fc generate test
fc check test

assertFileMD5 test/.filecheck edb8fe59d0410d8a2f51af16d4ed551e

echo "One" > test/One

	# one file
fc generate test 
fc check test

assertFilecheckMD5 test/One

	# subdir without -r
mkdir test/sub
echo "Sub" > test/sub/Two

fc generate test
fc check test

fc generate -r test
fc check -r test

touch test/sub/Two
touch test/sub/Three

fc check -r test
fc update -r test

#assertMD5 test/sub/.filecheck

fc check -r test

#rm -rf test
