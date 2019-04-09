"""
Partial backport of new functionality in Python 3.5's os module:

    fsencode (new in Python 3.2)
    fsdecode (new in Python 3.2)

Backport modifications are marked with "XXX backport" and "TODO backport".
"""
from __future__ import unicode_literals

import abc
import sys

# XXX backport: unicode on Python 2
_str = unicode if sys.version_info < (3,) else str
# XXX backport: string and binary types differ between python 2 and 3
string_types = basestring if sys.version_info[0] == 2 else str
binary_type = str if sys.version_info[0] == 2 else bytes

# XXX backport: Use backported surrogateescape for Python 2
# TODO backport: Find a way to do this without pulling in the entire future package?
if sys.version_info < (3,):
    from future.utils.surrogateescape import register_surrogateescape
    register_surrogateescape()

# XXX This is a compatibility shiim for the PathLike backport which gets us fspath access
ABC = abc.ABCMeta(str('ABC'), (object,), {'__slots__': ()})

# XXX backport: This invalid_utf8_indexes() helper is shamelessly copied from
# Bob Ippolito's pyutf8 package (pyutf8/ref.py), in order to help support the
# Python 2 UTF-8 decoding hack in fsdecode() below.
#
# URL: https://github.com/etrepum/pyutf8/blob/master/pyutf8/ref.py
#
def _invalid_utf8_indexes(bytes):
    skips = []
    i = 0
    len_bytes = len(bytes)
    while i < len_bytes:
        c1 = bytes[i]
        if c1 < 0x80:
            # U+0000 - U+007F - 7 bits
            i += 1
            continue
        try:
            c2 = bytes[i + 1]
            if ((c1 & 0xE0 == 0xC0) and (c2 & 0xC0 == 0x80)):
                # U+0080 - U+07FF - 11 bits
                c = (((c1 & 0x1F) << 6) |
                     (c2 & 0x3F))
                if c < 0x80:  # pragma: no cover
                    # Overlong encoding
                    skips.extend([i, i + 1])  # pragma: no cover
                i += 2
                continue
            c3 = bytes[i + 2]
            if ((c1 & 0xF0 == 0xE0) and
                (c2 & 0xC0 == 0x80) and
                (c3 & 0xC0 == 0x80)):
                # U+0800 - U+FFFF - 16 bits
                c = (((((c1 & 0x0F) << 6) |
                       (c2 & 0x3F)) << 6) |
                     (c3 & 0x3f))
                if ((c < 0x800) or (0xD800 <= c <= 0xDFFF)):
                    # Overlong encoding or surrogate.
                    skips.extend([i, i + 1, i + 2])
                i += 3
                continue
            c4 = bytes[i + 3]
            if ((c1 & 0xF8 == 0xF0) and
                (c2 & 0xC0 == 0x80) and
                (c3 & 0xC0 == 0x80) and
                (c4 & 0xC0 == 0x80)):
                # U+10000 - U+10FFFF - 21 bits
                c = (((((((c1 & 0x0F) << 6) |
                         (c2 & 0x3F)) << 6) |
                       (c3 & 0x3F)) << 6) |
                     (c4 & 0x3F))
                if (c < 0x10000) or (c > 0x10FFFF):  # pragma: no cover
                    # Overlong encoding or invalid code point.
                    skips.extend([i, i + 1, i + 2, i + 3])
                i += 4
                continue
        except IndexError:
            pass
        skips.append(i)
        i += 1
    return skips


# XXX backport: Another helper to support the Python 2 UTF-8 decoding hack.
def _chunks(b, indexes):
    i = 0
    for j in indexes:
        yield b[i:j]
        yield b[j:j + 1]
        i = j + 1
    yield b[i:]


def fspath(path):
    """
    Fetch the string value from a path-like object

    Returns **None** if there is no string value.
    """

    if isinstance(path, (string_types, binary_type)):
        return path
    path_type = type(path)
    expect = "unicode" if sys.version_info[0] == 2 else "str"
    try:
        path_repr = path_type.__fspath__(path)
    except AttributeError:
        if hasattr(path_type, '__fspath__'):
            raise
        else:
            raise TypeError("expected {0}, bytes or os.PathLike object, "
                            "not ".format(expect) + path_type.__name__)
    if isinstance(path_repr, (string_types, binary_type)):
        return path_repr
    else:
        raise TypeError("expected {}.__fspath__() to return {} or bytes, "
                        "not {}".format(path_type.__name__, expect,
                                        type(path_repr).__name__))


