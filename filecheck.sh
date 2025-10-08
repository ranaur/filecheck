#!/bin/sh
FILECHECK_PY="$(dirname $(readlink -f "$0"))/filecheck.py"

type python >& /dev/null
[ $? -eq 0 ] && PYTHON=python

type python3 >& /dev/null
[ $? -eq 0 ] && PYTHON=python3

[ -z "$PYTHON" ] && echo "python 3 not found in system!" && exit 1
[ ! -f "$FILECHECK_PY" ] && echo "script found in system!" && exit 1

"$PYTHON" "$FILECHECK_PY" $*

exit $?
