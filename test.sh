#!/bin/bash
function fc() {
	`dirname $0`/filecheck $*
}

function assertMD5() {
	if [ $2. == . ] ; then
		echo "*** FILE: $1"
		cat $1
		read -p "MD5 = "`md5sum $1 | cut -b 1-32`" Continue? "
	else
		if [ `md5sum $1 | cut -b 1-32` != $2 ] ; then
			>&2 echo "ERROR: file $1 has wrong MD5 (not $2)"
		fi
	fi
}

rm -rf test
mkdir test

	# empty dir
fc generate test
fc check test

assertMD5 test/.filecheck edb8fe59d0410d8a2f51af16d4ed551e

echo "One" > test/One

	# one file
fc generate test 
fc check test

ONE=`md5sum test/One | cut -b 1-32`
assertMD5 test/.filecheck $ONE

	# subdir without -r
mkdir test/sub
echo "Sub" > test/sub/Two

fc generate test
fc check test

assertMD5 test/.filecheck $ONE
 
fc generate -r test
fc check -r test

assertMD5 test/.filecheck
assertMD5 test/sub/.filecheck

touch test/sub/Two
touch test/sub/Three

fc check -r test
fc update -r test

assertMD5 test/sub/.filecheck

fc check -r test

#rm -rf test