def _fscodec():
    # XXX Backport: The following section attempts to use utf-8 encoders to
    # roundtrip to the filesystem, and also attempts to force windows to use
    # a "surrogate pass" error handling strategy to ignore the bad surrogate
    # pairs sometimes generated by python 2 encoders
    if sys.version_info[0] < 3:
        _fs_encode_errors = "surrogateescape"
        _fs_decode_errors = "surrogateescape"
        _fs_encoding = "utf-8"
    else:
        _fs_encoding = "utf-8"
        if sys.platform.startswith("win"):
            _fs_error_fn = None
            alt_strategy = "surrogatepass"
        else:
            if sys.version_info >= (3, 3):
                _fs_encoding = sys.getfilesystemencoding()
                if not _fs_encoding:
                    _fs_encoding = sys.getdefaultencoding()
            alt_strategy = "surrogateescape"
            _fs_error_fn = getattr(sys, "getfilesystemencodeerrors", None)
        _fs_encode_errors = _fs_error_fn() if _fs_error_fn else alt_strategy
        _fs_decode_errors = _fs_error_fn() if _fs_error_fn else alt_strategy

    _byte = chr if sys.version_info < (3,) else lambda i: bytes([i])


    def fsencode(filename):
        """Encode filename (an os.PathLike, bytes, or str) to the filesystem
        encoding with 'surrogateescape' error handler, return bytes unchanged.
        On Windows, use 'strict' error handler if the file system encoding is
        'mbcs' (which is the default encoding).
        """
        path = fspath(filename)
        if isinstance(path, _str):
            if sys.version_info[0] < 3:
                # XXX backport: Unlike Python 3, Python 2's UTF-8 codec does not
                # consider surrogate codepoints invalid, so the surrogateescape
                # error handler never gets invoked to encode them back into high
                # bytes.
                #
                # This code hacks around that by manually encoding the surrogate
                # codepoints to high bytes, without relying on surrogateescape.
                #
                # As a *separate* issue to the above, Python2's ASCII codec has
                # a different problem: it correctly invokes the surrogateescape
                # error handler, but then seems to do additional strict
                # validation (?) on the interim surrogate-decoded Unicode buffer
                # returned by surrogateescape, and then fails with a
                # UnicodeEncodeError anyway.
                #
                # The fix for that happens to be the same (manual encoding),
                # even though the two causes are quite different.
                #
                return b''.join(
                    (_byte(ord(c) - 0xDC00) if 0xDC00 <= ord(c) <= 0xDCFF else
                     c.encode(_fs_encoding, _fs_encode_errors))
                    for c in path)
            return path.encode(_fs_encoding, _fs_encode_errors)
        else:
            return path

    def fsdecode(filename):
        """Decode filename (an os.PathLike, bytes, or str) from the filesystem
        encoding with 'surrogateescape' error handler, return str unchanged. On
        Windows, use 'strict' error handler if the file system encoding is
        'mbcs' (which is the default encoding).
        """
        path = fspath(filename)
        if isinstance(path, bytes):
            if sys.version_info[0] < 3:
                # XXX backport: See the remarks in fsencode() above.
                #
                # This case is slightly trickier: Python 2 will invoke the
                # surrogateescape error handler for most bad high byte
                # sequences, *except* for full UTF-8 sequences that happen to
                # decode to surrogate codepoints.
                #
                # For decoding, it's not trivial to sidestep the UTF-8 codec
                # only for surrogates like fsencode() does, but as a hack we can
                # split the input into separate chunks around each invalid byte,
                # decode the chunks separately, and join the results.
                #
                # This prevents Python 2's UTF-8 codec from seeing the encoded
                # surrogate sequences as valid, which lets surrogateescape take
                # over and escape the individual bytes.
                #
                # TODO: Improve this.
                #
                from array import array
                indexes = _invalid_utf8_indexes(array(str('B'), filename))
                return ''.join(chunk.decode(_fs_encoding, _fs_decode_errors)
                               for chunk in _chunks(filename, indexes))
            return path.decode(_fs_encoding, _fs_decode_errors)
        else:
            return path

    return fsencode, fsdecode


fsencode, fsdecode = _fscodec()
del _fscodec


# If there is no C implementation, make the pure Python version the
# implementation as transparently as possible.
class PathLike(ABC):

    """Abstract base class for implementing the file system path protocol."""

    @abc.abstractmethod
    def __fspath__(self):
        """Return the file system path representation of the object."""
        raise NotImplementedError

    @classmethod
    def __subclasshook__(cls, subclass):
        return hasattr(subclass, '__fspath__')
