"""
Partial backport of new functionality in Python 3.5's os module.

Backport modifications are marked with "XXX backport".
"""
from __future__ import unicode_literals

import sys

# XXX backport: unicode on Python 2
_str = unicode if sys.version_info < (3,) else str


def _fscodec():
    encoding = sys.getfilesystemencoding()
    if encoding == 'mbcs':
        errors = 'strict'
    else:
        errors = 'surrogateescape'

    def fsencode(filename):
        """
        Encode filename to the filesystem encoding with 'surrogateescape' error
        handler, return bytes unchanged. On Windows, use 'strict' error handler if
        the file system encoding is 'mbcs' (which is the default encoding).
        """
        if isinstance(filename, bytes):
            return filename
        elif isinstance(filename, _str):
            return filename.encode(encoding, errors)
        else:
            raise TypeError("expect bytes or str, not %s" % type(filename).__name__)

    def fsdecode(filename):
        """
        Decode filename from the filesystem encoding with 'surrogateescape' error
        handler, return str unchanged. On Windows, use 'strict' error handler if
        the file system encoding is 'mbcs' (which is the default encoding).
        """
        if isinstance(filename, _str):
            return filename
        elif isinstance(filename, bytes):
            return filename.decode(encoding, errors)
        else:
            raise TypeError("expect bytes or str, not %s" % type(filename).__name__)

    return fsencode, fsdecode

fsencode, fsdecode = _fscodec()
del _fscodec
